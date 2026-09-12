"""A menu callback must use the customer's ID, never the bot's message author."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from aiogram.types import CallbackQuery, Chat, Message, User
from platform_core.service_catalog import CatalogService

from apps.telegram_bot import main as telegram_main


@pytest.mark.asyncio
async def test_selection_uses_callback_sender_and_rechecks_service(monkeypatch):
    service_id = uuid4()
    message = Message(message_id=8, date=datetime.now(UTC),
                      chat=Chat(id=42, type="private"),
                      from_user=User(id=999, is_bot=True, first_name="Bot"), text="الخدمات")
    callback = CallbackQuery(id="callback-1", chat_instance="chat-1",
                             from_user=User(id=42, is_bot=False, first_name="Customer"),
                             message=message, data=f"catalog:select:{service_id}")
    connection = SimpleNamespace(close=AsyncMock())
    connect = AsyncMock(return_value=connection)
    listing = AsyncMock(return_value=[CatalogService(service_id, "merge-pdf", "دمج PDF", "أدوات", 700)])
    begin = AsyncMock()
    answer = AsyncMock()
    monkeypatch.setattr(telegram_main, "get_settings", lambda: SimpleNamespace(
        telegram_orders_enabled=True, database_url="postgresql+asyncpg://test"))
    monkeypatch.setattr(telegram_main.asyncpg, "connect", connect)
    monkeypatch.setattr(telegram_main, "available_services", listing)
    monkeypatch.setattr(telegram_main.pdf_workflow, "begin", begin)
    monkeypatch.setattr(CallbackQuery, "answer", answer)

    await telegram_main.select_service(callback)
    listing.assert_awaited_once_with(connection, service_id=service_id)
    begin.assert_awaited_once_with(message, 42)
    answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_catalog_stays_closed_without_telegram_order_flag(monkeypatch):
    message = Message(message_id=9, date=datetime.now(UTC),
                      chat=Chat(id=42, type="private"),
                      from_user=User(id=42, is_bot=False, first_name="Customer"),
                      text="✨ الخدمات")
    answer = AsyncMock()
    connect = AsyncMock()
    monkeypatch.setattr(telegram_main, "get_settings", lambda: SimpleNamespace(
        telegram_orders_enabled=False))
    monkeypatch.setattr(telegram_main.asyncpg, "connect", connect)
    monkeypatch.setattr(Message, "answer", answer)

    await telegram_main.show_catalog(message)
    connect.assert_not_awaited()
    assert "قيد التجهيز" in answer.await_args.args[0]
