"""Owner registration stays disabled, audited and safe across duplicate HTTP requests."""

import os
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
from platform_core.admin_auth import authenticate, create_admin, create_session
from platform_core.orders import confirm_order, ensure_telegram_user

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
async def test_service_registration_role_audit_idempotency_and_disabled_default(db):
    password = "category registration password"
    owner_name, operator_name = "owner-" + uuid4().hex, "operator-" + uuid4().hex
    owner_id = await create_admin(db, owner_name, password, role_code="OWNER")
    await create_admin(db, operator_name, password, role_code="OPERATOR")
    owner = await authenticate(db, owner_name, password)
    operator = await authenticate(db, operator_name, password)
    owner_token, operator_token = await create_session(db, owner), await create_session(db, operator)
    category = {"slug": "category-" + uuid4().hex, "name_ar": "تعليم",
                "reason": "Adding an initial category"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as client:
        assert (await client.get("/api/admin/categories")).status_code == 401
        assert (await client.post("/api/admin/categories", json=category,
                                  headers={"Origin": "https://test"})).status_code == 401
        client.cookies.set(COOKIE_NAME, operator_token)
        assert (await client.post("/api/admin/categories", json=category,
                                  headers={"Origin": "https://test"})).status_code == 403
        client.cookies.set(COOKIE_NAME, owner_token)
        assert (await client.post("/api/admin/categories", json=category,
                                  headers={"Origin": "https://evil.test"})).status_code == 403
        created = await client.post("/api/admin/categories", json=category,
                                    headers={"Origin": "https://test"})
        assert created.status_code == 200
        category_id = created.json()["id"]
        again = await client.post("/api/admin/categories", json=category,
                                  headers={"Origin": "https://test"})
        assert again.json()["id"] == category_id
        assert (await client.post("/api/admin/categories", json={**category, "name_ar": "مختلف"},
                                  headers={"Origin": "https://test"})).status_code == 409
        assert any(item["id"] == category_id for item in (await client.get("/api/admin/categories")).json())

        service = {"category_id": category_id, "slug": "service-" + uuid4().hex,
                   "name_ar": "مساعدة تعليمية", "description_ar": "شرح ومراجعة",
                   "processor_type": "ai", "base_price_halalas": 500,
                   "input_schema": {"topic": {"type": "text"}},
                   "reason": "Register disabled service"}
        assert (await client.post("/api/admin/services", json={**service, "enabled": True},
                                  headers={"Origin": "https://test"})).status_code == 422
        assert (await client.post("/api/admin/services", json={**service, "category_id": str(uuid4())},
                                  headers={"Origin": "https://test"})).status_code == 404
        first = await client.post("/api/admin/services", json=service,
                                  headers={"Origin": "https://test"})
        assert first.status_code == 200
        service_id = first.json()["id"]
        assert first.json()["enabled"] is False
        repeated = await client.post("/api/admin/services", json=service,
                                     headers={"Origin": "https://test"})
        assert repeated.json()["id"] == service_id
        assert (await client.post("/api/admin/services", json={**service, "base_price_halalas": 600},
                                  headers={"Origin": "https://test"})).status_code == 409
        assert any(item["id"] == service_id and not item["enabled"]
                   for item in (await client.get("/api/admin/services")).json())
        assert (await client.post("/api/admin/services", json={**service, "slug": "merge-pdf"},
                                  headers={"Origin": "https://test"})).status_code == 422

    user_id = await ensure_telegram_user(db, uuid4().int % (2**63 - 1) + 1)
    with pytest.raises(ValueError, match="service unavailable"):
        await confirm_order(db, user_id, UUID(service_id), str(uuid4()))
    assert await db.fetchval("SELECT count(*) FROM audit_logs WHERE actor_admin_id=$1 AND action='CATEGORY_CREATED'",
                             owner_id) == 1
    assert await db.fetchval("SELECT count(*) FROM audit_logs WHERE actor_admin_id=$1 AND action='SERVICE_CREATED'",
                             owner_id) == 1
