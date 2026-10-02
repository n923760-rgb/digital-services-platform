"""Product administration, live bot catalog, consent and DB-only login limits."""

import asyncio
import hashlib
import os
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
from aiogram.types import CallbackQuery, Chat, Message, User
from platform_core.admin_auth import authenticate, create_admin, create_session
from platform_core.login_limits import login_keys, postgres_login_allowed
from platform_core.service_catalog import available_summary_products
from platform_core.service_registry import create_category, create_service, update_service
from platform_core.stars_payments import (
    StarsMismatch,
    accept_star_payment,
    approve_star_checkout,
    create_star_invoice,
)
from platform_core.summary_orders import (
    acknowledge_summary,
    execute_summary,
    quote_summary,
    select_summary_product,
)
from platform_core.telegram_workflow import StaleQuote
from platform_core.text_summary import SLUG, TEXT_INPUT_SCHEMA

from apps.api import admin as admin_api
from apps.api.v0 import app
from apps.telegram_bot import summary_ui

TEXT = "تقدم المنصة خدمات رقمية للسوق السعودي. تحافظ المنصة على أسعار واضحة وسجل الدفع."
TERMS = "Synthetic product purchase terms."


@pytest.fixture
async def products():
    db = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    owner = await create_admin(db, "owner-" + uuid4().hex, "synthetic product test password", role_code="OWNER")
    category = await create_category(db, owner, slug="category-" + uuid4().hex,
                                     name_ar="منتجات الاختبار", reason="Disposable catalog fixture")
    ids = []
    try:
        for price in (31, 47):
            service = await create_service(
                db, owner, category_id=category, slug="product-" + uuid4().hex,
                name_ar="تلخيص منتج اختبار", description_ar="تلخيص محلي من جمل النص",
                processor_type="tool", processor_key=SLUG, base_price_halalas=0,
                base_price_stars=price, input_schema=TEXT_INPUT_SCHEMA, reason="Disposable product fixture",
            )
            ids.append(service)
        yield db, owner, category, ids
    finally:
        await db.execute("UPDATE services SET enabled=false WHERE id=ANY($1::uuid[])", ids)
        await db.close()


async def activate(db, owner, product, revision=1, **changes):
    return await update_service(
        db, product, owner, expected_revision=revision, reason="Disposable activation test",
        enabled=True, confirm=True, allow_activation=True, **changes,
    )


async def invoice_for(db, user, product, message_id=1):
    await select_summary_product(db, user, product)
    quote = await quote_summary(db, user, message_id, TEXT, TERMS)
    buyer = await db.fetchval("SELECT id FROM users WHERE telegram_user_id=$1", user)
    invoice = await create_star_invoice(db, buyer, quote.workflow_id, quote.revision, TERMS, processor_key=SLUG)
    return quote, invoice


@pytest.mark.asyncio
async def test_new_product_visibility_live_name_price_and_paid_snapshot(products):
    db, owner, _category, (product, other) = products
    assert await available_summary_products(db, service_id=product) == []
    await activate(db, owner, product)
    await activate(db, owner, other)
    user = uuid4().int % 2**40 + 1
    quote, invoice = await invoice_for(db, user, product)
    digest = hashlib.sha256(TERMS.encode()).hexdigest()
    await approve_star_checkout(db, user, invoice.payload, "XTR", 31, uuid4().hex, digest, processor_key=SLUG)
    await update_service(db, product, owner, expected_revision=2, reason="Edit product after checkout",
                         name_ar="اسم المنتج المحدّث", base_price_stars=39)
    listing = await available_summary_products(db, service_id=product)
    assert listing[0].name_ar == "اسم المنتج المحدّث" and listing[0].price_stars == 39
    charge = uuid4().hex
    order = await accept_star_payment(db, user, invoice.payload, "XTR", 31, charge,
                                      allow_fulfillment=True, processor_key=SLUG)
    assert await db.fetchval("SELECT service_id FROM orders WHERE id=$1", order) == product
    assert await db.fetchval("SELECT price_snapshot_stars FROM orders WHERE id=$1", order) == 31
    assert await db.fetchval("SELECT count(*) FROM jobs WHERE order_id=$1", order) == 0
    assert await execute_summary(db, user, order)
    await acknowledge_summary(db, user, order, "telegram:synthetic:catalog")
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order) == "COMPLETED"
    await select_summary_product(db, user, product)
    assert (await quote_summary(db, user, 2, TEXT, TERMS)).price_stars == 39
    await update_service(db, product, owner, expected_revision=3, reason="Withdraw catalog product",
                         enabled=False, confirm=True)
    assert await available_summary_products(db, service_id=product) == []
    with pytest.raises(ValueError):
        await select_summary_product(db, user, product)
    assert quote.price_stars == 31


@pytest.mark.asyncio
async def test_product_switch_and_price_change_require_fresh_offer(products):
    db, owner, _category, (product, other) = products
    await activate(db, owner, product)
    await activate(db, owner, other)
    user = uuid4().int % 2**40 + 1
    _old_quote, old_invoice = await invoice_for(db, user, product)
    await approve_star_checkout(db, user, old_invoice.payload, "XTR", 31, uuid4().hex,
                                hashlib.sha256(TERMS.encode()).hexdigest(), processor_key=SLUG)
    await select_summary_product(db, user, other)
    with pytest.raises(StarsMismatch):
        await approve_star_checkout(db, user, old_invoice.payload, "XTR", 31, uuid4().hex,
                                    hashlib.sha256(TERMS.encode()).hexdigest(), processor_key=SLUG)
    late_charge = uuid4().hex
    assert await accept_star_payment(db, user, old_invoice.payload, "XTR", 31, late_charge,
                                     allow_fulfillment=True, processor_key=SLUG) is None
    assert await db.fetchval("SELECT status FROM star_charges WHERE charge_id=$1", late_charge) == "REFUND_PENDING"
    fresh = await quote_summary(db, user, 2, TEXT, TERMS)
    assert fresh.price_stars == 47
    buyer = await db.fetchval("SELECT id FROM users WHERE telegram_user_id=$1", user)
    invoice = await create_star_invoice(db, buyer, fresh.workflow_id, fresh.revision, TERMS, processor_key=SLUG)
    await update_service(db, other, owner, expected_revision=2, reason="Update before checkout", base_price_stars=50)
    with pytest.raises(StarsMismatch):
        await approve_star_checkout(db, user, invoice.payload, "XTR", 47, uuid4().hex,
                                    hashlib.sha256(TERMS.encode()).hexdigest(), processor_key=SLUG)
    with pytest.raises(StaleQuote):
        await create_star_invoice(db, buyer, fresh.workflow_id, fresh.revision, TERMS, processor_key=SLUG)


@pytest.mark.asyncio
async def test_invoice_cannot_rebind_to_another_same_price_product(products):
    db, owner, _category, (product, other) = products
    await activate(db, owner, product)
    await activate(db, owner, other, base_price_stars=31)
    user = uuid4().int % 2**40 + 1
    quote, invoice = await invoice_for(db, user, product)
    # Deliberate disposable corruption probes the product identity, not just amount/schema.
    await db.execute("UPDATE telegram_workflows SET service_id=$2 WHERE id=$1", quote.workflow_id, other)
    with pytest.raises(StarsMismatch):
        await approve_star_checkout(db, user, invoice.payload, "XTR", 31, uuid4().hex,
                                    hashlib.sha256(TERMS.encode()).hexdigest(), processor_key=SLUG)


@pytest.mark.asyncio
async def test_minimal_admin_product_routes_enforce_role_origin_revision_and_activation(products):
    db, _owner, category, _ids = products
    password = "synthetic http product test password"
    names = ["owner-" + uuid4().hex, "operator-" + uuid4().hex]
    tokens = []
    for name, role in zip(names, ("OWNER", "OPERATOR"), strict=True):
        await create_admin(db, name, password, role_code=role)
        tokens.append(await create_session(db, await authenticate(db, name, password)))
    data = {
        "category_id": str(category), "slug": "http-product-" + uuid4().hex,
        "name_ar": "منتج من اللوحة", "description_ar": "خدمة نصية", "processor_type": "tool",
        "processor_key": SLUG, "base_price_halalas": 0, "base_price_stars": 29,
        "input_schema": TEXT_INPUT_SCHEMA, "reason": "Create through minimal admin",
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as client:
        headers = {"Origin": "https://test"}
        assert (await client.post("/api/admin/services", json=data, headers=headers)).status_code == 401
        client.cookies.set(admin_api.COOKIE_NAME, tokens[1])
        assert (await client.post("/api/admin/services", json=data, headers=headers)).status_code == 403
        client.cookies.set(admin_api.COOKIE_NAME, tokens[0])
        assert (await client.post("/api/admin/services", json=data, headers={"Origin": "https://evil.test"})).status_code == 403
        assert (await client.post("/api/admin/services", json={**data, "processor_key": "arbitrary-code"}, headers=headers)).status_code == 422
        result = await client.post("/api/admin/services", json=data, headers=headers)
        assert result.status_code == 200 and result.json()["enabled"] is False
        service = UUID(result.json()["id"])
        repeated = await client.post("/api/admin/services", json=data, headers=headers)
        assert repeated.json()["id"] == str(service)
        path = f"/api/admin/services/{service}"
        change = {"expected_revision": 1, "name_ar": "منتج محدّث", "base_price_stars": 35,
                  "reason": "Edit name and price through panel"}
        assert (await client.patch(path, json=change, headers=headers)).status_code == 200
        assert (await client.patch(path, json=change, headers=headers)).status_code == 409
        assert (await client.patch(path, json={**change, "expected_revision": 2, "enabled": True, "confirm": True}, headers=headers)).status_code == 422
        assert await available_summary_products(db, service_id=service) == []
        assert await db.fetchval("SELECT count(*) FROM audit_logs WHERE metadata->>'service_id'=$1", str(service)) == 2


@pytest.mark.asyncio
async def test_catalog_callback_uses_private_customer_and_persists_selection(products, monkeypatch):
    db, owner, _category, (product, _other) = products
    await activate(db, owner, product)
    user = uuid4().int % 2**40 + 1
    settings = SimpleNamespace(
        database_url=os.environ["DATABASE_URL"], telegram_orders_enabled=True,
        telegram_stars_enabled=True, telegram_payment_terms=TERMS, telegram_payment_support="Synthetic support",
    )
    monkeypatch.setattr(summary_ui, "get_settings", lambda: settings)
    answer = AsyncMock()
    monkeypatch.setattr(Message, "answer", answer)
    monkeypatch.setattr(CallbackQuery, "answer", AsyncMock())
    message = Message(message_id=10, date=datetime.now(UTC), chat=Chat(id=user, type="private"),
                      from_user=User(id=999, is_bot=True, first_name="Synthetic bot"))
    callback = CallbackQuery(id="selection", chat_instance="synthetic",
                             from_user=User(id=user, is_bot=False, first_name="Customer"),
                             message=message, data=f"product:select:{product.hex}")
    await summary_ui.select_product(callback)
    assert await db.fetchval(
        "SELECT w.service_id FROM telegram_workflows w JOIN users u ON u.id=w.user_id WHERE u.telegram_user_id=$1 AND w.status='COLLECTING'", user,
    ) == product
    assert not await db.fetchval("SELECT 1 FROM telegram_workflows w JOIN users u ON u.id=w.user_id WHERE u.telegram_user_id=999 AND w.service_id=$1", product)
    await summary_ui.show_products(message)
    buttons = answer.await_args.kwargs["reply_markup"].inline_keyboard
    assert any(button.callback_data == f"product:select:{product.hex}" for row in buttons for button in row)
    await update_service(db, product, owner, expected_revision=2, reason="Refresh menu price test", base_price_stars=42)
    await summary_ui.show_products(message)
    buttons = answer.await_args.kwargs["reply_markup"].inline_keyboard
    assert any("42 ⭐" in button.text and button.callback_data.endswith(product.hex) for row in buttons for button in row)
    assert all(len(button.callback_data.encode()) <= 64 for row in buttons for button in row)
    foreign = callback.model_copy(update={"from_user": User(id=user + 1, is_bot=False, first_name="Foreign")})
    await summary_ui.select_product(foreign)
    assert not await db.fetchval("SELECT 1 FROM users WHERE telegram_user_id=$1", user + 1)


@pytest.mark.asyncio
async def test_postgres_login_limits_are_atomic_across_connections_and_expire():
    source, username = uuid4().hex, "owner-" + uuid4().hex
    connections = [await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", "")) for _ in range(6)]
    try:
        results = await asyncio.gather(*(
            postgres_login_allowed(db, source, username, source_limit=100, account_limit=100, pair_limit=3)
            for db in connections
        ))
        assert sum(results) == 3
        keys = login_keys(source, username)
        assert await connections[0].fetchval("SELECT attempts FROM admin_login_counters WHERE login_key=$1", keys[2]) == 6
        await connections[0].execute("UPDATE admin_login_counters SET expires_at=now()-interval '1 second' WHERE login_key=ANY($1::text[])", list(keys))
        assert await postgres_login_allowed(connections[0], source, username, pair_limit=3)
    finally:
        for db in connections:
            await db.close()


@pytest.mark.asyncio
async def test_db_login_limit_outage_fails_closed_and_logs_no_provider_body(monkeypatch, caplog):
    limiter, auth = AsyncMock(side_effect=OSError("sensitive-database-response")), AsyncMock()
    monkeypatch.setattr(admin_api, "postgres_login_allowed", limiter)
    monkeypatch.setattr(admin_api, "authenticate", auth)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as client:
        result = await client.post("/api/admin/login", headers={"Origin": "https://test"},
                                   json={"username": "unknown-user", "password": "synthetic"})
    assert result.status_code == 503 and "set-cookie" not in result.headers
    auth.assert_not_awaited()
    assert "sensitive-database-response" not in caplog.text
    assert "admin_login_limits_unavailable:OSError" in caplog.text
