"""SAR wallet operations. Call with one PostgreSQL connection; never cache balances."""

from dataclasses import dataclass
from uuid import UUID, uuid4

import asyncpg


class InsufficientFunds(ValueError):
    pass


class IdempotencyConflict(ValueError):
    pass


class InvalidSettlement(ValueError):
    pass


@dataclass(frozen=True)
class Balance:
    available_halalas: int
    reserved_halalas: int


async def _lock_wallet(connection: asyncpg.Connection, user_id: UUID) -> None:
    # All wallet writes lock the same row before reading ledger totals or checking keys.
    exists = await connection.fetchval("SELECT 1 FROM wallets WHERE user_id=$1 FOR UPDATE", user_id)
    if not exists:
        raise ValueError("wallet not found")


async def balance(connection: asyncpg.Connection, user_id: UUID) -> Balance:
    row = await connection.fetchrow(
        """SELECT
          COALESCE(SUM(CASE transaction_type
            WHEN 'TOP_UP' THEN amount_halalas WHEN 'BONUS' THEN amount_halalas
            WHEN 'REFUND' THEN amount_halalas WHEN 'ADMIN_ADJUSTMENT' THEN amount_halalas
            WHEN 'RELEASE' THEN amount_halalas WHEN 'RESERVE' THEN -amount_halalas
            ELSE 0 END), 0) AS available,
          COALESCE(SUM(CASE transaction_type WHEN 'RESERVE' THEN amount_halalas
            WHEN 'CAPTURE' THEN -amount_halalas WHEN 'RELEASE' THEN -amount_halalas
            ELSE 0 END), 0) AS reserved
          FROM wallet_transactions WHERE wallet_user_id=$1""",
        user_id,
    )
    return Balance(row["available"], row["reserved"])


async def _same_key(
    connection: asyncpg.Connection, user_id: UUID, key: str, kind: str,
    amount_halalas: int, order_id: UUID | None, reason: str | None = None,
) -> bool:
    existing = await connection.fetchrow(
        """SELECT transaction_type, amount_halalas, order_id, reason
           FROM wallet_transactions WHERE wallet_user_id=$1 AND idempotency_key=$2""",
        user_id, key,
    )
    if not existing:
        return False
    if (existing["transaction_type"], existing["amount_halalas"], existing["order_id"]) != (
        kind, amount_halalas, order_id,
    ):
        raise IdempotencyConflict("same key used for a different wallet operation")
    if kind == "ADMIN_ADJUSTMENT" and existing["reason"] != reason:
        raise IdempotencyConflict("same key used for a different adjustment reason")
    return True


async def credit(
    connection: asyncpg.Connection, user_id: UUID, amount_halalas: int, key: str,
    *, kind: str = "TOP_UP", reason: str | None = None,
) -> Balance:
    """Internal entrypoint only: payments/admin adapters must authenticate before invoking."""
    if kind not in {"TOP_UP", "BONUS", "ADMIN_ADJUSTMENT"}:
        raise ValueError("unsupported credit type")
    if amount_halalas == 0 or (amount_halalas < 0 and kind != "ADMIN_ADJUSTMENT"):
        raise ValueError("invalid credit amount")
    if kind == "ADMIN_ADJUSTMENT" and not (reason and reason.strip()):
        raise ValueError("administrative adjustment requires a reason")
    async with connection.transaction():
        await _lock_wallet(connection, user_id)
        if await _same_key(connection, user_id, key, kind, amount_halalas, None, reason):
            return await balance(connection, user_id)
        current = await balance(connection, user_id)
        if current.available_halalas + amount_halalas < 0:
            raise InsufficientFunds("adjustment exceeds available balance")
        await connection.execute(
            """INSERT INTO wallet_transactions
               (id,wallet_user_id,transaction_type,amount_halalas,idempotency_key,reason)
               VALUES ($1,$2,$3,$4,$5,$6)""",
            uuid4(), user_id, kind, amount_halalas, key, reason,
        )
        return await balance(connection, user_id)


async def reserve(
    connection: asyncpg.Connection, user_id: UUID, order_id: UUID,
    amount_halalas: int, key: str,
) -> Balance:
    if amount_halalas <= 0:
        raise ValueError("reservation must be positive")
    async with connection.transaction():
        await _lock_wallet(connection, user_id)
        if await _same_key(connection, user_id, key, "RESERVE", amount_halalas, order_id):
            return await balance(connection, user_id)
        order = await connection.fetchrow(
            "SELECT user_id,price_snapshot_halalas,status FROM orders WHERE id=$1", order_id,
        )
        if not order or order["user_id"] != user_id or order["price_snapshot_halalas"] != amount_halalas:
            raise ValueError("reservation does not match order")
        if order["status"] not in {"DRAFT", "AWAITING_PAYMENT", "RESERVED"}:
            raise ValueError("order cannot be reserved")
        prior = await connection.fetchval(
            "SELECT 1 FROM wallet_transactions WHERE order_id=$1 AND transaction_type='RESERVE'",
            order_id,
        )
        if prior:
            raise IdempotencyConflict("order already reserved with another key")
        current = await balance(connection, user_id)
        if current.available_halalas < amount_halalas:
            raise InsufficientFunds("insufficient available balance")
        await connection.execute(
            """INSERT INTO wallet_transactions
               (id,wallet_user_id,order_id,transaction_type,amount_halalas,idempotency_key)
               VALUES ($1,$2,$3,'RESERVE',$4,$5)""",
            uuid4(), user_id, order_id, amount_halalas, key,
        )
        return await balance(connection, user_id)


async def settle(
    connection: asyncpg.Connection, user_id: UUID, order_id: UUID,
    key: str, *, kind: str,
) -> Balance:
    if kind not in {"CAPTURE", "RELEASE"}:
        raise ValueError("unsupported settlement")
    async with connection.transaction():
        await _lock_wallet(connection, user_id)
        reservation = await connection.fetchrow(
            """SELECT amount_halalas FROM wallet_transactions
               WHERE wallet_user_id=$1 AND order_id=$2 AND transaction_type='RESERVE'""",
            user_id, order_id,
        )
        if not reservation:
            raise InvalidSettlement("order has no reservation")
        amount = reservation["amount_halalas"]
        if await _same_key(connection, user_id, key, kind, amount, order_id):
            return await balance(connection, user_id)
        settled = await connection.fetchval(
            """SELECT transaction_type FROM wallet_transactions
               WHERE order_id=$1 AND transaction_type IN ('CAPTURE','RELEASE')""",
            order_id,
        )
        if settled:
            raise InvalidSettlement(f"order already settled as {settled}")
        await connection.execute(
            """INSERT INTO wallet_transactions
               (id,wallet_user_id,order_id,transaction_type,amount_halalas,idempotency_key)
               VALUES ($1,$2,$3,$4,$5,$6)""",
            uuid4(), user_id, order_id, kind, amount, key,
        )
        return await balance(connection, user_id)
