"""Telegram file listing and authorized redelivery of completed results."""

import logging
from uuid import UUID
from zoneinfo import ZoneInfo

import asyncpg
from aiogram import Bot
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from platform_core.config import get_settings
from platform_core.customer_files import completed_result_owner, recent_results
from platform_core.files import FileUnavailable, read_file

from apps.telegram_bot.pdf_workflow import storage_client

logger = logging.getLogger(__name__)


async def show_files(message: Message) -> None:
    settings = get_settings()
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        files = await recent_results(connection, message.from_user.id)
    finally:
        await connection.close()
    if not files:
        await message.answer("ما عندك ملفات مكتملة ومتاحة حاليًا.")
        return
    buttons = [[InlineKeyboardButton(text=file.name[:45], callback_data=f"files:get:{file.id}")]
               for file in files]
    dates = [f"• {file.name[:45]} — حتى {file.retention_until.astimezone(ZoneInfo('Asia/Riyadh')):%Y-%m-%d}"
             for file in files]
    await message.answer("آخر ملفاتك المكتملة (التواريخ بتوقيت السعودية):\n" + "\n".join(dates)
                         + "\nاختر ملفًا لإرساله مجددًا:",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


async def send_file(callback: CallbackQuery, bot: Bot) -> None:
    if (not isinstance(callback.message, Message) or callback.message.chat.type != "private"
            or callback.message.chat.id != callback.from_user.id):
        await callback.answer()
        return
    try:
        file_id = UUID(callback.data.removeprefix("files:get:"))
    except (ValueError, AttributeError):
        await callback.answer("اختيار غير صالح.", show_alert=True)
        return
    await callback.answer()
    settings = get_settings()
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        owner_id = await completed_result_owner(connection, callback.from_user.id, file_id)
        if owner_id is None:
            await callback.message.answer("الملف غير متاح أو انتهت مدة حفظه.")
            return
        data = await read_file(connection, storage_client(), settings.object_storage_bucket,
                               owner_id, file_id)
    except FileUnavailable:
        await callback.message.answer("الملف غير متاح أو انتهت مدة حفظه.")
        return
    except Exception:
        logger.exception("customer_result_retrieval_failed", extra={"file_id": str(file_id)})
        await callback.message.answer("تعذر جلب الملف مؤقتًا. حاول لاحقًا.")
        return
    finally:
        await connection.close()
    try:
        await bot.send_document(chat_id=callback.from_user.id,
                                document=BufferedInputFile(data, filename="merged.pdf"),
                                caption="ملفك المكتمل ✅")
    except Exception:
        logger.exception("customer_result_resend_failed", extra={"file_id": str(file_id)})
        await callback.message.answer("تعذر إرسال الملف مؤقتًا. حاول لاحقًا.")
