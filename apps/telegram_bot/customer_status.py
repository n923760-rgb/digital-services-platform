"""Private Arabic status adapter; internal triage reasons are never exposed."""

import logging

import asyncpg
from aiogram.types import Message
from platform_core.config import get_settings
from platform_core.customer_status import recent_telegram_requests

logger = logging.getLogger(__name__)
REVIEW_LABELS = {"NEW": "بانتظار المراجعة", "IN_REVIEW": "قيد المراجعة",
                 "DECLINED": "تعذر قبول طلب الخدمة"}
ORDER_LABELS = {
    "DRAFT": "مسودة", "RESERVED": "بانتظار المعالجة", "QUEUED": "بانتظار المعالجة",
    "PROCESSING": "قيد المعالجة", "AWAITING_FULFILLMENT": "النتيجة جاهزة وبانتظار الإرسال",
    "REFUNDED": "تم رد النجوم عبر تلغرام",
    "COMPLETED": "تم تسليم النتيجة", "FAILED": "تعذر إكمال الطلب", "CANCELLED": "ملغى",
}


PAYMENT_LABELS = {"REFUND_PENDING": "رد النجوم قيد المتابعة",
                  "REFUNDED": "تم رد النجوم عبر تلغرام", "PAID": "وصل الدفع"}


async def show_requests(message: Message) -> None:
    if message.chat.type != "private" or message.from_user is None:
        return
    connection = None
    try:
        connection = await asyncpg.connect(get_settings().database_url.replace("+asyncpg", ""))
        records = await recent_telegram_requests(connection, message.from_user.id)
    except Exception:
        logger.exception("customer_status_unavailable")
        await message.answer("تعذر عرض حالة الطلبات مؤقتًا. حاول مرة أخرى.")
        return
    finally:
        if connection is not None:
            await connection.close()
    if not records:
        await message.answer("لا توجد طلبات مرسلة بعد. اضغط «➕ اطلب خدمة» لكتابة وصف للمراجعة.")
        return
    lines = ["آخر عشرة طلبات مرسلة:"]
    for record in records:
        review = record["kind"] == "review"
        payment = record["kind"] == "payment"
        labels = PAYMENT_LABELS if payment else REVIEW_LABELS if review else ORDER_LABELS
        label = labels.get(record["status"], "الحالة غير متاحة")
        title = "دفعة نجوم" if payment else "طلب مراجعة" if review else "طلب خدمة"
        lines.append(f"{title} {record['id']}\n{label}")
    lines.append("طلبات المراجعة لا تعني بدء التنفيذ أو تحديد سعر. حدّث الحالة باختيار «📋 طلباتي».")
    await message.answer("\n\n".join(lines))
