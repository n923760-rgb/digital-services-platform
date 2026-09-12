"""Custom request submission is durable, idempotent and visible only to admins."""

import asyncio
import os
from uuid import uuid4

import asyncpg
import httpx
import pytest
from platform_core.admin_auth import authenticate, create_admin, create_session
from platform_core.custom_requests import (
    begin_request,
    cancel_draft,
    draft_user_id,
    submit_request,
    submitted_telegram_request,
)
from platform_core.orders import ensure_telegram_user

from apps.api.admin import COOKIE_NAME
from apps.api.main import app


@pytest.fixture
async def db():
    connection = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    try:
        yield connection
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_draft_resume_submit_once_cancel_and_reopen(db):
    telegram_id = uuid4().int % (2**63 - 1) + 1
    user_id = await ensure_telegram_user(db, telegram_id)
    draft = await begin_request(db, user_id)
    assert await begin_request(db, user_id) == draft
    assert await draft_user_id(db, telegram_id) == user_id
    with pytest.raises(ValueError, match="description"):
        await submit_request(db, user_id, "101", "قصير")
    assert await draft_user_id(db, telegram_id) == user_id
    request_id = await submit_request(db, user_id, "101", "أحتاج تعديل سيرة ذاتية باللغة الإنجليزية")
    assert request_id == draft
    assert await submit_request(db, user_id, "101",
                                "أحتاج تعديل سيرة ذاتية باللغة الإنجليزية") == request_id
    assert await draft_user_id(db, telegram_id) is None
    assert await submitted_telegram_request(db, telegram_id, 101) == request_id
    assert await submitted_telegram_request(db, telegram_id + 1, 101) is None
    assert not await cancel_draft(db, telegram_id)
    reopened = await begin_request(db, user_id)
    assert reopened != request_id
    assert await cancel_draft(db, telegram_id)
    assert await draft_user_id(db, telegram_id) is None
    assert await db.fetchval("SELECT count(*) FROM custom_service_requests WHERE status='NEW'") >= 1
    assert await db.fetchval("SELECT count(*) FROM orders WHERE user_id=$1", user_id) == 0
    assert await db.fetchval("SELECT count(*) FROM wallet_transactions WHERE wallet_user_id=$1",
                             user_id) == 0


@pytest.mark.asyncio
async def test_concurrent_duplicate_message_returns_one_request(db):
    telegram_id = uuid4().int % (2**63 - 1) + 1
    user_id = await ensure_telegram_user(db, telegram_id)
    await begin_request(db, user_id)
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "")

    async def submit():
        connection = await asyncpg.connect(url)
        try:
            return await submit_request(connection, user_id, "201", "أحتاج تصميم دعوة مناسبة باللغة العربية")
        finally:
            await connection.close()

    first, second = await asyncio.gather(submit(), submit())
    assert first == second
    assert await db.fetchval("""SELECT count(*) FROM custom_service_requests
      WHERE user_id=$1 AND status='NEW'""", user_id) == 1


@pytest.mark.asyncio
async def test_review_queue_requires_admin_session(db):
    telegram_id = uuid4().int % (2**63 - 1) + 1
    user_id = await ensure_telegram_user(db, telegram_id)
    await begin_request(db, user_id)
    description = "أريد خدمة كتابة خطاب رسمي بالعربية"
    request_id = await submit_request(db, user_id, "301", description)
    password = "secure admin password for request review"
    name = "operator-" + uuid4().hex
    await create_admin(db, name, password, role_code="OPERATOR")
    token = await create_session(db, await authenticate(db, name, password))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as client:
        assert (await client.get("/api/admin/custom-requests")).status_code == 401
        client.cookies.set(COOKIE_NAME, token)
        response = await client.get("/api/admin/custom-requests")
        assert response.status_code == 200
        own = next(item for item in response.json() if item["id"] == str(request_id))
        assert own["description"] == description
        assert own["telegram_user_id"] == telegram_id
        assert (await client.get("/api/admin/overview")).json()["new_custom_requests"] >= 1
