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
from platform_core.custom_requests import draft_user_id
from platform_core.logging import configure_logging
from platform_core.orders import ensure_telegram_user
from platform_core.service_catalog import available_services
from platform_core.telegram_workflow import active_workflow

from apps.telegram_bot import (
    custom_request_ui,
    customer_files,
    customer_status,
    pdf_workflow,
    stars_payments,
)

logger = logging.getLogger(__name__)
dispatcher = Dispatcher()
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✨ الخدمات"), KeyboardButton(text="🧰 الأدوات")],
        [KeyboardButton(text="➕ اطلب خدمة"), KeyboardButton(text="📋 طلباتي")],
        [KeyboardButton(text="📁 ملفاتي")],
        [KeyboardButton(text="⭐ الدفع والدعم"), KeyboardButton(text="🛒 المتجر الرقمي")],
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



@dispatcher.callback_query(F.data.startswith("stars:confirm:"))
async def stars_invoice(callback: CallbackQuery, bot: Bot) -> None:
    await stars_payments.invoice(callback, bot)


@dispatcher.pre_checkout_query()
async def stars_precheckout(query) -> None:
    await stars_payments.precheckout(query)


@dispatcher.message(F.successful_payment | F.refunded_payment)
async def stars_receipt(message: Message) -> None:
    if message.chat.type == "private":
        await stars_payments.payment_notice(message)


@dispatcher.message(Command("terms"))
async def payment_terms(message: Message) -> None:
    if message.chat.type == "private":
        await message.answer(get_settings().telegram_payment_terms.strip()
                             or "شروط الشراء قيد التجهيز. الدفع غير متاح حاليًا.")


@dispatcher.message(Command("paysupport"))
async def payment_support(message: Message) -> None:
    if message.chat.type == "private":
        await message.answer(get_settings().telegram_payment_support.strip()
                             or "دعم الدفع قيد التجهيز. الدفع غير متاح حاليًا.")


@dispatcher.message(CommandStart())
async def start(message: Message) -> None:
    if message.chat.type != "private" or message.from_user is None:
        return
    await message.answer(
        "أهلًا 👋\nاضغط «➕ اطلب خدمة» ثم اكتب وصفًا نصيًا في رسالة واحدة للمراجعة.\n"
        "الصور والتسجيلات والمرفقات غير مدعومة في طلب المراجعة. "
        "الروابط داخل الوصف تُحفظ كنص ولا تُفتح تلقائيًا.\n"
        + ("لدمج ملفات PDF اختر «🔗 دمج PDF» أولًا.\n"
           if get_settings().telegram_orders_enabled else "الخدمات الجاهزة قيد التجهيز حاليًا.\n")
        + "لمتابعة حالة الطلبات اختر «📋 طلباتي».",
        reply_markup=merge_keyboard if get_settings().telegram_orders_enabled else keyboard,
    )
    settings = get_settings()
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        if await draft_user_id(connection, message.from_user.id):
            await message.answer("عندك طلب خدمة لم ترسل وصفه بعد. اكتب التفاصيل الآن، أو اكتب «إلغاء».")
    finally:
        await connection.close()
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
    if (message.chat.type == "private" and message.from_user
            and not await custom_request_ui.cancel_if_collecting(message)):
        await pdf_workflow.cancel(message)


@dispatcher.message(F.document)
async def document_message(message: Message, bot: Bot) -> None:
    if message.chat.type == "private" and message.from_user:
        connection = await asyncpg.connect(get_settings().database_url.replace("+asyncpg", ""))
        try:
            collecting = await draft_user_id(connection, message.from_user.id)
        finally:
            await connection.close()
        if collecting:
            await message.answer("طلب المراجعة يقبل وصفًا نصيًا فقط. اكتب التفاصيل أو اكتب «إلغاء».")
            return
        await pdf_workflow.upload(message, bot)


@dispatcher.callback_query(F.data.startswith("merge:confirm:"))
async def confirm_callback(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message) or callback.message.chat.type != "private":
        await callback.answer()
        return
    try:
        workflow_key, revision_text = callback.data.removeprefix("merge:confirm:").split(":")
        workflow_id = UUID(workflow_key)
        quote_revision = int(revision_text)
        if not 1 <= quote_revision <= 2**31 - 1:
            raise ValueError("invalid quote revision")
    except (ValueError, AttributeError):
        await callback.answer("تأكيد غير صالح.", show_alert=True)
        return
    await callback.answer()
    await pdf_workflow.confirm(
        callback.message, workflow_id, callback.from_user.id, quote_revision,
    )


async def show_catalog(message: Message) -> None:
    settings = get_settings()
    if not stars_payments.checkout_enabled(settings):
        await message.answer("الخدمات قيد التجهيز حاليًا. اضغط «➕ اطلب خدمة» لإرسال وصف نصي للمراجعة.")
        return
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        services = await available_services(connection, currency="XTR")
    finally:
        await connection.close()
    if not services:
        await message.answer("لا توجد خدمات متاحة حاليًا.")
        return
    buttons = [[InlineKeyboardButton(
        text=f"{service.name_ar[:32]} · {service.price_stars} ⭐",
        callback_data=f"catalog:select:{service.id}",
    )] for service in services]
    await message.answer("اختر الخدمة؛ ولطلب المراجعة استخدم «➕ اطلب خدمة»:",
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
    if not stars_payments.checkout_enabled(settings):
        await callback.answer("الخدمات قيد التجهيز.", show_alert=True)
        return
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        matching = await available_services(connection, service_id=service_id, currency="XTR")
    finally:
        await connection.close()
    if not matching:
        await callback.answer("الخدمة لم تعد متاحة.", show_alert=True)
        return
    await callback.answer()
    if matching[0].slug == "merge-pdf":
        await pdf_workflow.begin(callback.message, callback.from_user.id)


@dispatcher.callback_query(F.data.startswith("files:get:"))
async def file_callback(callback: CallbackQuery, bot: Bot) -> None:
    await customer_files.send_file(callback, bot)


@dispatcher.message(F.text)
async def text_message(message: Message) -> None:
    if message.chat.type != "private" or message.from_user is None:
        return
    content = message.text.strip().lower()
    if content == "➕ اطلب خدمة":
        await custom_request_ui.begin(message)
    elif content in {"إلغاء", "إلغاء الطلب"}:
        if not await custom_request_ui.cancel_if_collecting(message):
            await pdf_workflow.cancel(message)
    elif content in {"✨ الخدمات", "🧰 الأدوات"}:
        await show_catalog(message)
    elif content == "📋 طلباتي":
        await customer_status.show_requests(message)
    elif content == "📁 ملفاتي":
        await customer_files.show_files(message)
    elif content == "✅ مراجعة السعر":
        await pdf_workflow.review(message)
    elif content in {"💰 رصيدي", "⭐ الدفع والدعم"}:
        await message.answer(
            "الدفع بنجوم تلغرام مباشرة لكل طلب؛ لا تحتاج شحن رصيد داخل البوت. "
            "راجع /terms للشروط و/paysupport للمساعدة في الدفع."
        )
    elif content == "🛒 المتجر الرقمي":
        await message.answer("المتجر الرقمي غير مرتبط بهذا البوت حاليًا.")
    elif await custom_request_ui.submit_if_collecting(message):
        return
    elif content == "🔗 دمج pdf" or ("pdf" in content and any(
        term in content for term in ("ادمج", "دمج", "merge")
    )):
        await pdf_workflow.begin(message)
    else:
        await message.answer("الخدمات الجاهزة قيد التجهيز. اضغط «➕ اطلب خدمة» لإرسال طلب للمراجعة.")


@dispatcher.message()
async def unsupported_message(message: Message) -> None:
    if message.chat.type != "private" or message.from_user is None:
        return
    await message.answer(
        "هذا النوع من الرسائل غير مدعوم. لطلب المراجعة اختر «➕ اطلب خدمة» "
        "واكتب وصفًا نصيًا؛ الصور والتسجيلات الصوتية لا تُعالج."
    )


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
        await stars_payments.poll_updates(bot, dispatcher)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        with suppress(FileNotFoundError):
            os.unlink("/tmp/bot-heartbeat")
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
