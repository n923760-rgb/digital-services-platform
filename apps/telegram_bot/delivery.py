"""Telegram delivery adapter: channel-specific transport stays outside the domain."""

import asyncpg
from aiogram.types import BufferedInputFile
from platform_core.delivery import DeliveryClaim
from platform_core.files import Storage, read_file


async def send_result(
    bot, connection: asyncpg.Connection, storage: Storage, bucket: str,
    claim: DeliveryClaim,
) -> str:
    if claim.telegram_user_id is None:
        raise ValueError("customer has no Telegram recipient")
    data = await read_file(
        connection, storage, bucket, claim.user_id, claim.result_file_id,
    )
    message = await bot.send_document(
        chat_id=claim.telegram_user_id,
        document=BufferedInputFile(data, filename="merged.pdf"),
        caption="تم تجهيز ملفك ✅",
    )
    return f"telegram:{claim.telegram_user_id}:{message.message_id}"
