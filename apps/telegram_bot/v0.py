"""Minimal first-channel entrypoint: direct text summaries, no Redis/ARQ or storage runtime."""

import asyncio
import logging
import os
from contextlib import suppress
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, ErrorEvent, Message
from platform_core.config import get_settings
from platform_core.logging import configure_logging
from platform_core.summary_orders import (
    purge_expired_summary_text,
    recover_interrupted_summaries,
    require_no_legacy_work,
)
from platform_core.telegram_workflow import cancel_active
from platform_core.text_summary import SLUG

from apps.telegram_bot import customer_status, stars_payments, summary_ui

logger = logging.getLogger(__name__)
dispatcher = Dispatcher()


def private(message):
    return message.chat.type == "private" and message.from_user is not None and not message.from_user.is_bot


@dispatcher.message(CommandStart())
@dispatcher.message(Command("summary"))
async def start(message: Message, bot: Bot):
    if private(message):
        await summary_ui.billing(bot, message.from_user.id)
        await message.answer(
            "خدمة تلخيص النص: أرسل نصًا من 20 إلى 4,000 حرف.\n"
            "الملخص محلي ويختار جملًا من النص؛ ليس ذكاء اصطناعيًا توليديًا.\n"
            "ستراجع السعر والشروط قبل الدفع بالنجوم. /orders للمتابعة، /cancel للإلغاء."
        )


@dispatcher.callback_query(F.data.startswith("stars:confirm:"))
async def invoice(callback: CallbackQuery, bot: Bot):
    await stars_payments.invoice(callback, bot, service_slug=SLUG)


@dispatcher.pre_checkout_query()
async def precheckout(query):
    await stars_payments.precheckout(query, service_slug=SLUG)


@dispatcher.message(F.successful_payment | F.refunded_payment)
async def receipt(message: Message, bot: Bot):
    if private(message) or message.chat.type == "private" and message.refunded_payment:
        await summary_ui.billing(bot, message.chat.id)
        await message.answer("وصل تحديث الدفع. /orders للحالة و/paysupport للمساعدة.")


@dispatcher.message(Command("terms"))
async def terms(message: Message):
    if private(message):
        await message.answer(get_settings().telegram_payment_terms.strip() or "شروط الشراء قيد التجهيز؛ الدفع غير متاح.")


@dispatcher.message(Command("paysupport"))
async def support(message: Message):
    if private(message):
        await message.answer(get_settings().telegram_payment_support.strip() or "دعم الدفع قيد التجهيز؛ الدفع غير متاح.")


@dispatcher.message(Command("orders"))
async def orders(message: Message, bot: Bot):
    if private(message):
        await summary_ui.billing(bot, message.from_user.id)
        await customer_status.show_requests(message)


@dispatcher.message(Command("cancel"))
async def cancel(message: Message):
    if private(message):
        connection = await summary_ui.connect()
        try:
            user_id = await connection.fetchval("SELECT id FROM users WHERE telegram_user_id=$1", message.from_user.id)
            changed = await cancel_active(connection, user_id) if user_id else False
        finally:
            await connection.close()
        await message.answer("ألغي العرض غير المدفوع." if changed else "لا يوجد عرض غير مدفوع للإلغاء.")


@dispatcher.message(F.text)
async def text(message: Message):
    if private(message):
        if message.text.startswith("/"):
            logger.info("summary_command_rejected")
            await message.answer("الأوامر: /summary /orders /cancel /terms /paysupport")
        else:
            await summary_ui.quote(message)


@dispatcher.message()
async def unsupported(message: Message):
    if private(message):
        logger.info("summary_media_rejected")
        await message.answer("هذه الخدمة تقبل نصًا فقط؛ الملفات والصور والتسجيلات غير مدعومة.")


@dispatcher.errors()
async def errors(event: ErrorEvent, bot: Bot):
    logger.error("summary_handler_failed:%s", type(event.exception).__name__)
    # Financial receipts remain persisted; do not log exception bodies or customer text.
    if event.update.message and event.update.message.chat.type == "private":
        try:
            await bot.send_message(event.update.message.chat.id, "تعذر إكمال العملية. تابع /orders أو /paysupport؛ لا تدفع مرة أخرى لهذا الطلب.")
        except TelegramAPIError:
            logger.warning("summary_error_notice_unavailable")
    return True


async def heartbeat():
    while True:
        await asyncio.to_thread(Path("/tmp/bot-heartbeat").write_text, "ready", encoding="ascii")
        await asyncio.sleep(15)


async def main():
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    connection = await summary_ui.connect()
    try:
        await require_no_legacy_work(connection)
        await purge_expired_summary_text(connection)
        await recover_interrupted_summaries(connection)
    finally:
        await connection.close()
    bot = Bot(token=settings.telegram_bot_token)
    task = None
    try:
        await bot.get_me()
        await summary_ui.billing(bot)
        task = asyncio.create_task(heartbeat())
        logger.info("summary_polling_started")
        await stars_payments.poll_updates(bot, dispatcher)
    finally:
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        with suppress(FileNotFoundError):
            os.unlink("/tmp/bot-heartbeat")
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
