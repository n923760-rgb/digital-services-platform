"""Telegram adapter for durable custom request intake; no payment side effects."""

import asyncpg
from aiogram.types import Message
from platform_core.config import get_settings
from platform_core.custom_requests import (
    begin_request,
    cancel_draft,
    draft_user_id,
    submit_request,
    submitted_telegram_request,
)
from platform_core.orders import ensure_telegram_user


async def begin(message: Message) -> None:
    connection = await asyncpg.connect(get_settings().database_url.replace("+asyncpg", ""))
    try:
        user_id = await ensure_telegram_user(connection, message.from_user.id)
        await begin_request(connection, user_id)
    finally:
        await connection.close()
    await message.answer("اكتب وصف الخدمة التي تحتاجها في رسالة واحدة (10 إلى 2000 حرف). "
                         "هذا طلب للمراجعة فقط، وليس تنفيذًا أو عرض سعر؛ لن يُخصم منك شيء الآن. "
                         "المرفقات والصوت والصور غير مدعومة. "
                         "للخروج اكتب «إلغاء».")


async def submit_if_collecting(message: Message) -> bool:
    connection = await asyncpg.connect(get_settings().database_url.replace("+asyncpg", ""))
    try:
        user_id = await draft_user_id(connection, message.from_user.id)
        if user_id is None:
            request_id = await submitted_telegram_request(connection, message.from_user.id,
                                                           message.message_id)
            if request_id is None:
                return False
        else:
            try:
                request_id = await submit_request(connection, user_id, str(message.message_id),
                                                  message.text)
            except ValueError:
                await message.answer("اكتب وصفًا بين 10 و2000 حرف في رسالة واحدة، أو اكتب «إلغاء».")
                return True
    finally:
        await connection.close()
    await message.answer(f"وصل طلبك للمراجعة ✅ رقم الطلب: {request_id}\n"
                         "هذا طلب مراجعة فقط؛ لم يبدأ التنفيذ ولم يُخصم مبلغ. "
                         "تابع الحالة عبر «📋 طلباتي»؛ لا توجد إشعارات تلقائية لقرار المراجعة حاليًا.")
    return True


async def cancel_if_collecting(message: Message) -> bool:
    connection = await asyncpg.connect(get_settings().database_url.replace("+asyncpg", ""))
    try:
        cancelled = await cancel_draft(connection, message.from_user.id)
    finally:
        await connection.close()
    if cancelled:
        await message.answer("تم إلغاء وصف الخدمة غير المرسل.")
    return cancelled
