"""Financially safe delivery outbox transitions, independent of Telegram transport."""

from dataclasses import dataclass
from uuid import UUID

import asyncpg

from platform_core.ledger import _lock_wallet, settle
from platform_core.orders import acknowledge_delivery


@dataclass(frozen=True)
class DeliveryClaim:
    id: UUID
    order_id: UUID
    user_id: UUID
    telegram_user_id: int | None
    result_file_id: UUID
    attempt_number: int


async def claim_delivery(connection: asyncpg.Connection) -> DeliveryClaim | None:
    async with connection.transaction():
        row = await connection.fetchrow(
            """SELECT d.id,d.order_id,d.attempt_count,d.max_attempts,
               o.user_id,u.telegram_user_id,j.result_file_id
               FROM delivery_outbox d JOIN orders o ON o.id=d.order_id
               JOIN users u ON u.id=o.user_id JOIN jobs j ON j.order_id=o.id
               WHERE d.status='PENDING' AND d.next_attempt_at<=now()
               AND o.status='AWAITING_FULFILLMENT'
               AND j.status='COMPLETED' ORDER BY d.created_at,d.id LIMIT 1
               FOR UPDATE OF d SKIP LOCKED""",
        )
        if not row:
            return None
        attempt = row["attempt_count"] + 1
        if attempt > row["max_attempts"]:
            raise ValueError("delivery exhausted without settlement")
        await connection.execute(
            """UPDATE delivery_outbox SET status='SENDING',attempt_count=$2,
               claimed_at=now(),error_code=NULL WHERE id=$1""",
            row["id"], attempt,
        )
        return DeliveryClaim(
            row["id"], row["order_id"], row["user_id"], row["telegram_user_id"],
            row["result_file_id"], attempt,
        )


async def finish_delivery(
    connection: asyncpg.Connection, claim: DeliveryClaim, receipt: str,
) -> None:
    async with connection.transaction():
        await _lock_wallet(connection, claim.user_id)
        state = await connection.fetchrow(
            """SELECT status,attempt_count FROM delivery_outbox
               WHERE id=$1 AND order_id=$2 FOR UPDATE""",
            claim.id, claim.order_id,
        )
        if not state or state["status"] != "SENDING" or state["attempt_count"] != claim.attempt_number:
            raise ValueError("delivery attempt no longer active")
        await acknowledge_delivery(connection, claim.user_id, claim.order_id, receipt)
        await connection.execute(
            """UPDATE delivery_outbox SET status='SENT',external_receipt=$2,
               completed_at=now() WHERE id=$1""",
            claim.id, receipt,
        )


async def fail_delivery(
    connection: asyncpg.Connection, claim: DeliveryClaim, error_code: str, *, retryable: bool,
) -> bool:
    """Return True if attempts exhausted, the order failed, and reservation released."""
    if not error_code or len(error_code) > 100:
        raise ValueError("invalid delivery error")
    async with connection.transaction():
        await _lock_wallet(connection, claim.user_id)
        state = await connection.fetchrow(
            """SELECT status,attempt_count,max_attempts FROM delivery_outbox
               WHERE id=$1 AND order_id=$2 FOR UPDATE""",
            claim.id, claim.order_id,
        )
        if not state or state["status"] != "SENDING" or state["attempt_count"] != claim.attempt_number:
            return False
        exhausted = not retryable or state["attempt_count"] >= state["max_attempts"]
        await connection.execute(
            """UPDATE delivery_outbox SET status=$2,error_code=$3,
               next_attempt_at=now() + ($5 * interval '1 second'),
               completed_at=CASE WHEN $4 THEN now() ELSE NULL END WHERE id=$1""",
            claim.id, "FAILED" if exhausted else "PENDING", error_code, exhausted,
            30 * state["attempt_count"],
        )
        if exhausted:
            price = await connection.fetchval(
                "SELECT price_snapshot_halalas FROM orders WHERE id=$1", claim.order_id,
            )
            await connection.execute("UPDATE orders SET status='FAILED' WHERE id=$1", claim.order_id)
            if price:
                await settle(
                    connection, claim.user_id, claim.order_id,
                    f"release:{claim.order_id}", kind="RELEASE",
                )
        return exhausted


async def recover_stale_deliveries(
    connection: asyncpg.Connection, timeout_seconds: int = 180,
) -> int:
    if timeout_seconds < 120:
        raise ValueError("delivery timeout too short")
    rows = await connection.fetch(
        """SELECT d.id,d.order_id,d.attempt_count,o.user_id,u.telegram_user_id,j.result_file_id
           FROM delivery_outbox d JOIN orders o ON o.id=d.order_id
           JOIN users u ON u.id=o.user_id JOIN jobs j ON j.order_id=o.id
           WHERE d.status='SENDING' AND d.claimed_at < now() - ($1 * interval '1 second')
           ORDER BY d.claimed_at LIMIT 100""",
        timeout_seconds,
    )
    recovered = 0
    for row in rows:
        claim = DeliveryClaim(
            row["id"], row["order_id"], row["user_id"], row["telegram_user_id"],
            row["result_file_id"], row["attempt_count"],
        )
        await fail_delivery(connection, claim, "DELIVERY_TIMEOUT", retryable=True)
        recovered += 1
    return recovered
