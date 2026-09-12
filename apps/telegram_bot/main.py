import asyncio
import logging
import os
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from platform_core.config import get_settings
from platform_core.logging import configure_logging

logger = logging.getLogger(__name__)
dispatcher = Dispatcher()


@dispatcher.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "أهلًا 👋\nوش تحتاج أسوي لك؟\n"
        "الخدمات قيد التجهيز حاليًا؛ راح نفتح الطلبات بعد اكتمال المحفظة والتنفيذ."
    )


async def heartbeat() -> None:
    while True:
        with open("/tmp/bot-heartbeat", "w", encoding="ascii") as marker:
            marker.write("ready")
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
