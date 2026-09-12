"""Job retry and release invariants on a migrated PostgreSQL instance."""

import asyncio
import os
from uuid import uuid4

import asyncpg
import pytest
from platform_core.jobs import claim_job, fail_job, pending_jobs, recover_stale_jobs
from platform_core.ledger import Balance, balance, credit
from platform_core.orders import confirm_order, ensure_telegram_user


@pytest.fixture
async def db():
    connection = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    try:
        yield connection
    finally:
        await connection.close()


@pytest.fixture
async def reserved_order(db):
    user_id = await ensure_telegram_user(db, uuid4().int % (2**63 - 1) + 1)
    category_id, service_id = uuid4(), uuid4()
    await db.execute(
        "INSERT INTO service_categories (id,slug,name_ar) VALUES ($1,$2,'اختبار')",
        category_id, str(category_id),
    )
    await db.execute(
        """INSERT INTO services (id,category_id,slug,name_ar,processor_type,base_price_halalas,enabled)
           VALUES ($1,$2,$3,'اختبار','tool',1000,true)""",
        service_id, category_id, str(service_id),
    )
    await credit(db, user_id, 1000, "payment:test")
    order_id = await confirm_order(db, user_id, service_id, str(uuid4()))
    job_id = await db.fetchval("SELECT id FROM jobs WHERE order_id=$1", order_id)
    return user_id, order_id, job_id


@pytest.mark.asyncio
async def test_retry_exhaustion_releases_reservation_once(db, reserved_order):
    user_id, order_id, job_id = reserved_order
    assert (job_id, 1) in await pending_jobs(db)
    for number in range(1, 4):
        claim = await claim_job(db, job_id)
        assert claim.attempt_number == number
        assert await claim_job(db, job_id) is None
        assert await fail_job(db, claim, "TRANSIENT", retryable=True) is (number == 3)
    assert (job_id, 4) not in await pending_jobs(db)
    assert await claim_job(db, job_id) is None
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order_id) == "FAILED"
    assert await db.fetchval("SELECT status FROM jobs WHERE id=$1", job_id) == "FAILED"
    assert await db.fetchval("SELECT count(*) FROM job_attempts WHERE job_id=$1", job_id) == 3
    assert await balance(db, user_id) == Balance(1000, 0)
    assert await db.fetchval(
        "SELECT count(*) FROM wallet_transactions WHERE order_id=$1 AND transaction_type='RELEASE'",
        order_id,
    ) == 1


@pytest.mark.asyncio
async def test_permanent_failure_releases_without_retry(db, reserved_order):
    user_id, order_id, job_id = reserved_order
    claim = await claim_job(db, job_id)
    assert await fail_job(db, claim, "PROCESSOR_UNAVAILABLE", retryable=False)
    assert await balance(db, user_id) == Balance(1000, 0)
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order_id) == "FAILED"
    with pytest.raises(ValueError, match="no longer active"):
        await fail_job(db, claim, "PROCESSOR_UNAVAILABLE", retryable=False)


@pytest.mark.asyncio
async def test_concurrent_claims_only_one_attempt(db, reserved_order):
    _, _, job_id = reserved_order
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "")

    async def claim():
        connection = await asyncpg.connect(url)
        try:
            return await claim_job(connection, job_id)
        finally:
            await connection.close()

    claims = await asyncio.gather(claim(), claim())
    assert sum(item is not None for item in claims) == 1
    assert await db.fetchval("SELECT count(*) FROM job_attempts WHERE job_id=$1", job_id) == 1


@pytest.mark.asyncio
async def test_rejected_claim_does_not_touch_wallet(db, reserved_order):
    user_id, _, job_id = reserved_order
    assert await claim_job(db, uuid4()) is None
    assert await balance(db, user_id) == Balance(0, 1000)
    assert (job_id, 1) in await pending_jobs(db)


@pytest.mark.asyncio
async def test_expired_processing_attempt_recovers(db, reserved_order):
    user_id, _, job_id = reserved_order
    claim = await claim_job(db, job_id)
    await db.execute("UPDATE jobs SET started_at=now()-interval '10 minutes' WHERE id=$1", job_id)
    assert await recover_stale_jobs(db) >= 1
    assert await db.fetchval("SELECT status FROM jobs WHERE id=$1", job_id) == "PENDING"
    assert await db.fetchval(
        "SELECT error_code FROM job_attempts WHERE job_id=$1 AND attempt_number=1", job_id,
    ) == "WORKER_TIMEOUT"
    assert await balance(db, user_id) == Balance(0, 1000)
    assert (job_id, claim.attempt_number + 1) in await pending_jobs(db)
