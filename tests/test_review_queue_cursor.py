"""Authenticated review pagination reaches old items without shifting offsets."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import httpx
import pytest
from platform_core.admin_auth import authenticate, create_admin, create_session
from platform_core.orders import ensure_telegram_user

from apps.api.admin import COOKIE_NAME
from apps.api.main import app


@pytest.mark.asyncio
async def test_review_cursor_ties_new_insert_and_terminal_exclusion():
    db = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    try:
        telegram_id = uuid4().int % (2**63 - 1) + 1
        user_id = await ensure_telegram_user(db, telegram_id)
        timestamp = datetime(2099, 1, 1, tzinfo=UTC)
        ids = sorted([uuid4() for _ in range(55)], reverse=True)
        await db.executemany(
            """INSERT INTO custom_service_requests
              (id,user_id,channel,status,description,source_message_key,created_at,updated_at)
              VALUES ($1,$2,'telegram','NEW','وصف تجريبي لطلب خدمة للمراجعة',$3,$4,$4)""",
            [(item, user_id, str(item), timestamp) for item in ids],
        )
        for status in ("CANCELLED", "COLLECTING"):
            await db.execute(
                """INSERT INTO custom_service_requests (id,user_id,channel,status,updated_at)
                  VALUES ($1,$2,'telegram',$3,$4)""", uuid4(), user_id, status, timestamp,
            )
        name, password = "operator-" + uuid4().hex, "synthetic pagination password"
        await create_admin(db, name, password, role_code="OPERATOR")
        token = await create_session(db, await authenticate(db, name, password))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://test",
        ) as client:
            assert (await client.get("/api/admin/custom-requests")).status_code == 401
            client.cookies.set(COOKIE_NAME, token)
            first = await client.get("/api/admin/custom-requests")
            assert first.status_code == 200
            page = first.json()
            assert [item["id"] for item in page] == [str(item) for item in ids[:50]]
            boundary = page[-1]
            newer = uuid4()
            await db.execute(
                """INSERT INTO custom_service_requests
                  (id,user_id,channel,status,description,source_message_key,updated_at)
                  VALUES ($1,$2,'telegram','NEW','طلب أحدث أثناء التنقل في الصفحات',$3,$4)""",
                newer, user_id, str(newer), datetime(2100, 1, 1, tzinfo=UTC),
            )
            params = {"before_updated_at": boundary["updated_at"], "before_id": boundary["id"]}
            older = await client.get("/api/admin/custom-requests", params=params)
            assert older.status_code == 200
            remaining = [item["id"] for item in older.json() if item["telegram_user_id"] ==
                         telegram_id]
            assert remaining == [str(item) for item in ids[50:]]
            assert str(newer) not in {item["id"] for item in older.json()}
            assert not {item["id"] for item in older.json()} & {item["id"] for item in page}
            for invalid in (
                {"before_id": boundary["id"]},
                {"before_updated_at": boundary["updated_at"]},
                {"before_updated_at": "invalid", "before_id": boundary["id"]},
                {"before_updated_at": "2099-01-01T00:00:00", "before_id": boundary["id"]},
                {"before_updated_at": boundary["updated_at"], "before_id": "invalid"},
            ):
                assert (await client.get("/api/admin/custom-requests", params=invalid)).status_code == 422
            client.cookies.clear()
            assert (await client.get("/api/admin/custom-requests", params=params)).status_code == 401
    finally:
        if "user_id" in locals():
            await db.execute("DELETE FROM custom_service_requests WHERE user_id=$1", user_id)
        await db.close()
