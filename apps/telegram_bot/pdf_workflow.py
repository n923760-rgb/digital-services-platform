"""Thin Arabic Telegram adapter for the data-driven PDF merge workflow."""

import logging
from io import BytesIO
from uuid import UUID

import asyncpg
import boto3
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from platform_core.config import get_settings
from platform_core.files import InvalidFile, upload_file
from platform_core.ledger import IdempotencyConflict, InsufficientFunds
from platform_core.orders import ensure_telegram_user
from platform_core.storage_s3 import S3Storage
from platform_core.telegram_uploads import (
    UPLOAD_INTENT_SECONDS,
    UploadBusy,
    UploadRejected,
    admit_pdf_upload,
    discard_unattached_input,
    finish_pdf_upload,
    upload_lock,
)
from platform_core.telegram_workflow import (
    StaleQuote,
    cancel_active,
    confirm_pdf_merge,
    has_upload,
    quote_pdf_merge,
    start_pdf_merge,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class BoundedBuffer(BytesIO):
    def __init__(self, limit: int):
        super().__init__()
        self.limit = limit

    def write(self, data: bytes) -> int:
        if self.tell() + len(data) > self.limit:
            raise InvalidFile("Telegram document exceeds the upload limit")
        return super().write(data)


def storage_client() -> S3Storage:
    return S3Storage(boto3.client(
        "s3", endpoint_url=settings.object_storage_endpoint,
        aws_access_key_id=settings.object_storage_access_key,
        aws_secret_access_key=settings.object_storage_secret_key,
        region_name=settings.object_storage_region,
    ))


def quote_keyboard(workflow_id: UUID, quote_revision: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ تأكيد الطلب",
            callback_data=f"merge:confirm:{workflow_id.hex}:{quote_revision}",
        ),
    ]])


async def begin(message: Message, telegram_user_id: int | None = None) -> None:
    if not settings.telegram_orders_enabled:
        await message.answer("الخدمة قيد التجهيز حاليًا.")
        return
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        user_id = await ensure_telegram_user(
            connection, telegram_user_id if telegram_user_id is not None else message.from_user.id,
        )
        workflow = await start_pdf_merge(connection, user_id)
        if workflow.status == "CONFIRMING":
            await show_quote(message, connection, user_id)
        else:
            await message.answer(
                f"أرسل ملفات PDF بالترتيب المطلوب (من 2 إلى 10). وصلت {workflow.file_count} ملفات. "
                "بعدها اضغط «✅ مراجعة السعر»."
            )
    except ValueError:
        await message.answer("خدمة دمج PDF غير متاحة الآن.")
    finally:
        await connection.close()


async def show_quote(message: Message, connection: asyncpg.Connection, user_id: UUID) -> None:
    try:
        workflow = await quote_pdf_merge(connection, user_id)
    except ValueError:
        await message.answer("أرسل ملفين PDF على الأقل قبل مراجعة السعر.")
        return
    price = f"{workflow.quoted_price_halalas / 100:.2f} ر.س"
    await message.answer(
        f"دمج {workflow.file_count} ملفات PDF. السعر: {price}. تؤكد الطلب؟",
        reply_markup=quote_keyboard(workflow.id, workflow.quote_revision),
    )


async def review(message: Message) -> None:
    if not settings.telegram_orders_enabled:
        await message.answer("الخدمة قيد التجهيز حاليًا.")
        return
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        user_id = await ensure_telegram_user(connection, message.from_user.id)
        await show_quote(message, connection, user_id)
    finally:
        await connection.close()


async def upload(message: Message, bot: Bot) -> None:
    if not settings.telegram_orders_enabled:
        await message.answer("رفع الملفات غير متاح حاليًا.")
        return
    document = message.document
    if not document or document.file_size is None or document.file_size > settings.max_upload_bytes:
        await message.answer("الملف كبير أو غير صالح. أرسل PDF أصغر من الحد المسموح.")
        return
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        user_id = await ensure_telegram_user(connection, message.from_user.id)
        async with upload_lock(connection, user_id):
            if await has_upload(connection, user_id, message.message_id):
                await message.answer("الملف مضاف مسبقًا ✅")
                return
            admission = await admit_pdf_upload(
                connection, user_id, document.file_size,
                max_upload_bytes=settings.max_upload_bytes,
                max_user_upload_bytes=settings.max_user_upload_bytes,
            )
            data_buffer = BoundedBuffer(admission.byte_limit)
            await bot.download(document, destination=data_buffer)
            storage = storage_client()
            record = await upload_file(
                connection, storage, settings.object_storage_bucket, user_id,
                document.file_name or "", document.mime_type or "", data_buffer.getvalue(),
                limit=admission.byte_limit, retention_days=settings.file_retention_days,
                intent_retention_seconds=UPLOAD_INTENT_SECONDS,
            )
            try:
                workflow = await finish_pdf_upload(
                    connection, user_id, record.id, message.message_id, admission,
                    retention_days=settings.file_retention_days,
                )
            except BaseException:
                # Also clean up cancellation, then re-raise it rather than swallowing it.
                try:
                    await discard_unattached_input(
                        connection, storage, settings.object_storage_bucket, user_id, record.id,
                    )
                except Exception:
                    logger.exception("unattached_upload_cleanup_failed",
                                     extra={"file_id": str(record.id)})
                raise
            await message.answer(
                f"وصل الملف {workflow.file_count} ✅ أرسل الباقي، أو اضغط «✅ مراجعة السعر»."
            )
    except UploadBusy:
        await message.answer("جارٍ رفع ملفك السابق. انتظر وصول التأكيد ثم أرسل الملف التالي.")
    except UploadRejected:
        await message.answer(
            "تعذر قبول الملف: تحقق من الطلب النشط وحدّ عدد الملفات والحجم والمساحة المتاحة."
        )
    except InvalidFile:
        await message.answer("الملف غير صالح. أرسل PDF صحيحًا وبالحجم المسموح.")
    except ValueError:
        await message.answer("تعذر إضافة الملف إلى الطلب. راجع عدد الملفات أو ابدأ طلبًا جديدًا.")
    except Exception:
        logger.exception("telegram_upload_failed", extra={"telegram_user_id": message.from_user.id})
        await message.answer("تعذر حفظ الملف مؤقتًا. حاول مرة أخرى.")
    finally:
        await connection.close()


async def confirm(
    message: Message, workflow_id: UUID, telegram_user_id: int, quote_revision: int,
) -> None:
    if not settings.telegram_orders_enabled:
        await message.answer("الطلبات غير متاحة حاليًا.")
        return
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        user_id = await ensure_telegram_user(connection, telegram_user_id)
        order_id = await confirm_pdf_merge(
            connection, user_id, workflow_id, expected_quote_revision=quote_revision,
        )
        await message.answer(f"تم تسجيل طلبك ✅ رقم الطلب: {order_id}")
    except InsufficientFunds:
        await message.answer("رصيدك غير كافٍ. لم يُنشأ الطلب ولم يُخصم أي مبلغ.")
    except IdempotencyConflict:
        await message.answer("هذا التأكيد يخص طلبًا مختلفًا. افتح طلبًا جديدًا.")
    except StaleQuote:
        await message.answer("هذا التأكيد يخص عرضًا قديمًا. راجع العرض الحالي وأكد من زره الجديد.")
        await show_quote(message, connection, user_id)
    except ValueError as exc:
        if "price changed" in str(exc):
            await message.answer("تغير السعر. راجع السعر الجديد وأكد مرة أخرى.")
            await show_quote(message, connection, user_id)
        else:
            await message.answer("انتهى هذا التأكيد أو تغيرت الملفات. راجع طلبك مجددًا.")
    finally:
        await connection.close()


async def cancel(message: Message) -> None:
    if not settings.telegram_orders_enabled:
        await message.answer("لا يوجد طلب نشط.")
        return
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        user_id = await ensure_telegram_user(connection, message.from_user.id)
        cancelled = await cancel_active(connection, user_id)
        await message.answer("تم إلغاء الطلب الحالي." if cancelled else "لا يوجد طلب نشط.")
    finally:
        await connection.close()
