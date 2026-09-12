"""Service changes are owner-only, audited, revisioned and preserve order price snapshots."""

import json
import os
from uuid import uuid4

import asyncpg
import httpx
import pytest
from platform_core.admin_auth import authenticate, create_admin, create_session
from platform_core.ledger import credit
from platform_core.orders import confirm_order, ensure_telegram_user
from platform_core.service_registry import ServiceUpdateRejected, update_service

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
async def test_owner_edit_is_atomic_and_existing_order_keeps_price(db):
    category_id, service_id = uuid4(), uuid4()
    await db.execute("INSERT INTO service_categories (id,slug,name_ar) VALUES ($1,$2,'أدوات')",
                     category_id, str(category_id))
    await db.execute("""INSERT INTO services
      (id,category_id,slug,name_ar,processor_type,base_price_halalas,enabled)
      VALUES ($1,$2,$3,'خدمة اختبار','tool',1000,true)""",
      service_id, category_id, str(service_id))
    user_id = await ensure_telegram_user(db, uuid4().int % (2**63 - 1) + 1)
    await credit(db, user_id, 3000, "service-admin-fixture")
    first_order = await confirm_order(db, user_id, service_id, str(uuid4()))

    password = "an owner password for service edits"
    owner_name, operator_name = "owner-" + uuid4().hex, "operator-" + uuid4().hex
    owner_id = await create_admin(db, owner_name, password, role_code="OWNER")
    await create_admin(db, operator_name, password, role_code="OPERATOR")
    owner = await authenticate(db, owner_name, password)
    operator = await authenticate(db, operator_name, password)
    owner_token, operator_token = await create_session(db, owner), await create_session(db, operator)
    path = f"/api/admin/services/{service_id}"
    changed = {"expected_revision": 1, "reason": "Price update for testing",
               "description_ar": "وصف جديد", "base_price_halalas": 1500}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as client:
        assert (await client.get("/api/admin/services")).status_code == 401
        assert (await client.patch(path, json=changed, headers={"Origin": "https://test"})).status_code == 401
        client.cookies.set(COOKIE_NAME, operator_token)
        assert any(row["id"] == str(service_id) for row in (await client.get("/api/admin/services")).json())
        assert (await client.patch(path, json=changed, headers={"Origin": "https://test"})).status_code == 403
        client.cookies.set(COOKIE_NAME, owner_token)
        assert (await client.patch(path, json=changed, headers={"Origin": "https://evil.test"})).status_code == 403
        assert (await client.patch(path, json=changed, headers={"Origin": "https://test"})).status_code == 200
        assert (await client.patch(path, json=changed, headers={"Origin": "https://test"})).status_code == 409
        assert (await client.patch(path, json={**changed, "expected_revision": 2, "enabled": False},
                                   headers={"Origin": "https://test"})).status_code == 422
        stopped = await client.patch(path, json={**changed, "expected_revision": 2,
                                                 "enabled": False, "confirm": True},
                                     headers={"Origin": "https://test"})
        assert stopped.status_code == 200
        assert stopped.json()["revision"] == 3
        assert (await client.patch(path, json={**changed, "expected_revision": 3,
                                              "enabled": True, "confirm": True},
                                   headers={"Origin": "https://test"})).status_code == 422

    assert await db.fetchval("SELECT price_snapshot_halalas FROM orders WHERE id=$1", first_order) == 1000
    assert await db.fetchval("SELECT base_price_halalas FROM services WHERE id=$1", service_id) == 1500
    assert await db.fetchval("SELECT enabled FROM services WHERE id=$1", service_id) is False
    rows = await db.fetch("SELECT metadata FROM audit_logs WHERE actor_admin_id=$1 AND action='SERVICE_UPDATED'",
                          owner_id)
    assert len(rows) == 2
    first = next(json.loads(row["metadata"]) for row in rows
                 if json.loads(row["metadata"])["revision_after"] == 2)
    assert first["before"]["base_price_halalas"] == 1000
    assert first["after"]["base_price_halalas"] == 1500


@pytest.mark.asyncio
async def test_unknown_processor_cannot_be_activated_even_if_flag_is_set(db):
    category_id, service_id = uuid4(), uuid4()
    await db.execute("INSERT INTO service_categories (id,slug,name_ar) VALUES ($1,$2,'اختبار')",
                     category_id, str(category_id))
    await db.execute("""INSERT INTO services
      (id,category_id,slug,name_ar,processor_type,base_price_halalas)
      VALUES ($1,$2,$3,'خدمة غير جاهزة','tool',1000)""",
      service_id, category_id, str(service_id))
    admin_id = await create_admin(db, "owner-" + uuid4().hex,
                                  "password for disabled service", role_code="OWNER")
    with pytest.raises(ServiceUpdateRejected, match="activation is unavailable"):
        await update_service(db, service_id, admin_id, expected_revision=1,
                             reason="Activation readiness test", enabled=True,
                             confirm=True, allow_activation=True)
    assert await db.fetchval("SELECT enabled FROM services WHERE id=$1", service_id) is False
    assert await db.fetchval("SELECT count(*) FROM audit_logs WHERE actor_admin_id=$1", admin_id) == 0
