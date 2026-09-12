"""Exercise admin authentication and authorization against migrated PostgreSQL."""

import os
from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import httpx
import pytest
from platform_core.admin_auth import (
    authenticate,
    create_admin,
    create_session,
    has_permission,
    load_session,
    revoke_session,
    token_digest,
)
from platform_core.orders import ensure_telegram_user

from apps.api import admin as admin_api
from apps.api.main import app


@pytest.fixture
async def db():
    connection = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    try:
        yield connection
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_admin_sessions_permissions_and_immutable_audit(db):
    password = "a unique long administrator password"
    owner_name, operator_name = "owner-" + uuid4().hex, "operator-" + uuid4().hex
    owner_id = await create_admin(db, owner_name, password, role_code="OWNER")
    operator_id = await create_admin(db, operator_name, password, role_code="OPERATOR")
    assert await authenticate(db, owner_name, "incorrect password") is None
    assert await authenticate(db, "missing-" + uuid4().hex, password) is None
    owner = await authenticate(db, owner_name, password)
    operator = await authenticate(db, operator_name, password)
    assert owner and operator and owner.id == owner_id and operator.id == operator_id
    assert await has_permission(db, owner, "admin:audit")
    assert await has_permission(db, operator, "admin:view")
    assert not await has_permission(db, operator, "admin:audit")
    token = await create_session(db, owner)
    assert token.encode() != token_digest(token)
    assert await load_session(db, token) == owner
    assert await db.fetchval("SELECT count(*) FROM audit_logs WHERE actor_admin_id=$1", owner_id) == 1
    with pytest.raises(asyncpg.PostgresError):
        await db.execute("DELETE FROM audit_logs WHERE actor_admin_id=$1", owner_id)
    await revoke_session(db, token, owner)
    assert await load_session(db, token) is None
    assert await db.fetchval("SELECT count(*) FROM audit_logs WHERE actor_admin_id=$1", owner_id) == 2
    operator_token = await create_session(db, operator)
    await db.execute("UPDATE admins SET enabled=false WHERE id=$1", operator_id)
    assert await load_session(db, operator_token) is None


@pytest.mark.asyncio
async def test_routes_enforce_role_and_origin(db):
    name = "operator-" + uuid4().hex
    password = "another long secret password"
    await create_admin(db, name, password, role_code="OPERATOR")
    operator = await authenticate(db, name, password)
    token = await create_session(db, operator)
    app.state.redis = None
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as client:
        assert (await client.get("/api/admin/overview")).status_code == 401
        assert (await client.get("/api/admin/attention")).status_code == 401
        client.cookies.set(admin_api.COOKIE_NAME, token)
        assert (await client.get("/api/admin/me")).json()["role"] == "OPERATOR"
        overview = await client.get("/api/admin/overview")
        assert overview.status_code == 200
        assert overview.json()["backup"]["status"] == "unconfigured"
        assert (await client.get("/api/admin/attention")).status_code == 200
        assert (await client.get("/api/admin/audit")).status_code == 403
        assert (await client.post("/api/admin/logout", headers={"Origin": "https://evil.example"})).status_code == 403
        assert (await client.post("/api/admin/logout", headers={"Origin": "https://test"})).status_code == 200
        assert (await client.get("/api/admin/me")).status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limit_and_secure_cookie(db):
    name = "owner-" + uuid4().hex
    password = "another unique and long owner password"
    await create_admin(db, name, password, role_code="OWNER")
    redis = AsyncMock()
    redis.incr.side_effect = [1, 2, 6]
    app.state.redis = redis
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as client:
        form = {"username": name, "password": password}
        assert (await client.post("/api/admin/login", json=form, headers={"Origin": "https://evil.example"})).status_code == 403
        assert (await client.post("/api/admin/login", json={**form, "password": "wrong"}, headers={"Origin": "https://test"})).status_code == 401
        result = await client.post("/api/admin/login", json=form, headers={"Origin": "https://test"})
        assert result.status_code == 200
        assert all(flag in result.headers["set-cookie"].lower() for flag in ("httponly", "secure", "samesite=strict"))
        assert (await client.get("/api/admin/audit")).status_code == 200
        assert (await client.post("/api/admin/login", json=form, headers={"Origin": "https://test"})).status_code == 429


@pytest.mark.asyncio
async def test_attention_reports_failures_without_customer_data(db):
    user_id = await ensure_telegram_user(db, uuid4().int % (2**63 - 1) + 1)
    category_id, service_id, order_id = uuid4(), uuid4(), uuid4()
    job_id, delivery_id, payment_id = uuid4(), uuid4(), uuid4()
    await db.execute("INSERT INTO service_categories (id,slug,name_ar) VALUES ($1,$2,'اختبار')",
                     category_id, str(category_id))
    await db.execute("""INSERT INTO services
      (id,category_id,slug,name_ar,processor_type,base_price_halalas)
      VALUES ($1,$2,$3,'دمج PDF','tool',1000)""", service_id, category_id, str(service_id))
    await db.execute("""INSERT INTO orders
      (id,user_id,service_id,client_request_key,channel,price_snapshot_halalas,status)
      VALUES ($1,$2,$3,$4,'telegram',1000,'FAILED')""",
      order_id, user_id, service_id, str(uuid4()))
    await db.execute("""INSERT INTO jobs
      (id,order_id,status,attempt_count,max_attempts,error_code,completed_at)
      VALUES ($1,$2,'FAILED',3,3,'PROCESSOR_UNAVAILABLE',now())""", job_id, order_id)
    await db.execute("""INSERT INTO delivery_outbox
      (id,order_id,channel,status,attempt_count,max_attempts,error_code,completed_at)
      VALUES ($1,$2,'telegram','FAILED',3,3,'DELIVERY_FAILED',now())""", delivery_id, order_id)
    await db.execute("""INSERT INTO payments
      (id,user_id,provider,payment_type,amount_halalas,status,client_request_key)
      VALUES ($1,$2,'test-provider','WALLET_TOPUP',1000,'FAILED',$3)""",
      payment_id, user_id, str(uuid4()))
    password = "a unique attention test password"
    name = "operator-" + uuid4().hex
    await create_admin(db, name, password, role_code="OPERATOR")
    operator = await authenticate(db, name, password)
    token = await create_session(db, operator)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as client:
        assert (await client.get("/api/admin/attention")).status_code == 401
        client.cookies.set(admin_api.COOKIE_NAME, token)
        result = await client.get("/api/admin/attention")
        assert result.status_code == 200
        payload = result.json()
        job = next(item for item in payload["jobs"] if item["id"] == str(job_id))
        delivery = next(item for item in payload["deliveries"] if item["id"] == str(delivery_id))
        payment = next(item for item in payload["payments"] if item["id"] == str(payment_id))
        assert job["order_id"] == delivery["order_id"] == str(order_id)
        assert job["error_code"] == "PROCESSOR_UNAVAILABLE"
        assert delivery["error_code"] == "DELIVERY_FAILED"
        assert payment["amount_halalas"] == 1000
        assert all(len(payload[section]) <= 20 for section in ("jobs", "deliveries", "payments"))
        assert not {"user_id", "client_request_key", "provider_reference", "external_receipt"} & set(job)
        assert not {"user_id", "client_request_key", "provider_reference", "external_receipt"} & set(payment)
