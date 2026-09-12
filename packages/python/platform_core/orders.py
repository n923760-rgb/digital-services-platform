"""Idempotent order confirmation; caller later dispatches durable PENDING jobs."""

import json
from collections.abc import Sequence
from uuid import UUID, uuid4

import asyncpg

from platform_core.ledger import IdempotencyConflict, _lock_wallet, reserve, settle


async def ensure_telegram_user(connection: asyncpg.Connection, telegram_user_id: int) -> UUID:
    if telegram_user_id <= 0:
        raise ValueError("invalid Telegram user id")
    async with connection.transaction():
        await connection.execute(
            """INSERT INTO users (id,telegram_user_id) VALUES ($1,$2)
               ON CONFLICT (telegram_user_id) DO NOTHING""",
            uuid4(), telegram_user_id,
        )
        user_id = await connection.fetchval(
            "SELECT id FROM users WHERE telegram_user_id=$1", telegram_user_id,
        )
        await connection.execute(
            "INSERT INTO wallets (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING",
            user_id,
        )
        return user_id


async def confirm_order(
    connection: asyncpg.Connection, user_id: UUID, service_id: UUID,
    client_request_key: str, channel: str = "telegram", *, file_ids: Sequence[UUID] = (),
) -> UUID:
    if not client_request_key.strip() or len(client_request_key) > 160:
        raise ValueError("invalid request key")
    async with connection.transaction():
        await _lock_wallet(connection, user_id)
        existing = await connection.fetchrow(
            """SELECT id,service_id,channel FROM orders
               WHERE user_id=$1 AND client_request_key=$2""",
            user_id, client_request_key,
        )
        if existing:
            if existing["service_id"] != service_id or existing["channel"] != channel:
                raise IdempotencyConflict("request key already used for a different order")
            prior_files = await connection.fetch(
                "SELECT file_id FROM order_files WHERE order_id=$1 ORDER BY position", existing["id"],
            )
            if [row["file_id"] for row in prior_files] != list(file_ids):
                raise IdempotencyConflict("request key already used with different inputs")
            return existing["id"]
        service = await connection.fetchrow(
            """SELECT s.base_price_halalas,s.input_schema FROM services s
               JOIN service_categories c ON c.id=s.category_id
               WHERE s.id=$1 AND s.enabled=true AND c.enabled=true""", service_id,
        )
        if not service:
            raise ValueError("service unavailable")
        schema = service["input_schema"]
        if isinstance(schema, str):
            schema = json.loads(schema)
        if not isinstance(schema, dict):
            raise ValueError("invalid service input schema")
        minimum = schema.get("min_files", 0)
        maximum = schema.get("max_files", 0)
        if (type(minimum) is not int or type(maximum) is not int or minimum < 0
                or maximum < minimum or maximum > 20):
            raise ValueError("invalid service file schema")
        if not minimum <= len(file_ids) <= maximum or len(set(file_ids)) != len(file_ids):
            raise ValueError("invalid number of input files")
        if file_ids:
            files = await connection.fetch(
                """SELECT id,mime_type FROM files WHERE id = ANY($1::uuid[])
                   AND owner_user_id=$2 AND status='READY' AND retention_until>now()""",
                list(file_ids), user_id,
            )
            expected = schema.get("file_mime")
            if (len(files) != len(file_ids) or not isinstance(expected, str)
                    or any(row["mime_type"] != expected for row in files)):
                raise ValueError("input file missing, expired or wrong type")
        price = service["base_price_halalas"]
        order_id = uuid4()
        await connection.execute(
            """INSERT INTO orders
               (id,user_id,service_id,client_request_key,channel,price_snapshot_halalas,status)
               VALUES ($1,$2,$3,$4,$5,$6,'DRAFT')""",
            order_id, user_id, service_id, client_request_key, channel, price,
        )
        if price:
            await reserve(connection, user_id, order_id, price, f"reserve:{order_id}")
        await connection.execute("UPDATE orders SET status='RESERVED' WHERE id=$1", order_id)
        for position, file_id in enumerate(file_ids):
            await connection.execute(
                "INSERT INTO order_files (order_id,position,file_id) VALUES ($1,$2,$3)",
                order_id, position, file_id,
            )
        await connection.execute(
            "INSERT INTO jobs (id,order_id,status) VALUES ($1,$2,'PENDING')", uuid4(), order_id,
        )
        return order_id


async def acknowledge_delivery(
    connection: asyncpg.Connection, user_id: UUID, order_id: UUID, receipt: str,
) -> None:
    """Only a trusted delivery adapter may confirm external delivery and capture funds."""
    if not receipt.strip() or len(receipt) > 200:
        raise ValueError("invalid delivery receipt")
    async with connection.transaction():
        await _lock_wallet(connection, user_id)
        order = await connection.fetchrow(
            """SELECT status,delivery_receipt,price_snapshot_halalas FROM orders
               WHERE id=$1 AND user_id=$2 FOR UPDATE""",
            order_id, user_id,
        )
        if not order:
            raise ValueError("order not found")
        if order["status"] == "COMPLETED":
            if order["delivery_receipt"] != receipt:
                raise IdempotencyConflict("order delivered with different receipt")
            return
        if order["status"] != "AWAITING_FULFILLMENT":
            raise ValueError("order not ready for delivery")
        ready = await connection.fetchval(
            """SELECT 1 FROM jobs j JOIN files f ON f.id=j.result_file_id
               WHERE j.order_id=$1 AND j.status='COMPLETED' AND f.file_type='OUTPUT'
               AND f.order_id=$1 AND f.owner_user_id=$2 AND f.status='READY'
               AND f.retention_until>now() LIMIT 1""",
            order_id, user_id,
        )
        if not ready:
            raise ValueError("result unavailable")
        if order["price_snapshot_halalas"]:
            await settle(connection, user_id, order_id, f"capture:{order_id}", kind="CAPTURE")
        await connection.execute(
            """UPDATE orders SET status='COMPLETED',completed_at=now(),delivery_receipt=$2
               WHERE id=$1""",
            order_id, receipt,
        )
