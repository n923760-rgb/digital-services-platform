"""Private XTR invoices, bounded checkout validation and provider-confirmed refunds."""

import asyncio
import hashlib
import logging

import asyncpg
from aiogram import Bot
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery, TransactionPartnerUser
from platform_core.config import get_settings
from platform_core.orders import ensure_telegram_user
from platform_core.stars_inbox import persist_payment_update, process_payment_inbox
from platform_core.stars_payments import (
    approve_star_checkout,
    confirm_star_refund,
    create_star_invoice,
)
from platform_core.telegram_workflow import StaleQuote

logger = logging.getLogger(__name__)


def terms_digest(settings) -> str:
    return hashlib.sha256(settings.telegram_payment_terms.strip().encode()).hexdigest()


def checkout_enabled(settings) -> bool:
    return bool(settings.telegram_orders_enabled and settings.telegram_stars_enabled
                and settings.telegram_payment_terms.strip()
                and settings.telegram_payment_support.strip())


async def invoice(callback: CallbackQuery, bot: Bot) -> None:
    from uuid import UUID

    settings = get_settings()
    if (not isinstance(callback.message, Message) or callback.message.chat.type != "private"
            or callback.message.chat.id != callback.from_user.id or not checkout_enabled(settings)):
        await callback.answer("الدفع غير متاح حاليًا.", show_alert=True)
        return
    connection = None
    try:
        key, revision = callback.data.removeprefix("stars:confirm:").split(":")
        workflow_id = UUID(hex=key)
        revision = int(revision)
        if not 1 <= revision <= 2**31 - 1:
            raise ValueError("invalid revision")
        await callback.answer()
        connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
        user_id = await ensure_telegram_user(connection, callback.from_user.id)
        payment = await create_star_invoice(
            connection, user_id, workflow_id, revision, settings.telegram_payment_terms.strip(),
        )
        if payment.order_id:
            await callback.message.answer(f"دفعك مسجل مسبقًا. رقم الطلب: {payment.order_id}")
            return
        await bot.send_invoice(
            chat_id=callback.from_user.id, title="دمج ملفات PDF",
            description="دفع مباشر لهذا الطلب. التنفيذ بعد تأكيد الدفع. الشروط: /terms",
            payload=payment.payload, provider_token="", currency="XTR",
            prices=[LabeledPrice(label="دمج PDF", amount=payment.amount_stars)],
            start_parameter="stars-payment", protect_content=True,
        )
    except (ValueError, StaleQuote):
        await callback.message.answer("تغير العرض أو انتهى. راجع السعر والشروط وأكد من الزر الجديد.")
    except Exception:
        logger.warning("star_invoice_unavailable")
        await callback.message.answer("تعذر إرسال الفاتورة مؤقتًا. حاول مرة أخرى.")
    finally:
        if connection is not None:
            await connection.close()


async def precheckout(query: PreCheckoutQuery) -> None:
    settings = get_settings()
    connection = None
    accepted = False
    try:
        if checkout_enabled(settings):
            # Leave time for the Telegram answer inside its ten-second deadline.
            async with asyncio.timeout(5):
                connection = await asyncpg.connect(
                    settings.database_url.replace("+asyncpg", ""), timeout=2,
                )
                await approve_star_checkout(
                    connection, query.from_user.id, query.invoice_payload, query.currency,
                    query.total_amount, query.id, terms_digest(settings),
                )
                accepted = True
    except Exception:
        logger.warning("star_checkout_rejected")
    finally:
        if connection is not None:
            await connection.close(timeout=0.5)
    await query.answer(ok=accepted, **({} if accepted else {
        "error_message": "تعذر الدفع لهذا العرض. راجع السعر والملفات والشروط ثم حاول مجددًا.",
    }))


async def payment_notice(message: Message) -> None:
    await message.answer(
        "وصل تحديث الدفع ويجري التحقق منه. تابع «📋 طلباتي». "
        "للاستفسار عن الدفع استخدم /paysupport."
    )


async def poll_updates(bot: Bot, dispatcher) -> None:
    """Advance getUpdates offset only after durable receipt insertion, even if handlers fail."""
    offset = None
    settings = get_settings()
    while True:
        try:
            updates = await bot.get_updates(
                offset=offset, timeout=25, allowed_updates=dispatcher.resolve_used_update_types(),
            )
            for update in updates:
                message = update.message
                if message and (message.successful_payment or message.refunded_payment):
                    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
                    try:
                        await persist_payment_update(connection, bot.id, update)
                    finally:
                        await connection.close()
                try:
                    await dispatcher.feed_update(bot, update)
                except Exception:
                    logger.warning("telegram_update_handler_failed")
                offset = update.update_id + 1
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("telegram_poll_retry")
            await asyncio.sleep(2)


async def reconcile_refund(bot, connection, row) -> bool:
    history = await bot.get_star_transactions(offset=0, limit=100)
    for transaction in history.transactions:
        receiver = transaction.receiver
        if (transaction.id == row["charge_id"] and abs(transaction.amount) == row["amount_stars"]
                and transaction.nanostar_amount in (None, 0)
                and isinstance(receiver, TransactionPartnerUser)
                and receiver.transaction_type == "invoice_payment"
                and receiver.user.id == row["telegram_user_id"]
                and receiver.invoice_payload == f"stars:{row['invoice_id'].hex}"):
            return True
    return False


async def process_refunds(bot, connection) -> int:
    # No database lock is held across provider I/O. Retry time bounds concurrent claims.
    async with connection.transaction():
        rows = await connection.fetch(
            """SELECT c.charge_id,c.invoice_id,i.amount_stars,u.telegram_user_id
               FROM star_charges c JOIN star_invoices i ON i.id=c.invoice_id
               JOIN users u ON u.id=i.user_id WHERE c.status='REFUND_PENDING'
               AND (c.refund_attempted_at IS NULL
                    OR c.refund_attempted_at<now()-interval '60 seconds')
               ORDER BY COALESCE(c.refund_attempted_at,c.created_at),c.charge_id
               LIMIT 5 FOR UPDATE OF c SKIP LOCKED""",
        )
        for row in rows:
            await connection.execute(
                "UPDATE star_charges SET refund_attempted_at=now() WHERE charge_id=$1",
                row["charge_id"],
            )
    confirmed = 0
    for row in rows:
        try:
            async with asyncio.timeout(8):
                ok = await bot.refund_star_payment(
                    user_id=row["telegram_user_id"], telegram_payment_charge_id=row["charge_id"],
                )
        except Exception:
            # A timeout/crash may follow provider success. Use positive transaction evidence.
            try:
                async with asyncio.timeout(8):
                    ok = await reconcile_refund(bot, connection, row)
            except Exception:
                ok = False
        if ok is True:
            await confirm_star_refund(
                connection, row["telegram_user_id"], f"stars:{row['invoice_id'].hex}",
                "XTR", row["amount_stars"], row["charge_id"],
            )
            confirmed += 1
        else:
            logger.warning("star_refund_pending")
    return confirmed


async def process_billing(connection, bot, settings) -> None:
    await process_payment_inbox(connection, bot.id, allow_fulfillment=checkout_enabled(settings))
    await process_refunds(bot, connection)
