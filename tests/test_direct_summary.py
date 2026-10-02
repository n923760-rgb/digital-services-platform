"""Direct summary/domain/Stars regressions with disposable PostgreSQL; no real billing."""

import asyncio
import hashlib
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient
from platform_core.ledger import Balance, balance
from platform_core.stars_payments import (
    StarsMismatch,
    accept_star_payment,
    approve_star_checkout,
    confirm_star_refund,
    create_star_invoice,
)
from platform_core.summary_orders import (
    acknowledge_summary,
    execute_summary,
    quote_summary,
    recover_interrupted_summaries,
    require_no_legacy_work,
)
from platform_core.text_summary import (
    SLUG,
    InvalidSummaryInput,
    LocalSummarizer,
    SummaryProviderError,
    validate_text,
)

from apps.api import v0 as api
from apps.telegram_bot import summary_ui

TEXT = "تقدم المنصة خدمات رقمية للسوق السعودي. تعتمد المنصة واجهة عربية واضحة. تحافظ المنصة على سجل الدفع."
TERMS = "Synthetic test terms, not live business terms."
DIGEST = hashlib.sha256(TERMS.encode()).hexdigest()


@pytest.fixture
async def summary_db():
    db = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    try:
        yield db
    finally:
        await db.close()


@pytest.fixture
async def offer(summary_db):
    db = summary_db
    await db.execute("UPDATE services SET enabled=true,base_price_stars=24 WHERE slug=$1", SLUG)
    user = uuid4().int % 2**40 + 1
    quote = await quote_summary(db, user, 1, TEXT, TERMS)
    invoice = await create_star_invoice(db, await db.fetchval(
        "SELECT id FROM users WHERE telegram_user_id=$1", user,
    ), quote.workflow_id, quote.revision, TERMS, service_slug=SLUG)
    await approve_star_checkout(db, user, invoice.payload, "XTR", 24, uuid4().hex, DIGEST, service_slug=SLUG)
    return user, quote, invoice, uuid4().hex


async def paid(db, offer):
    user, _, invoice, charge = offer
    return await accept_star_payment(
        db, user, invoice.payload, "XTR", 24, charge, allow_fulfillment=True, service_slug=SLUG,
    )


@pytest.mark.parametrize("text", ["", "short", "1" * 50, "أ" * 4001, None])
def test_summary_input_limits(text):
    with pytest.raises(InvalidSummaryInput):
        validate_text(text)


@pytest.mark.asyncio
async def test_local_summary_preserves_original_arabic_and_caps_output():
    result = await LocalSummarizer().summarize(TEXT)
    assert "المنصة" in result
    assert all(sentence in TEXT for sentence in result.splitlines())
    assert len(await LocalSummarizer().summarize("سعودي " * 600)) <= 1800


@pytest.mark.asyncio
async def test_direct_payment_replay_has_one_order_no_jobs_or_sar_writes(summary_db, offer):
    user, _, invoice, charge = offer
    assert await summary_db.fetchval("SELECT count(*) FROM orders o JOIN star_invoices i ON i.order_id=o.id WHERE i.id=$1", invoice.id) == 0
    connections = [await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", "")) for _ in range(2)]
    try:
        orders = await asyncio.gather(*(paid(db, offer) for db in connections))
    finally:
        for db in connections:
            await db.close()
    assert orders[0] == orders[1]
    order = orders[0]
    assert await summary_db.fetchval("SELECT count(*) FROM jobs WHERE order_id=$1", order) == 0
    user_id = await summary_db.fetchval("SELECT id FROM users WHERE telegram_user_id=$1", user)
    assert await balance(summary_db, user_id) == Balance(0, 0)
    assert await summary_db.fetchval("SELECT count(*) FROM star_payment_events WHERE charge_id=$1 AND event_type='PAID'", charge) == 1


@pytest.mark.asyncio
async def test_direct_provider_result_reuse_and_actual_delivery_receipt(summary_db, offer):
    db = summary_db
    user, _, _, charge = offer
    order = await paid(db, offer)
    provider = SimpleNamespace(summarize=AsyncMock(return_value="ملخص للاختبار دون مزود خارجي."))
    async def summarize(text):
        assert not db.is_in_transaction()
        assert text == TEXT
        return "ملخص للاختبار دون مزود خارجي."
    provider.summarize.side_effect = summarize
    result = await execute_summary(db, user, order, provider)
    assert await execute_summary(db, user, order, provider) == result
    assert provider.summarize.await_count == 1
    assert await db.fetchval("SELECT status FROM star_charges WHERE charge_id=$1", charge) == "PAID"
    await acknowledge_summary(db, user, order, "telegram:synthetic:1")
    await acknowledge_summary(db, user, order, "telegram:synthetic:1")
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order) == "COMPLETED"
    assert await db.fetchval("SELECT count(*) FROM star_payment_events WHERE charge_id=$1 AND event_type='DELIVERED'", charge) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["provider", "bad_result", "interrupted"])
async def test_direct_failure_requests_refund_without_queue(summary_db, offer, failure, caplog):
    db = summary_db
    user, _, invoice, charge = offer
    order = await paid(db, offer)
    if failure == "interrupted":
        await db.execute("UPDATE orders SET status='PROCESSING' WHERE id=$1", order)
        await recover_interrupted_summaries(db)
    else:
        provider = SimpleNamespace(summarize=AsyncMock(
            side_effect=OSError("sensitive-provider-body") if failure == "provider" else None,
            return_value="" if failure == "bad_result" else "unused",
        ))
        with pytest.raises((OSError, SummaryProviderError)):
            await execute_summary(db, user, order, provider)
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order) == "FAILED"
    assert await db.fetchval("SELECT status FROM star_charges WHERE charge_id=$1", charge) == "REFUND_PENDING"
    assert "sensitive-provider-body" not in caplog.text
    assert "summary_" in caplog.text
    await confirm_star_refund(db, user, invoice.payload, "XTR", 24, charge)
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order) == "REFUNDED"


@pytest.mark.asyncio
async def test_refund_during_direct_provider_prevents_completion(summary_db, offer):
    db = summary_db
    user, _, invoice, charge = offer
    order = await paid(db, offer)
    async def refunded(_text):
        await confirm_star_refund(db, user, invoice.payload, "XTR", 24, charge)
        return "يجب ألا تتحول هذه النتيجة إلى تسليم بعد الاسترداد."
    assert await execute_summary(db, user, order, SimpleNamespace(summarize=refunded)) is None
    assert await db.fetchval("SELECT count(*) FROM summary_results WHERE order_id=$1", order) == 0
    with pytest.raises(ValueError):
        await acknowledge_summary(db, user, order, "telegram:synthetic:1")


@pytest.mark.asyncio
async def test_input_snapshot_immutable_and_expired_input_refunds(summary_db, offer):
    db = summary_db
    _user, quote, invoice, charge = offer
    with pytest.raises(asyncpg.PostgresError):
        await db.execute("UPDATE summary_inputs SET input_text=$2 WHERE workflow_id=$1", quote.workflow_id, TEXT[::-1])
    with pytest.raises(asyncpg.PostgresError):
        await db.execute("UPDATE star_invoices SET input_text_digest='rebound' WHERE id=$1", invoice.id)
    await db.execute("DELETE FROM summary_inputs WHERE workflow_id=$1", quote.workflow_id)
    assert await paid(db, offer) is None
    assert await db.fetchval("SELECT status FROM star_charges WHERE charge_id=$1", charge) == "REFUND_PENDING"


@pytest.mark.asyncio
async def test_minimal_checkout_rejects_other_service_and_foreign_buyer(summary_db, offer):
    user, _, invoice, _ = offer
    for payer, slug in [(user + 1, SLUG), (user, "merge-pdf")]:
        with pytest.raises(StarsMismatch):
            await approve_star_checkout(summary_db, payer, invoice.payload, "XTR", 24, "other-query", DIGEST, service_slug=slug)


def test_minimal_ready_needs_only_migrated_postgres_and_reports_failure(monkeypatch):
    db = SimpleNamespace(fetchval=AsyncMock(side_effect=["0017_direct_text_summary", True]), close=AsyncMock())
    connect = AsyncMock(return_value=db)
    monkeypatch.setattr(api.asyncpg, "connect", connect)
    with TestClient(api.app) as client:
        response = client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok"}
    connect.side_effect = OSError("sensitive-connection")
    with TestClient(api.app) as client:
        response = client.get("/api/health/ready")
    assert response.status_code == 503
    assert "sensitive-connection" not in response.text


@pytest.mark.asyncio
async def test_uncertain_send_keeps_cached_result_until_actual_receipt(summary_db, offer):
    db = summary_db
    user, _, _, charge = offer
    order = await paid(db, offer)
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=OSError("private-transport-body")))
    await summary_ui.deliver_pending(db, bot, user)
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order) == "AWAITING_FULFILLMENT"
    assert await db.fetchval("SELECT status FROM star_charges WHERE charge_id=$1", charge) == "PAID"
    bot.send_message.side_effect = None
    bot.send_message.return_value = SimpleNamespace(chat=SimpleNamespace(id=user), message_id=123)
    await summary_ui.deliver_pending(db, bot, user)
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order) == "COMPLETED"


@pytest.mark.asyncio
async def test_minimal_startup_refuses_unresolved_legacy_work():
    db = SimpleNamespace(fetchval=AsyncMock(return_value=1))
    with pytest.raises(RuntimeError, match="legacy orders"):
        await require_no_legacy_work(db)


@pytest.mark.asyncio
async def test_typed_payment_update_runs_minimal_bot_directly_and_replays_safely(summary_db, offer, monkeypatch):
    from datetime import UTC, datetime

    from aiogram.types import Chat, Message, SuccessfulPayment, Update, User
    from platform_core.stars_inbox import persist_payment_update

    from apps.telegram_bot import v0

    db = summary_db
    user, _, invoice, charge = offer
    settings = SimpleNamespace(
        database_url=os.environ["DATABASE_URL"], telegram_orders_enabled=True,
        telegram_stars_enabled=True, telegram_payment_terms=TERMS,
        telegram_payment_support="Synthetic support",
    )
    monkeypatch.setattr(summary_ui, "get_settings", lambda: settings)
    message = Message(
        message_id=2, date=datetime.now(UTC), chat=Chat(id=user, type="private"),
        from_user=User(id=user, is_bot=False, first_name="Synthetic"),
        successful_payment=SuccessfulPayment(
            currency="XTR", total_amount=24, invoice_payload=invoice.payload,
            telegram_payment_charge_id=charge, provider_payment_charge_id="",
        ),
    )
    update = Update(update_id=uuid4().int % 2**30, message=message)
    bot = SimpleNamespace(
        id=999, send_message=AsyncMock(return_value=SimpleNamespace(chat=SimpleNamespace(id=user), message_id=3)),
        refund_star_payment=AsyncMock(return_value=False),
    )
    monkeypatch.setattr(Message, "answer", AsyncMock())
    await persist_payment_update(db, bot.id, update)
    await v0.receipt(message, bot)
    await v0.receipt(message, bot)
    assert bot.send_message.await_count == 1
    order = await db.fetchval("SELECT order_id FROM star_charges WHERE charge_id=$1", charge)
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order) == "COMPLETED"
    assert await db.fetchval("SELECT count(*) FROM jobs WHERE order_id=$1", order) == 0
    assert await db.fetchval(
        "SELECT status FROM telegram_payment_inbox WHERE bot_id=$1 AND update_id=$2", bot.id, update.update_id,
    ) == "DONE"
