"""Exercise the ledger against the migrated PostgreSQL database, including row locks."""

import asyncio
import os
from uuid import uuid4

import asyncpg
import pytest

from platform_core.ledger import (
    Balance,
    IdempotencyConflict,
    InsufficientFunds,
    InvalidSettlement,
    balance,
    credit,
    reserve,
    settle,
)
from platform_core.orders import confirm_order, ensure_telegram_user


@pytest.fixture
async def db():
    connection = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    try:
        yield connection
    finally:
        await connection.close()


@pytest.fixture
async def customer(db):
    telegram_id = uuid4().int % (2**63 - 1) + 1
    return await ensure_telegram_user(db, telegram_id)


@pytest.fixture
async def service(db):
    category_id, service_id = uuid4(), uuid4()
    await db.execute(
        "INSERT INTO service_categories (id,slug,name_ar) VALUES ($1,$2,'اختبارات')",
        category_id, str(category_id),
    )
    await db.execute(
        """INSERT INTO services (id,category_id,slug,name_ar,processor_type,base_price_halalas,enabled)
           VALUES ($1,$2,$3,'خدمة اختبار','tool',1500,true)""",
        service_id, category_id, str(service_id),
    )
    return service_id


@pytest.mark.asyncio
async def test_ledger_topup_idempotency_and_adjustment(db, customer):
    assert await credit(db, customer, 2500, "payment:1") == await balance(db, customer)
    assert (await balance(db, customer)).available_halalas == 2500
    await credit(db, customer, 2500, "payment:1")
    assert await db.fetchval(
        "SELECT count(*) FROM wallet_transactions WHERE wallet_user_id=$1", customer,
    ) == 1
    with pytest.raises(IdempotencyConflict):
        await credit(db, customer, 3500, "payment:1")
    with pytest.raises(ValueError, match="reason"):
        await credit(db, customer, -500, "admin:1", kind="ADMIN_ADJUSTMENT")
    with pytest.raises(InsufficientFunds):
        await credit(db, customer, -2600, "admin:1", kind="ADMIN_ADJUSTMENT", reason="test")
    await credit(db, customer, -500, "admin:1", kind="ADMIN_ADJUSTMENT", reason="test")
    with pytest.raises(IdempotencyConflict):
        await credit(db, customer, -500, "admin:1", kind="ADMIN_ADJUSTMENT", reason="other")
    assert (await balance(db, customer)).available_halalas == 2000


@pytest.mark.asyncio
async def test_order_confirmation_reservation_price_snapshot_and_settlement(db, customer, service):
    await credit(db, customer, 3000, "payment:1")
    order_id = await confirm_order(db, customer, service, "telegram:update:123")
    assert order_id == await confirm_order(db, customer, service, "telegram:update:123")
    with pytest.raises(IdempotencyConflict):
        await confirm_order(db, customer, uuid4(), "telegram:update:123")
    assert await db.fetchval("SELECT count(*) FROM jobs WHERE order_id=$1", order_id) == 1
    assert await balance(db, customer) == Balance(1500, 1500)
    await db.execute("UPDATE services SET base_price_halalas=2800 WHERE id=$1", service)
    assert await db.fetchval(
        "SELECT price_snapshot_halalas FROM orders WHERE id=$1", order_id,
    ) == 1500
    await settle(db, customer, order_id, "capture:1", kind="CAPTURE")
    await settle(db, customer, order_id, "capture:1", kind="CAPTURE")
    with pytest.raises(InvalidSettlement):
        await settle(db, customer, order_id, "release:1", kind="RELEASE")
    assert (await balance(db, customer)).available_halalas == 1500
    assert (await balance(db, customer)).reserved_halalas == 0


@pytest.mark.asyncio
async def test_failure_releases_funds_and_insufficient_order_rolls_back(db, customer, service):
    with pytest.raises(InsufficientFunds):
        await confirm_order(db, customer, service, "no-funds")
    assert await db.fetchval(
        "SELECT count(*) FROM orders WHERE user_id=$1", customer,
    ) == 0
    await credit(db, customer, 1500, "payment:1")
    order_id = await confirm_order(db, customer, service, "retry")
    await settle(db, customer, order_id, "release:1", kind="RELEASE")
    await settle(db, customer, order_id, "release:1", kind="RELEASE")
    assert (await balance(db, customer)).available_halalas == 1500
    assert (await balance(db, customer)).reserved_halalas == 0


@pytest.mark.asyncio
async def test_concurrent_confirmations_cannot_overspend(db, customer, service):
    await credit(db, customer, 1500, "payment:1")
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "")

    async def purchase(key):
        connection = await asyncpg.connect(url)
        try:
            return await confirm_order(connection, customer, service, key)
        finally:
            await connection.close()

    outcomes = await asyncio.gather(
        purchase("concurrent:1"), purchase("concurrent:2"), return_exceptions=True,
    )
    assert len([result for result in outcomes if isinstance(result, InsufficientFunds)]) == 1
    assert len([result for result in outcomes if not isinstance(result, Exception)]) == 1
    assert await db.fetchval("SELECT count(*) FROM orders WHERE user_id=$1", customer) == 1
    assert (await balance(db, customer)).available_halalas == 0


@pytest.mark.asyncio
async def test_concurrent_duplicate_confirmation_creates_one_order(db, customer, service):
    await credit(db, customer, 1500, "payment:1")
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "")

    async def purchase():
        connection = await asyncpg.connect(url)
        try:
            return await confirm_order(connection, customer, service, "same-key")
        finally:
            await connection.close()

    first, second = await asyncio.gather(purchase(), purchase())
    assert first == second
    assert await db.fetchval("SELECT count(*) FROM jobs WHERE order_id=$1", first) == 1
    assert await balance(db, customer) == Balance(0, 1500)


@pytest.mark.asyncio
async def test_ledger_is_immutable_and_reservation_matches_order(db, customer, service):
    await credit(db, customer, 1500, "payment:1")
    order_id = await confirm_order(db, customer, service, "immutable")
    with pytest.raises(asyncpg.PostgresError):
        await db.execute(
            "UPDATE wallet_transactions SET amount_halalas=1 WHERE wallet_user_id=$1", customer,
        )
    with pytest.raises(asyncpg.PostgresError):
        await db.execute("DELETE FROM wallet_transactions WHERE wallet_user_id=$1", customer)
    with pytest.raises(IdempotencyConflict):
        await reserve(db, customer, order_id, 1500, "different-reserve-key")
    with pytest.raises(ValueError, match="does not match"):
        await reserve(db, customer, order_id, 1501, "different-amount")
