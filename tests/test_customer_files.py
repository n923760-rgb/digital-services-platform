"""Only the owner can view and resend completed, retained PDF results."""

import os
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import pytest
from aiogram.types import CallbackQuery, Chat, Message, User
from platform_core.customer_files import completed_result_owner, recent_results

from apps.telegram_bot import customer_files as telegram_files


@pytest.fixture
async def db():
    connection = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    transaction = connection.transaction()
    await transaction.start()
    try:
        yield connection
    finally:
        await transaction.rollback()
        await connection.close()


@pytest.mark.asyncio
async def test_only_delivered_results_are_visible_and_expiration_is_enforced(db):
    category_id, service_id, user_id, order_id, file_id = (uuid4() for _ in range(5))
    telegram_id = uuid4().int % (2**63 - 1) + 1
    await db.execute("INSERT INTO users (id,telegram_user_id) VALUES ($1,$2)", user_id, telegram_id)
    await db.execute("INSERT INTO service_categories (id,slug,name_ar) VALUES ($1,$2,'أدوات')",
                     category_id, str(category_id))
    await db.execute("""INSERT INTO services
      (id,category_id,slug,name_ar,processor_type,base_price_halalas)
      VALUES ($1,$2,$3,'دمج','tool',700)""", service_id, category_id, str(service_id))
    await db.execute("""INSERT INTO orders
      (id,user_id,service_id,client_request_key,channel,price_snapshot_halalas,status)
      VALUES ($1,$2,$3,$4,'telegram',700,'AWAITING_FULFILLMENT')""",
      order_id, user_id, service_id, str(order_id))
    await db.execute("""INSERT INTO files
      (id,owner_user_id,order_id,storage_key,file_name,mime_type,size_bytes,
       file_type,status,retention_until)
      VALUES ($1,$2,$3,$4,'merged.pdf','application/pdf',9,'OUTPUT','READY',
              now()+interval '2 days')""", file_id, user_id, order_id, str(file_id))

    assert await recent_results(db, telegram_id) == []
    assert await completed_result_owner(db, telegram_id, file_id) is None
    await db.execute("UPDATE orders SET status='COMPLETED' WHERE id=$1", order_id)
    assert [file.id for file in await recent_results(db, telegram_id)] == [file_id]
    assert await completed_result_owner(db, telegram_id, file_id) == user_id
    assert await recent_results(db, telegram_id + 1) == []
    assert await completed_result_owner(db, telegram_id + 1, file_id) is None
    await db.execute("UPDATE files SET retention_until=now()-interval '1 second' WHERE id=$1",
                     file_id)
    assert await recent_results(db, telegram_id) == []
    assert await completed_result_owner(db, telegram_id, file_id) is None


@pytest.mark.asyncio
async def test_resend_uses_callback_customer_and_rechecks_ownership(monkeypatch):
    file_id, user_id = uuid4(), uuid4()
    message = Message(message_id=10, date=datetime.now(UTC),
                      chat=Chat(id=42, type="private"),
                      from_user=User(id=999, is_bot=True, first_name="Bot"), text="ملفاتي")
    callback = CallbackQuery(id="callback-file", chat_instance="chat-file",
                             from_user=User(id=42, is_bot=False, first_name="Customer"),
                             message=message, data=f"files:get:{file_id}")
    connection = SimpleNamespace(close=AsyncMock())
    connect = AsyncMock(return_value=connection)
    owner = AsyncMock(return_value=user_id)
    read = AsyncMock(return_value=b"%PDF-file")
    bot = SimpleNamespace(send_document=AsyncMock())
    answer = AsyncMock()
    monkeypatch.setattr(telegram_files, "get_settings", lambda: SimpleNamespace(
        database_url="postgresql+asyncpg://test", object_storage_bucket="test"))
    monkeypatch.setattr(telegram_files.asyncpg, "connect", connect)
    monkeypatch.setattr(telegram_files, "completed_result_owner", owner)
    monkeypatch.setattr(telegram_files, "read_file", read)
    monkeypatch.setattr(telegram_files, "storage_client", lambda: "storage")
    monkeypatch.setattr(CallbackQuery, "answer", answer)
    monkeypatch.setattr(Message, "answer", AsyncMock())

    await telegram_files.send_file(callback, bot)
    owner.assert_awaited_once_with(connection, 42, file_id)
    read.assert_awaited_once_with(connection, "storage", "test", user_id, file_id)
    assert bot.send_document.await_args.kwargs["chat_id"] == 42
    assert bot.send_document.await_args.kwargs["document"].data == b"%PDF-file"
    owner.reset_mock()
    read.reset_mock()
    bot.send_document.reset_mock()
    owner.return_value = None
    await telegram_files.send_file(callback, bot)
    owner.assert_awaited_once_with(connection, 42, file_id)
    read.assert_not_awaited()
    bot.send_document.assert_not_awaited()
