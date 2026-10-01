"""Actual disposable Redis Lua concurrency, cross-source limits and expiry."""

import asyncio
import os
from uuid import uuid4

import pytest
from platform_core.login_limits import login_allowed, login_keys
from redis.asyncio import Redis


@pytest.fixture
async def limiter():
    redis = Redis.from_url(os.environ["TEST_REDIS_URL"])
    try:
        yield redis
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_concurrent_pair_has_one_atomic_fixed_window(limiter):
    source, account = uuid4().hex, uuid4().hex
    results = await asyncio.gather(*[
        login_allowed(limiter, source, account) for _ in range(16)
    ])
    assert sum(results) == 5
    keys = login_keys(source, account)
    assert [int(await limiter.get(key)) for key in keys] == [16, 16, 16]
    ttls = [await limiter.ttl(key) for key in keys]
    assert all(0 < ttl <= 900 for ttl in ttls)


@pytest.mark.asyncio
async def test_account_limit_survives_source_rotation_and_normalization(limiter):
    account = "owner-" + uuid4().hex
    results = [
        await login_allowed(limiter, uuid4().hex, " " + account.upper() + " ")
        for _ in range(11)
    ]
    assert sum(results) == 10 and results[-1] is False
    assert login_keys("source", account)[1] == login_keys("other", account.upper())[1]


@pytest.mark.asyncio
async def test_source_limit_survives_username_rotation(limiter):
    source = uuid4().hex
    results = [
        await login_allowed(limiter, source, uuid4().hex) for _ in range(31)
    ]
    assert sum(results) == 30 and results[-1] is False


@pytest.mark.asyncio
async def test_missing_expiry_is_repaired_and_window_expires(limiter):
    source, account = uuid4().hex, uuid4().hex
    keys = login_keys(source, account)
    await limiter.set(keys[2], 1)
    assert await limiter.ttl(keys[2]) == -1
    assert await login_allowed(limiter, source, account, window_seconds=1)
    ttls = [await limiter.ttl(key) for key in keys]
    assert all(0 <= ttl <= 1 for ttl in ttls)
    await asyncio.sleep(1.1)
    counts = [await limiter.get(key) for key in keys]
    assert counts == [None, None, None]
    assert await login_allowed(limiter, source, account, window_seconds=1)


def test_counter_keys_do_not_expose_identity():
    keys = login_keys("203.0.113.99", "Private-Owner")
    assert all("203.0.113.99" not in key and "Private-Owner" not in key for key in keys)
    assert all("{admin-login}" in key for key in keys)
