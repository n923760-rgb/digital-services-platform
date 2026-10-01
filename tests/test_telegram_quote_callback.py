"""Quote callback identity, legacy rejection and Telegram payload boundaries."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from aiogram.types import CallbackQuery, Chat, Message, User

from apps.telegram_bot import main as telegram_main
from apps.telegram_bot.pdf_workflow import quote_keyboard


def test_quote_button_fits_telegram_limit_and_identifies_the_offer():
    workflow_id = uuid4()
    first = quote_keyboard(workflow_id, 1).inline_keyboard[0][0].callback_data
    latest = quote_keyboard(workflow_id, 2**31 - 1).inline_keyboard[0][0].callback_data
    assert first != latest
    assert len(latest.encode("utf-8")) <= 64
    assert first == f"merge:confirm:{workflow_id.hex}:1"


@pytest.mark.asyncio
async def test_quote_callback_uses_customer_and_displayed_revision(monkeypatch):
    workflow_id = uuid4()
    message = Message(
        message_id=80, date=datetime.now(UTC), chat=Chat(id=42, type="private"),
        from_user=User(id=999, is_bot=True, first_name="Bot"), text="عرض السعر",
    )
    callback = CallbackQuery(
        id="quote-1", chat_instance="private-chat",
        from_user=User(id=42, is_bot=False, first_name="Customer"), message=message,
        data=f"merge:confirm:{workflow_id.hex}:7",
    )
    confirm = AsyncMock()
    answer = AsyncMock()
    monkeypatch.setattr(telegram_main.pdf_workflow, "confirm", confirm)
    monkeypatch.setattr(CallbackQuery, "answer", answer)
    await telegram_main.confirm_callback(callback)
    confirm.assert_awaited_once_with(message, workflow_id, 42, 7)
    answer.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["", ":0", ":-1", ":2147483648", ":bad", ":1:extra"])
async def test_legacy_or_invalid_confirmation_never_reaches_orders(monkeypatch, suffix):
    message = Message(
        message_id=81, date=datetime.now(UTC), chat=Chat(id=42, type="private"),
        from_user=User(id=999, is_bot=True, first_name="Bot"), text="عرض قديم",
    )
    callback = CallbackQuery(
        id="quote-invalid", chat_instance="private-chat",
        from_user=User(id=42, is_bot=False, first_name="Customer"), message=message,
        data=f"merge:confirm:{uuid4().hex}{suffix}",
    )
    confirm = AsyncMock()
    answer = AsyncMock()
    monkeypatch.setattr(telegram_main.pdf_workflow, "confirm", confirm)
    monkeypatch.setattr(CallbackQuery, "answer", answer)
    await telegram_main.confirm_callback(callback)
    confirm.assert_not_awaited()
    answer.assert_awaited_once_with("تأكيد غير صالح.", show_alert=True)
