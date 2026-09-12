"""Idempotent order confirmation; caller later dispatches durable PENDING jobs."""

from uuid import UUID, uuid4

import asyncpg

from platform_core.ledger import IdempotencyConflict, _lock_wallet, reserve


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
    client_request_key: str, channel: str = "telegram",
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
            return existing["id"]
        service = await connection.fetchrow(
            "SELECT base_price_halalas FROM services WHERE id=$1 AND enabled=true", service_id,
        )
        if not service:
            raise ValueError("service unavailable")
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
        await connection.execute(
            "INSERT INTO jobs (id,order_id,status) VALUES ($1,$2,'PENDING')", uuid4(), order_id,
        )
        return order_id
