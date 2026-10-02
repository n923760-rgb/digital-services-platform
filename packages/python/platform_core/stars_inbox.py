"""Persist only payment fields before polling acknowledges updates; retry from PostgreSQL."""

import json
import logging

from platform_core.stars_payments import (
    StarsMismatch,
    accept_star_payment,
    confirm_star_refund,
)


logger = logging.getLogger(__name__)


async def persist_payment_update(connection, bot_id, update):
    message = update.message
    if message is None or message.chat.type != "private":
        return
    payment = message.successful_payment or message.refunded_payment
    if payment is None:
        return
    is_refund = message.refunded_payment is not None
    # Refund service messages can be authored by the bot; the private chat identifies the buyer.
    payer = message.chat.id if is_refund else message.from_user.id if message.from_user else None
    event = {
        "kind": "REFUNDED" if is_refund else "PAID", "telegram_user_id": payer,
        "payload": payment.invoice_payload, "currency": payment.currency,
        "amount": payment.total_amount, "charge_id": payment.telegram_payment_charge_id,
    }
    if payer != message.chat.id:
        raise StarsMismatch("payment sender and private chat differ")
    await connection.execute(
        """INSERT INTO telegram_payment_inbox (bot_id,update_id,event)
           VALUES ($1,$2,$3::jsonb) ON CONFLICT (bot_id,update_id) DO NOTHING""",
        bot_id, update.update_id, json.dumps(event),
    )


async def process_payment_inbox(
    connection, bot_id, *, allow_fulfillment, service_slug: str | None = None,
) -> int:
    processed = 0
    # One row/transaction avoids rolling back earlier receipts when a later event fails.
    for _ in range(20):
        async with connection.transaction():
            row = await connection.fetchrow(
                """SELECT update_id,event FROM telegram_payment_inbox
                   WHERE bot_id=$1 AND status='PENDING'
                   ORDER BY COALESCE(attempted_at,created_at),update_id
                   LIMIT 1 FOR UPDATE SKIP LOCKED""", bot_id,
            )
            if not row:
                break
            event = row["event"]
            if isinstance(event, str):
                event = json.loads(event)
            try:
                # Savepoint permits classifying a mismatch without a partially recorded payment.
                async with connection.transaction():
                    args = (connection, event["telegram_user_id"], event["payload"],
                            event["currency"], event["amount"], event["charge_id"])
                    if event["kind"] == "REFUNDED":
                        await confirm_star_refund(*args)
                    else:
                        await accept_star_payment(
                            *args, allow_fulfillment=allow_fulfillment, service_slug=service_slug,
                        )
            except StarsMismatch:
                logger.warning("star_receipt_rejected")
                await connection.execute(
                    """UPDATE telegram_payment_inbox SET status='REJECTED',attempted_at=now()
                       WHERE bot_id=$1 AND update_id=$2""", bot_id, row["update_id"],
                )
            else:
                await connection.execute(
                    """UPDATE telegram_payment_inbox SET status='DONE',attempted_at=now()
                       WHERE bot_id=$1 AND update_id=$2""", bot_id, row["update_id"],
                )
            processed += 1
    return processed
