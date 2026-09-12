"""Real PostgreSQL payment and wallet invariants; adapter fixture is test-only."""

import asyncio
import hashlib
import hmac
import json
import os
from uuid import UUID, uuid4

import asyncpg
import pytest
from platform_core.ledger import IdempotencyConflict, balance
from platform_core.orders import ensure_telegram_user
from platform_core.payments import (
    PaymentMismatch,
    VerifiedTopup,
    accept_verified_webhook,
    apply_verified_topup,
    bind_provider_reference,
    create_topup_intent,
)


@pytest.fixture
async def db():
    connection = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    try:
        yield connection
    finally:
        await connection.close()


@pytest.fixture
async def customer(db):
    return await ensure_telegram_user(db, uuid4().int % (2**63 - 1) + 1)


@pytest.mark.asyncio
async def test_paid_receipts_credit_once_and_preserve_event_history(db, customer):
    payment_id = await create_topup_intent(db, customer, 2500, "test-provider", "request-1")
    assert payment_id == await create_topup_intent(db, customer, 2500, "test-provider", "request-1")
    with pytest.raises(IdempotencyConflict):
        await create_topup_intent(db, customer, 3000, "test-provider", "request-1")
    await bind_provider_reference(db, payment_id, "checkout-1")
    await bind_provider_reference(db, payment_id, "checkout-1")
    with pytest.raises(IdempotencyConflict):
        await bind_provider_reference(db, payment_id, "checkout-other")
    other = await create_topup_intent(db, customer, 2500, "test-provider", "request-2")
    with pytest.raises(IdempotencyConflict):
        await bind_provider_reference(db, other, "checkout-1")
    event = VerifiedTopup("test-provider", "event-1", payment_id, "checkout-1", 2500, "SAR")
    assert (await apply_verified_topup(db, event)).available_halalas == 2500
    await apply_verified_topup(db, event)
    await apply_verified_topup(db, VerifiedTopup("test-provider", "event-2", payment_id,
                                                 "checkout-1", 2500, "SAR"))
    assert await db.fetchval("SELECT count(*) FROM payment_events WHERE payment_id=$1", payment_id) == 2
    assert await db.fetchval(
        "SELECT count(*) FROM wallet_transactions WHERE wallet_user_id=$1", customer,
    ) == 1
    assert await db.fetchval("SELECT status FROM payments WHERE id=$1", payment_id) == "PAID"
    await bind_provider_reference(db, payment_id, "checkout-1")
    with pytest.raises(asyncpg.PostgresError):
        await db.execute("DELETE FROM payment_events WHERE payment_id=$1", payment_id)


@pytest.mark.asyncio
async def test_forged_or_mismatched_receipts_cannot_credit(db, customer):
    payment_id = await create_topup_intent(db, customer, 2500, "test-provider", "request-3")
    await bind_provider_reference(db, payment_id, "checkout-3")
    for event in (
        VerifiedTopup("test-provider", "bad-amount", payment_id, "checkout-3", 3000, "SAR"),
        VerifiedTopup("test-provider", "bad-currency", payment_id, "checkout-3", 2500, "USD"),
        VerifiedTopup("test-provider", "bad-ref", payment_id, "checkout-4", 2500, "SAR"),
        VerifiedTopup("other-provider", "bad-provider", payment_id, "checkout-3", 2500, "SAR"),
    ):
        with pytest.raises(PaymentMismatch):
            await apply_verified_topup(db, event)
    assert (await balance(db, customer)).available_halalas == 0
    assert await db.fetchval("SELECT count(*) FROM payment_events WHERE payment_id=$1", payment_id) == 0
    event = VerifiedTopup("test-provider", "event-3", payment_id, "checkout-3", 2500, "SAR")
    await apply_verified_topup(db, event)
    other = await create_topup_intent(db, customer, 2500, "test-provider", "request-4")
    await bind_provider_reference(db, other, "checkout-4")
    with pytest.raises(PaymentMismatch):
        await apply_verified_topup(db, VerifiedTopup("test-provider", "event-3", other,
                                                     "checkout-4", 2500, "SAR"))
    assert (await balance(db, customer)).available_halalas == 2500
    assert await db.fetchval("SELECT status FROM payments WHERE id=$1", other) == "PENDING"


@pytest.mark.asyncio
async def test_concurrent_verified_delivery_cannot_double_credit(db, customer):
    payment_id = await create_topup_intent(db, customer, 4200, "test-provider", "concurrent")
    await bind_provider_reference(db, payment_id, "checkout-concurrent")
    event = VerifiedTopup("test-provider", "event-concurrent", payment_id,
                          "checkout-concurrent", 4200, "SAR")

    async def deliver():
        connection = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
        try:
            return await apply_verified_topup(connection, event)
        finally:
            await connection.close()

    first, second = await asyncio.gather(deliver(), deliver())
    assert first.available_halalas == second.available_halalas == 4200
    assert await db.fetchval("SELECT count(*) FROM payment_events WHERE payment_id=$1", payment_id) == 1
    assert await db.fetchval("SELECT count(*) FROM wallet_transactions WHERE wallet_user_id=$1", customer) == 1


class ExampleSignatureAdapter:
    """Demonstrate verification boundary; not a production payment provider."""

    secret = b"test-only-secret"

    def verify_paid_event(self, raw_body: bytes, headers: dict[str, str]) -> VerifiedTopup:
        signature = hmac.new(self.secret, raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, headers.get("x-test-signature", "")):
            raise PaymentMismatch("invalid webhook signature")
        event = json.loads(raw_body)
        return VerifiedTopup(event["provider"], event["event_id"], UUID(event["payment_id"]),
                             event["provider_reference"], event["amount_halalas"], event["currency"])


@pytest.mark.asyncio
async def test_signature_boundary_rejects_unauthenticated_webhooks(db, customer):
    payment_id = await create_topup_intent(db, customer, 1200, "test-provider", "signed")
    await bind_provider_reference(db, payment_id, "checkout-signed")
    raw_body = json.dumps({"provider": "test-provider", "event_id": "signed-event",
                           "payment_id": str(payment_id), "provider_reference": "checkout-signed",
                           "amount_halalas": 1200, "currency": "SAR"}).encode()
    adapter = ExampleSignatureAdapter()
    with pytest.raises(PaymentMismatch):
        await accept_verified_webhook(db, adapter, raw_body, {"x-test-signature": "forged"})
    assert (await balance(db, customer)).available_halalas == 0
    signature = hmac.new(adapter.secret, raw_body, hashlib.sha256).hexdigest()
    await accept_verified_webhook(db, adapter, raw_body, {"x-test-signature": signature})
    assert (await balance(db, customer)).available_halalas == 1200
