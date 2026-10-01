"""Customer-owned status and text-only intake, using disposable PostgreSQL."""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import pytest
from platform_core.admin_auth import create_admin
from platform_core.custom_requests import begin_request, draft_user_id, submit_request, triage_request
from platform_core.customer_status import recent_telegram_requests
from platform_core.orders import confirm_order, ensure_telegram_user

from apps.telegram_bot import customer_status, main


@pytest.fixture
async def db():
    connection = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    try:
        yield connection
    finally:
        await connection.close()


async def customer(db):
    telegram_id = uuid4().int % (2**63 - 1) + 1
    return telegram_id, await ensure_telegram_user(db, telegram_id)


async def review(db, user_id, key, *, channel="telegram"):
    await begin_request(db, user_id, channel=channel)
    return await submit_request(db, user_id, key, "أحتاج وصف خدمة للمراجعة فقط", channel=channel)


def message(telegram_id, *, chat_type="private", text=None):
    return SimpleNamespace(
        chat=SimpleNamespace(type=chat_type), from_user=SimpleNamespace(id=telegram_id),
        text=text, answer=AsyncMock(),
    )


def configure_connections(monkeypatch):
    original = asyncpg.connect
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "")

    async def connect(_url):
        return await original(url)

    monkeypatch.setattr(asyncpg, "connect", connect)


@pytest.mark.asyncio
async def test_status_is_owned_channel_scoped_and_excludes_drafts(db):
    telegram_id, user_id = await customer(db)
    foreign_id, foreign_user = await customer(db)
    own = await review(db, user_id, "101")
    await review(db, foreign_user, "101")
    await review(db, user_id, "201", channel="web")
    await begin_request(db, user_id)
    category_id, service_id = uuid4(), uuid4()
    await db.execute(
        "INSERT INTO service_categories (id,slug,name_ar) VALUES ($1,$2,'اختبار')",
        category_id, str(category_id),
    )
    await db.execute(
        """INSERT INTO services
           (id,category_id,slug,name_ar,processor_type,base_price_halalas,input_schema,enabled)
           VALUES ($1,$2,$3,'اختبار','tool',0,'{"min_files":0,"max_files":0}',true)""",
        service_id, category_id, str(service_id),
    )
    own_order = await confirm_order(db, user_id, service_id, "own-order")
    await confirm_order(db, foreign_user, service_id, "foreign-order")
    await confirm_order(db, user_id, service_id, "web-order", channel="web")
    records = await recent_telegram_requests(db, telegram_id)
    assert {row["id"] for row in records} == {own, own_order}
    assert {row["kind"] for row in records} == {"review", "order"}
    assert len(await recent_telegram_requests(db, foreign_id)) == 2
    assert await recent_telegram_requests(db, uuid4().int % (2**63 - 1) + 1) == []


@pytest.mark.asyncio
async def test_status_limit_and_private_triage_reason(db, monkeypatch):
    telegram_id, user_id = await customer(db)
    ids = [await review(db, user_id, str(index)) for index in range(11)]
    reason = "سبب داخلي لا يعرض على العميل"
    owner = await create_admin(
        db, "owner-" + uuid4().hex, "status test owner password", role_code="OWNER",
    )
    await triage_request(
        db, ids[-1], owner, expected_revision=1, action="START_REVIEW",
        reason="مراجعة نطاق طلب الخدمة المرسل",
    )
    await triage_request(
        db, ids[-1], owner, expected_revision=2, action="DECLINE", reason=reason,
    )
    records = await recent_telegram_requests(db, telegram_id)
    assert len(records) == 10 and records[0]["id"] == ids[-1]
    assert all(set(row) == {"id", "kind", "status", "created_at"} for row in records)
    configure_connections(monkeypatch)
    incoming = message(telegram_id)
    await customer_status.show_requests(incoming)
    output = incoming.answer.await_args.args[0]
    assert "تعذر قبول طلب الخدمة" in output and reason not in output
    assert str(ids[0]) not in output
    assert await db.fetchval(
        "SELECT count(*) FROM wallet_transactions WHERE wallet_user_id=$1", user_id,
    ) == 0
    with pytest.raises(ValueError):
        await recent_telegram_requests(db, telegram_id, limit=11)


@pytest.mark.asyncio
async def test_document_does_not_upload_or_consume_text_draft(db, monkeypatch):
    telegram_id, user_id = await customer(db)
    await begin_request(db, user_id)
    configure_connections(monkeypatch)
    upload = AsyncMock()
    monkeypatch.setattr(main.pdf_workflow, "upload", upload)
    incoming = message(telegram_id)
    await main.document_message(incoming, SimpleNamespace())
    upload.assert_not_awaited()
    assert "وصفًا نصيًا فقط" in incoming.answer.await_args.args[0]
    assert await draft_user_id(db, telegram_id) == user_id
    assert await db.fetchval("SELECT count(*) FROM files WHERE owner_user_id=$1", user_id) == 0


@pytest.mark.asyncio
async def test_unsupported_media_preserves_draft_and_groups_are_ignored(db):
    telegram_id, user_id = await customer(db)
    await begin_request(db, user_id)
    incoming = message(telegram_id)
    await main.unsupported_message(incoming)
    assert "غير مدعوم" in incoming.answer.await_args.args[0]
    assert await draft_user_id(db, telegram_id) == user_id
    group = message(telegram_id, chat_type="group")
    await main.unsupported_message(group)
    await customer_status.show_requests(group)
    group.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_requests_menu_empty_and_database_error_are_safe(db, monkeypatch):
    telegram_id, _ = await customer(db)
    configure_connections(monkeypatch)
    incoming = message(telegram_id, text="📋 طلباتي")
    await main.text_message(incoming)
    assert "لا توجد طلبات" in incoming.answer.await_args.args[0]

    async def unavailable(_url):
        raise OSError("private internal failure detail")

    monkeypatch.setattr(asyncpg, "connect", unavailable)
    incoming.answer.reset_mock()
    await customer_status.show_requests(incoming)
    assert "مؤقتًا" in incoming.answer.await_args.args[0]
    assert "private internal" not in incoming.answer.await_args.args[0]
