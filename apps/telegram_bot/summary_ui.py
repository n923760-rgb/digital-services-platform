"""Thin private Telegram text-summary transport; application state stays in platform_core."""

import logging

import asyncpg
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from platform_core.config import get_settings
from platform_core.stars_inbox import process_payment_inbox
from platform_core.summary_orders import (
    acknowledge_summary,
    execute_summary,
    paid_summary_orders,
    quote_summary,
)
from platform_core.text_summary import SLUG, InvalidSummaryInput, SummaryProviderError

from apps.telegram_bot.stars_payments import checkout_enabled, process_refunds

logger = logging.getLogger(__name__)


async def connect():
    return await asyncpg.connect(get_settings().database_url.replace("+asyncpg", ""), timeout=3)


async def quote(message: Message):
    settings = get_settings()
    if not checkout_enabled(settings):
        await message.answer("الخدمة قيد التجهيز. الدفع غير متاح حاليًا.")
        return
    connection = await connect()
    try:
        offer = await quote_summary(
            connection, message.from_user.id, message.message_id, message.text,
            settings.telegram_payment_terms, retention_days=settings.file_retention_days,
        )
    except (InvalidSummaryInput, ValueError):
        logger.info("summary_quote_rejected")
        await message.answer("أرسل نصًا من 20 إلى 4,000 حرف. قد تكون الخدمة غير متاحة؛ حاول لاحقًا.")
        return
    finally:
        await connection.close()
    await message.answer(
        f"تلخيص محلي باختيار جمل من النص، وليس ذكاء اصطناعيًا توليديًا.\n"
        f"السعر: {offer.price_stars} ⭐\n{settings.telegram_payment_terms.strip()}\n"
        "الضغط يعني الموافقة على هذه الشروط والدفع لهذا النص.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="أوافق على الشروط وأدفع بالنجوم",
                                 callback_data=f"stars:confirm:{offer.workflow_id.hex}:{offer.revision}"),
        ]]),
    )


async def deliver_pending(connection, bot, telegram_user_id=None):
    for row in await paid_summary_orders(connection, telegram_user_id):
        try:
            result = await execute_summary(connection, row["telegram_user_id"], row["id"])
        except (SummaryProviderError, ValueError, OSError):
            logger.warning("summary_execution_failed")
            continue
        if result is None:
            continue
        try:
            sent = await bot.send_message(
                row["telegram_user_id"],
                f"ملخص محلي — الطلب {row['id']}\n\n{result}",
            )
        except (TelegramAPIError, OSError):
            # Provider error can follow an accepted send; retain cached result for explicit retry.
            logger.warning("summary_delivery_uncertain")
            continue
        await acknowledge_summary(
            connection, row["telegram_user_id"], row["id"], f"telegram:{sent.chat.id}:{sent.message_id}",
        )


async def billing(bot, telegram_user_id=None):
    connection = await connect()
    try:
        await process_payment_inbox(
            connection, bot.id, allow_fulfillment=checkout_enabled(get_settings()), service_slug=SLUG,
        )
        try:
            await deliver_pending(connection, bot, telegram_user_id)
        finally:
            await process_refunds(bot, connection)
    finally:
        await connection.close()
