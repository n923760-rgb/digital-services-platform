import asyncio
import logging
import os
from contextlib import suppress
from pathlib import Path
from uuid import UUID

import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from platform_core.config import get_settings
from platform_core.ledger import balance
from platform_core.logging import configure_logging
from platform_core.orders import ensure_telegram_user
from platform_core.service_catalog import available_services
from platform_core.telegram_workflow import active_workflow

from apps.telegram_bot import pdf_workflow

logger = logging.getLogger(__name__)
dispatcher = Dispatcher()
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✨ الخدمات"), KeyboardButton(text="🧰 الأدوات")],
        [KeyboardButton(text="➕ اطلب خدمة"), KeyboardButton(text="📁 ملفاتي")],
        [KeyboardButton(text="💰 رصيدي"), KeyboardButton(text="🛒 المتجر الرقمي")],
    ],
    resize_keyboard=True,
)
merge_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        *keyboard.keyboard,
        [KeyboardButton(text="🔗 دمج PDF"), KeyboardButton(text="✅ مراجعة السعر")],
    ],
    resize_keyboard=True,
)


@dispatcher.message(CommandStart())
async def start(message: Message) -> None:
    if message.chat.type != "private" or message.from_user is None:
        return
    await message.answer(
        "أهلًا 👋\nوش تحتاج أسوي لك؟\n"
        "اكتب طلبك مباشرة، أو أرسل صورة، ملف، رابط أو تسجيل صوتي.\n"
        "الخدمات قيد التجهيز حاليًا.",
        reply_markup=merge_keyboard if get_settings().telegram_orders_enabled else keyboard,
    )
    settings = get_settings()
    if settings.telegram_orders_enabled:
        connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
        try:
            user_id = await ensure_telegram_user(connection, message.from_user.id)
            workflow = await active_workflow(connection, user_id)
            if workflow:
                await message.answer(
                    f"عندك طلب دمج PDF غير مكتمل ({workflow.file_count} ملفات). "
                    "اختر «🔗 دمج PDF» لاستكماله."
                )
        finally:
            await connection.close()


@dispatcher.message(Command("merge"))
async def merge_command(message: Message) -> None:
    if message.chat.type == "private" and message.from_user:
        await pdf_workflow.begin(message)


@dispatcher.message(Command("cancel"))
async def cancel_command(message: Message) -> None:
    if message.chat.type == "private" and message.from_user:
        await pdf_workflow.cancel(message)


@dispatcher.message(F.document)
async def document_message(message: Message, bot: Bot) -> None:
    if message.chat.type == "private" and message.from_user:
        await pdf_workflow.upload(message, bot)


@dispatcher.callback_query(F.data.startswith("merge:confirm:"))
async def confirm_callback(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message) or callback.message.chat.type != "private":
        await callback.answer()
        return
    try:
        workflow_id = UUID(callback.data.removeprefix("merge:confirm:"))
    except (ValueError, AttributeError):
        await callback.answer("تأكيد غير صالح.", show_alert=True)
        return
    await callback.answer()
    await pdf_workflow.confirm(callback.message, workflow_id, callback.from_user.id)


async def show_catalog(message: Message) -> None:
    settings = get_settings()
    if not settings.telegram_orders_enabled:
        await message.answer("الخدمات قيد التجهيز حاليًا. اكتب طلبك، وسنعلن إتاحتها هنا قريبًا.")
        return
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        services = await available_services(connection)
    finally:
        await connection.close()
    if not services:
        await message.answer("لا توجد خدمات متاحة حاليًا.")
        return
    buttons = [[InlineKeyboardButton(
        text=f"{service.name_ar[:32]} · {service.price_halalas / 100:.2f} ر.س",
        callback_data=f"catalog:select:{service.id}",
    )] for service in services]
    await message.answer("اختر الخدمة أو اكتب طلبك مباشرة:",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@dispatcher.callback_query(F.data.startswith("catalog:select:"))
async def select_service(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message) or callback.message.chat.type != "private":
        await callback.answer()
        return
    try:
        service_id = UUID(callback.data.removeprefix("catalog:select:"))
    except (ValueError, AttributeError):
        await callback.answer("اختيار غير صالح.", show_alert=True)
        return
    settings = get_settings()
    if not settings.telegram_orders_enabled:
        await callback.answer("الخدمات قيد التجهيز.", show_alert=True)
        return
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        matching = await available_services(connection, service_id=service_id)
    finally:
        await connection.close()
    if not matching:
        await callback.answer("الخدمة لم تعد متاحة.", show_alert=True)
        return
    await callback.answer()
    if matching[0].slug == "merge-pdf":
        await pdf_workflow.begin(callback.message, callback.from_user.id)


@dispatcher.message(F.text)
async def text_message(message: Message) -> None:
    if message.chat.type != "private" or message.from_user is None:
        return
    content = message.text.strip().lower()
    if content in {"✨ الخدمات", "🧰 الأدوات"}:
        await show_catalog(message)
    elif content == "🔗 دمج pdf" or ("pdf" in content and any(
        term in content for term in ("ادمج", "دمج", "merge")
    )):
        await pdf_workflow.begin(message)
    elif content == "✅ مراجعة السعر":
        await pdf_workflow.review(message)
    elif content in {"إلغاء", "إلغاء الطلب"}:
        await pdf_workflow.cancel(message)
    elif content == "💰 رصيدي":
        connection = await asyncpg.connect(get_settings().database_url.replace("+asyncpg", ""))
        try:
            user_id = await ensure_telegram_user(connection, message.from_user.id)
            current = await balance(connection, user_id)
            await message.answer(
                f"رصيدك المتاح: {current.available_halalas / 100:.2f} ر.س\n"
                f"المبلغ المحجوز: {current.reserved_halalas / 100:.2f} ر.س"
            )
        finally:
            await connection.close()
    elif content == "🛒 المتجر الرقمي":
        await message.answer("رابط المتجر الرقمي سيتوفر قريبًا.")
    else:
        await message.answer("الخدمات قيد التجهيز. يمكنك تجربة «🔗 دمج PDF» عند تفعيلها.")


async def heartbeat() -> None:
    while True:
        await asyncio.to_thread(Path("/tmp/bot-heartbeat").write_text, "ready", encoding="ascii")
        await asyncio.sleep(15)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required for the telegram profile")
    bot = Bot(token=settings.telegram_bot_token)
    await bot.get_me()
    task = asyncio.create_task(heartbeat())
    try:
        logger.info("telegram_polling_started")
        await dispatcher.start_polling(bot)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        with suppress(FileNotFoundError):
            os.unlink("/tmp/bot-heartbeat")
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
