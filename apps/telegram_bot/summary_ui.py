"""Thin private Telegram text-summary transport; application state stays in platform_core."""

import logging
from uuid import UUID

import asyncpg
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from platform_core.config import get_settings
from platform_core.service_catalog import available_summary_products
from platform_core.stars_inbox import process_payment_inbox
from platform_core.summary_orders import (
    acknowledge_summary,
    execute_summary,
    paid_summary_orders,
    quote_summary,
    select_summary_product,
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
        await message.answer("اختر المنتج من /services، ثم أرسل نصًا من 20 إلى 4,000 حرف. قد تكون الخدمة غير متاحة.")
        return
    finally:
        await connection.close()
    # Full terms fit their own message even at the configured Unicode character limit.
    await message.answer(settings.telegram_payment_terms.strip())
    await message.answer(
        f"{offer.service_name}\nتلخيص محلي باختيار جمل من النص، وليس ذكاء اصطناعيًا توليديًا.\n"
        f"السعر: {offer.price_stars} ⭐\n"
        "الضغط يعني الموافقة على الشروط المعروضة في الرسالة السابقة والدفع لهذا النص.",
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
            connection, bot.id, allow_fulfillment=checkout_enabled(get_settings()), processor_key=SLUG,
        )
        try:
            await deliver_pending(connection, bot, telegram_user_id)
        finally:
            await process_refunds(bot, connection)
    finally:
        await connection.close()


async def show_products(message):
    if not checkout_enabled(get_settings()):
        await message.answer("الخدمات قيد التجهيز. الدفع غير متاح حاليًا.")
        return
    connection = await connect()
    try:
        products = await available_summary_products(connection)
    finally:
        await connection.close()
    if not products:
        await message.answer("لا توجد منتجات متاحة حاليًا. تابع لاحقًا أو استخدم /paysupport.")
        return
    await message.answer(
        "اختر خدمة؛ ستراجع السعر والشروط قبل الدفع. الأسعار بالنجوم.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{product.name_ar} · {product.price_stars} ⭐",
                callback_data=f"product:select:{product.id.hex}",
            )] for product in products
        ]),
    )


async def select_product(callback):
    # Buttons on a bot-authored message identify the customer through callback.from_user.
    if (not isinstance(callback.message, Message) or callback.message.chat.type != "private"
            or callback.message.chat.id != callback.from_user.id or callback.from_user.is_bot
            or not checkout_enabled(get_settings())):
        await callback.answer("الخدمة غير متاحة.", show_alert=True)
        return
    try:
        service_id = UUID(hex=callback.data.removeprefix("product:select:"))
    except (ValueError, AttributeError):
        logger.info("summary_product_callback_rejected")
        await callback.answer("اختر المنتج من /services.", show_alert=True)
        return
    connection = await connect()
    try:
        try:
            product = await select_summary_product(connection, callback.from_user.id, service_id)
        except ValueError:
            logger.info("summary_product_unavailable")
            await callback.answer("تغيّرت إتاحة المنتج. افتح /services مجددًا.", show_alert=True)
            return
    finally:
        await connection.close()
    await callback.answer()
    await callback.message.answer(
        f"{product.name_ar}\n{product.description_ar}\nالسعر الحالي: {product.price_stars} ⭐\n"
        "التنفيذ: تلخيص محلي يختار جملًا من النص. أرسل نصًا من 20 إلى 4,000 حرف.\n"
        "ستراجع السعر والشروط قبل الدفع. /cancel لإلغاء الاختيار."
    )
