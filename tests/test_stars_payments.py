"""Disposable PostgreSQL and typed Telegram fixtures for native direct Stars billing."""

import asyncio
import hashlib
import os
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import pytest
from aiogram.types import Chat, Message, RefundedPayment, SuccessfulPayment, Update, User
from platform_core.delivery import claim_delivery, fail_delivery, finish_delivery
from platform_core.files import upload_file
from platform_core.jobs import claim_job, complete_job, fail_job
from platform_core.ledger import Balance, balance
from platform_core.orders import ensure_telegram_user
from platform_core.stars_inbox import persist_payment_update, process_payment_inbox
from platform_core.stars_payments import (
    StarsMismatch,
    accept_star_payment,
    approve_star_checkout,
    confirm_star_refund,
    create_star_invoice,
)
from platform_core.telegram_workflow import (
    StaleQuote,
    attach_pdf,
    cancel_active,
    quote_pdf_merge,
    start_pdf_merge,
)

from apps.telegram_bot import stars_payments as ui

TERMS = "Synthetic accepted terms for an isolated test only."
DIGEST = hashlib.sha256(TERMS.encode()).hexdigest()


class MemoryStorage:
    def put_object(self, **kwargs):
        pass


@pytest.fixture
async def db():
    connection = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    try:
        yield connection
    finally:
        await connection.close()


@pytest.fixture
async def offer(db):
    category, proposed = uuid4(), uuid4()
    await db.execute("INSERT INTO service_categories (id,slug,name_ar) VALUES ($1,$2,'نجوم اختبار')",
                     category, str(category))
    await db.execute(
        """INSERT INTO services (id,category_id,slug,name_ar,processor_type,base_price_halalas,
           base_price_stars,input_schema,enabled)
           VALUES ($1,$2,'merge-pdf','دمج PDF','tool',700,37,$3::jsonb,true)
           ON CONFLICT (slug) DO NOTHING""", proposed, category,
        '{"min_files":2,"max_files":10,"file_mime":"application/pdf"}',
    )
    service = await db.fetchval("SELECT id FROM services WHERE slug='merge-pdf'")
    await db.execute(
        "UPDATE services SET enabled=true,base_price_stars=37 WHERE id=$1", service,
    )
    telegram_id = uuid4().int % (2**63 - 1) + 1
    user = await ensure_telegram_user(db, telegram_id)
    workflow = await start_pdf_merge(db, user)
    for i in (1, 2):
        file = await upload_file(db, MemoryStorage(), "test", user, f"{i}.pdf",
                                 "application/pdf", b"%PDF-synthetic")
        await attach_pdf(db, user, file.id, i)
    quote = await quote_pdf_merge(db, user, currency="XTR", terms_digest=DIGEST)
    invoice = await create_star_invoice(db, user, workflow.id, quote.quote_revision, TERMS)
    return SimpleNamespace(user=user, telegram_id=telegram_id, workflow=workflow,
                           quote=quote, invoice=invoice, service=service)


async def approve(db, offer, query="synthetic-checkout"):
    await approve_star_checkout(db, offer.telegram_id, offer.invoice.payload, "XTR", 37,
                                 f"{query}:{offer.invoice.id}", DIGEST)


async def pay(db, offer, charge=None, allow=True):
    return await accept_star_payment(db, offer.telegram_id, offer.invoice.payload, "XTR", 37,
                                     charge or str(offer.invoice.id), allow_fulfillment=allow)


@pytest.mark.asyncio
async def test_checkout_is_not_payment_and_concurrent_receipts_create_one_order(db, offer):
    assert offer.quote.quoted_price_halalas is None
    assert offer.quote.quoted_price_stars == 37
    assert await create_star_invoice(db, offer.user, offer.workflow.id,
                                     offer.quote.quote_revision, TERMS) == offer.invoice
    assert await db.fetchval("SELECT count(*) FROM orders WHERE user_id=$1", offer.user) == 0
    await approve(db, offer)
    assert await db.fetchval("SELECT count(*) FROM jobs j JOIN orders o ON o.id=j.order_id "
                            "WHERE o.user_id=$1", offer.user) == 0

    async def receipt():
        connection = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
        try:
            return await pay(connection, offer)
        finally:
            await connection.close()

    first, second = await asyncio.gather(receipt(), receipt())
    assert first == second
    order = await db.fetchrow("SELECT * FROM orders WHERE id=$1", first)
    assert (order["currency"], order["price_snapshot_halalas"], order["price_snapshot_stars"]) == (
        "XTR", 0, 37,
    )
    assert await db.fetchval("SELECT count(*) FROM jobs WHERE order_id=$1", first) == 1
    assert await balance(db, offer.user) == Balance(0, 0)
    assert await db.fetchval("SELECT count(*) FROM star_payment_events WHERE charge_id=$1",
                            str(offer.invoice.id)) == 1
    assert await db.fetchval("SELECT terms_text FROM star_invoices WHERE id=$1",
                            offer.invoice.id) == TERMS
    with pytest.raises(asyncpg.RaiseError, match="immutable"):
        await db.execute("DELETE FROM star_payment_events WHERE charge_id=$1",
                         str(offer.invoice.id))


@pytest.mark.asyncio
@pytest.mark.parametrize("currency,amount,payer", [
    ("SAR", 37, False), ("XTR", 36, False), ("XTR", 37, True),
])
async def test_checkout_and_receipt_reject_currency_amount_or_foreign_owner(db, offer, currency, amount, payer):
    sender = offer.telegram_id + 1 if payer else offer.telegram_id
    with pytest.raises(StarsMismatch):
        await approve_star_checkout(db, sender, offer.invoice.payload, currency, amount, "bad", DIGEST)
    with pytest.raises(StarsMismatch):
        await accept_star_payment(db, sender, offer.invoice.payload, currency, amount, "bad",
                                  allow_fulfillment=True)
    assert await db.fetchval("SELECT count(*) FROM orders WHERE user_id=$1", offer.user) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["price", "terms", "files", "cancel"])
async def test_stale_invoice_never_passes_checkout(db, offer, change):
    digest = DIGEST
    if change == "price":
        await db.execute("UPDATE services SET base_price_stars=38 WHERE id=$1", offer.service)
    elif change == "terms":
        digest = "f" * 64
    elif change == "files":
        file = await upload_file(db, MemoryStorage(), "test", offer.user, "third.pdf",
                                 "application/pdf", b"%PDF-third")
        await attach_pdf(db, offer.user, file.id, 3)
        with pytest.raises(StaleQuote):
            await create_star_invoice(db, offer.user, offer.workflow.id,
                                      offer.quote.quote_revision, TERMS)
    else:
        await cancel_active(db, offer.user)
    with pytest.raises(StarsMismatch):
        await approve_star_checkout(db, offer.telegram_id, offer.invoice.payload,
                                    "XTR", 37, "stale", digest)


@pytest.mark.asyncio
async def test_paid_receipt_honors_approved_price_and_duplicate_charge_is_refunded(db, offer):
    await approve(db, offer)
    await db.execute("UPDATE services SET base_price_stars=38 WHERE id=$1", offer.service)
    order = await pay(db, offer)
    assert order
    assert await pay(db, offer, charge="duplicate:" + str(offer.invoice.id)) is None
    assert await db.fetchval("SELECT status FROM star_charges WHERE charge_id=$1",
                            "duplicate:" + str(offer.invoice.id)) == "REFUND_PENDING"
    assert await db.fetchval("SELECT count(*) FROM orders WHERE user_id=$1", offer.user) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["cancel", "expiry", "disabled", "unapproved"])
async def test_late_or_unfulfillable_paid_receipt_is_kept_for_refund(db, offer, change):
    if change != "unapproved":
        await approve(db, offer)
    if change == "cancel":
        await cancel_active(db, offer.user)
    elif change == "expiry":
        await db.execute("UPDATE files SET retention_until=now()-interval '1 second' "
                         "WHERE owner_user_id=$1", offer.user)
    order = await pay(db, offer, allow=change != "disabled")
    assert order is None
    assert await db.fetchval("SELECT status FROM star_charges WHERE charge_id=$1",
                            str(offer.invoice.id)) == "REFUND_PENDING"
    assert await db.fetchval("SELECT count(*) FROM orders WHERE user_id=$1", offer.user) == 0
    assert await balance(db, offer.user) == Balance(0, 0)


@pytest.mark.asyncio
async def test_delivery_recognizes_stars_only_after_receipt(db, offer):
    await approve(db, offer)
    order = await pay(db, offer)
    job_id = await db.fetchval("SELECT id FROM jobs WHERE order_id=$1", order)
    job = await claim_job(db, job_id)
    output = await upload_file(db, MemoryStorage(), "test", offer.user, "result.pdf",
                               "application/pdf", b"%PDF-result", order_id=order, file_type="OUTPUT")
    await complete_job(db, job, output.id)
    assert await db.fetchval("SELECT status FROM star_charges WHERE order_id=$1", order) == "PAID"
    await db.execute("UPDATE delivery_outbox SET created_at='1990-01-01 UTC' WHERE order_id=$1", order)
    delivery = await claim_delivery(db)
    # Other fixtures must not be consumed: select our own delivery using its matching claim.
    if delivery.order_id != order:
        pytest.fail("unrelated pending delivery in disposable fixture")
    await finish_delivery(db, delivery, "telegram:synthetic-receipt")
    assert await db.fetchval("SELECT status FROM star_charges WHERE order_id=$1", order) == "DELIVERED"
    assert await balance(db, offer.user) == Balance(0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["processing", "delivery"])
async def test_terminal_failure_requests_real_stars_refund_not_sar_release(db, offer, failure):
    await approve(db, offer)
    order = await pay(db, offer)
    job = await claim_job(db, await db.fetchval("SELECT id FROM jobs WHERE order_id=$1", order))
    if failure == "processing":
        assert await fail_job(db, job, "SYNTHETIC_INPUT_ERROR", retryable=False)
    else:
        output = await upload_file(db, MemoryStorage(), "test", offer.user, "result.pdf",
                                   "application/pdf", b"%PDF-result",
                                   order_id=order, file_type="OUTPUT")
        await complete_job(db, job, output.id)
        await db.execute("UPDATE delivery_outbox SET created_at='1990-01-01 UTC' WHERE order_id=$1", order)
        delivery = await claim_delivery(db)
        assert delivery.order_id == order
        assert await fail_delivery(db, delivery, "SYNTHETIC_DELIVERY_ERROR", retryable=False)
    assert await db.fetchval("SELECT status FROM star_charges WHERE order_id=$1", order) == "REFUND_PENDING"
    bot = SimpleNamespace(refund_star_payment=AsyncMock(return_value=True))
    for _ in range(5):
        await ui.process_refunds(bot, db)
        if await db.fetchval("SELECT status FROM star_charges WHERE order_id=$1", order) == "REFUNDED":
            break
    assert await db.fetchval("SELECT status FROM star_charges WHERE order_id=$1", order) == "REFUNDED"
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order) == "REFUNDED"
    assert await balance(db, offer.user) == Balance(0, 0)


def update(offer, update_id, *, refunded=False):
    data = {"currency": "XTR", "total_amount": 37, "invoice_payload": offer.invoice.payload,
            "telegram_payment_charge_id": str(offer.invoice.id), "provider_payment_charge_id": ""}
    receipt = RefundedPayment(**data) if refunded else SuccessfulPayment(**data)
    message = Message(
        message_id=update_id, date=datetime.now(UTC),
        chat=Chat(id=offer.telegram_id, type="private"),
        from_user=User(id=999 if refunded else offer.telegram_id,
                       is_bot=refunded, first_name="Synthetic"),
        **({"refunded_payment": receipt} if refunded else {"successful_payment": receipt}),
    )
    return Update(update_id=update_id, message=message)


@pytest.mark.asyncio
async def test_durable_receipt_replay_and_refund_before_payment_never_starts_job(db, offer):
    await approve(db, offer)
    bot_id = uuid4().int % (2**63 - 1) + 1
    for _ in range(2):
        await persist_payment_update(db, bot_id, update(offer, 1, refunded=True))
    await persist_payment_update(db, bot_id, update(offer, 2))
    assert await process_payment_inbox(db, bot_id, allow_fulfillment=True) == 2
    assert await process_payment_inbox(db, bot_id, allow_fulfillment=True) == 0
    assert await db.fetchval("SELECT status FROM star_charges WHERE charge_id=$1",
                            str(offer.invoice.id)) == "REFUNDED"
    assert await db.fetchval("SELECT count(*) FROM orders WHERE user_id=$1", offer.user) == 0


@pytest.mark.asyncio
async def test_provider_refund_while_processing_prevents_completion(db, offer):
    await approve(db, offer)
    order = await pay(db, offer)
    job = await claim_job(db, await db.fetchval("SELECT id FROM jobs WHERE order_id=$1", order))
    await confirm_star_refund(db, offer.telegram_id, offer.invoice.payload, "XTR", 37,
                              str(offer.invoice.id))
    output = await upload_file(db, MemoryStorage(), "test", offer.user, "result.pdf",
                               "application/pdf", b"%PDF-result", order_id=order, file_type="OUTPUT")
    with pytest.raises(ValueError, match="attempt no longer active"):
        await complete_job(db, job, output.id)
    await fail_job(db, job, "STARS_REFUNDED", retryable=False)
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order) == "REFUNDED"


@pytest.mark.asyncio
async def test_polling_persists_before_next_offset_even_when_handler_fails(monkeypatch):
    event_offer = SimpleNamespace(telegram_id=42, invoice=SimpleNamespace(
        id=uuid4(), payload="stars:" + uuid4().hex))
    incoming = update(event_offer, 11)
    db = SimpleNamespace(execute=AsyncMock(), close=AsyncMock())
    calls = []

    async def get_updates(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return [incoming]
        db.execute.assert_awaited_once()
        assert kwargs["offset"] == 12
        raise asyncio.CancelledError()

    bot = SimpleNamespace(id=123, get_updates=get_updates)
    dispatcher = SimpleNamespace(resolve_used_update_types=lambda: ["message"],
                                 feed_update=AsyncMock(side_effect=RuntimeError("synthetic failure")))
    monkeypatch.setattr(ui.asyncpg, "connect", AsyncMock(return_value=db))
    monkeypatch.setattr(ui, "get_settings", lambda: SimpleNamespace(database_url="postgresql://test"))
    with pytest.raises(asyncio.CancelledError):
        await ui.poll_updates(bot, dispatcher)
    dispatcher.feed_update.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("matched", [False, True])
async def test_ambiguous_refund_requires_matching_outgoing_history(db, offer, matched):
    from aiogram.types import StarTransaction, StarTransactions, TransactionPartnerUser

    await approve(db, offer)
    await pay(db, offer, allow=False)
    transaction = StarTransaction(
        id=str(offer.invoice.id), amount=37, date=datetime.now(UTC),
        receiver=TransactionPartnerUser(
            transaction_type="invoice_payment",
            user=User(id=offer.telegram_id if matched else offer.telegram_id + 1,
                      is_bot=False, first_name="Synthetic buyer"),
            invoice_payload=offer.invoice.payload,
        ),
    )
    bot = SimpleNamespace(
        refund_star_payment=AsyncMock(side_effect=OSError("synthetic timeout")),
        get_star_transactions=AsyncMock(return_value=StarTransactions(transactions=[transaction])),
    )
    await ui.process_refunds(bot, db)
    status = await db.fetchval("SELECT status FROM star_charges WHERE charge_id=$1",
                              str(offer.invoice.id))
    assert status == ("REFUNDED" if matched else "REFUND_PENDING")


@pytest.mark.asyncio
async def test_precheckout_failure_sends_negative_answer_and_gates_require_terms_support(monkeypatch):
    from aiogram.types import PreCheckoutQuery

    settings = SimpleNamespace(telegram_orders_enabled=True, telegram_stars_enabled=True,
                               telegram_payment_terms=TERMS, telegram_payment_support="Synthetic support",
                               database_url="postgresql://test")
    assert ui.checkout_enabled(settings)
    settings.telegram_payment_support = ""
    assert not ui.checkout_enabled(settings)
    settings.telegram_payment_support = "Synthetic support"
    db = SimpleNamespace(close=AsyncMock())
    query = PreCheckoutQuery(
        id="synthetic", from_user=User(id=42, is_bot=False, first_name="Synthetic"),
        currency="XTR", total_amount=37, invoice_payload="stars:" + uuid4().hex,
    )
    answer = AsyncMock()
    monkeypatch.setattr(ui, "get_settings", lambda: settings)
    monkeypatch.setattr(ui.asyncpg, "connect", AsyncMock(return_value=db))
    monkeypatch.setattr(ui, "approve_star_checkout", AsyncMock(side_effect=TimeoutError()))
    monkeypatch.setattr(PreCheckoutQuery, "answer", answer)
    await ui.precheckout(query)
    assert answer.await_args.kwargs["ok"] is False
    assert answer.await_args.kwargs["error_message"]


@pytest.mark.asyncio
async def test_owned_private_invoice_has_one_xtr_price_and_empty_provider_token(db, offer, monkeypatch):
    from aiogram.types import CallbackQuery

    settings = SimpleNamespace(telegram_orders_enabled=True, telegram_stars_enabled=True,
                               telegram_payment_terms=TERMS, telegram_payment_support="Synthetic support",
                               database_url=os.environ["DATABASE_URL"])
    message = Message(message_id=7, date=datetime.now(UTC),
                      chat=Chat(id=offer.telegram_id, type="private"),
                      from_user=User(id=999, is_bot=True, first_name="Bot"), text="Stars quote")
    callback = CallbackQuery(
        id="synthetic-invoice", chat_instance="private",
        from_user=User(id=offer.telegram_id, is_bot=False, first_name="Buyer"),
        message=message,
        data=f"stars:confirm:{offer.workflow.id.hex}:{offer.quote.quote_revision}",
    )
    bot = SimpleNamespace(send_invoice=AsyncMock())
    monkeypatch.setattr(ui, "get_settings", lambda: settings)
    monkeypatch.setattr(CallbackQuery, "answer", AsyncMock())
    await ui.invoice(callback, bot)
    invoice = bot.send_invoice.await_args.kwargs
    assert invoice["currency"] == "XTR" and invoice["provider_token"] == ""
    assert invoice["chat_id"] == offer.telegram_id
    assert len(invoice["prices"]) == 1 and invoice["prices"][0].amount == 37
    assert invoice["payload"] == offer.invoice.payload
    assert len(invoice["payload"].encode()) <= 128
    assert invoice["start_parameter"]


@pytest.mark.asyncio
async def test_star_price_api_is_owner_only_strict_revisioned_and_preserves_invoice(db, offer):
    import json

    import httpx
    from platform_core.admin_auth import authenticate, create_admin, create_session

    from apps.api.admin import COOKIE_NAME
    from apps.api.main import app

    password = "isolated Stars price admin test"
    owner_name, operator_name = "stars-owner-" + uuid4().hex, "stars-operator-" + uuid4().hex
    owner_id = await create_admin(db, owner_name, password, role_code="OWNER")
    await create_admin(db, operator_name, password, role_code="OPERATOR")
    owner = await authenticate(db, owner_name, password)
    operator = await authenticate(db, operator_name, password)
    owner_token, operator_token = await create_session(db, owner), await create_session(db, operator)
    revision = await db.fetchval("SELECT revision FROM services WHERE id=$1", offer.service)
    sar_price = await db.fetchval("SELECT base_price_halalas FROM services WHERE id=$1", offer.service)
    payload = {"expected_revision": revision, "reason": "Synthetic Stars price review",
               "base_price_stars": 54}
    path = f"/api/admin/services/{offer.service}"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as client:
        assert (await client.patch(path, json=payload, headers={"Origin": "https://test"})).status_code == 401
        client.cookies.set(COOKIE_NAME, operator_token)
        assert (await client.patch(path, json=payload, headers={"Origin": "https://test"})).status_code == 403
        client.cookies.set(COOKIE_NAME, owner_token)
        assert (await client.patch(path, json=payload, headers={"Origin": "https://evil.test"})).status_code == 403
        for invalid in (True, 37.5, 0, -1, 100001):
            assert (await client.patch(path, json={**payload, "base_price_stars": invalid},
                                       headers={"Origin": "https://test"})).status_code == 422
        updated = await client.patch(path, json=payload, headers={"Origin": "https://test"})
        assert updated.status_code == 200 and updated.json()["base_price_stars"] == 54
        assert (await client.patch(path, json=payload, headers={"Origin": "https://test"})).status_code == 409
    assert await db.fetchval("SELECT base_price_halalas FROM services WHERE id=$1", offer.service) == sar_price
    assert await db.fetchval("SELECT amount_stars FROM star_invoices WHERE id=$1", offer.invoice.id) == 37
    audit = json.loads(await db.fetchval(
        "SELECT metadata FROM audit_logs WHERE actor_admin_id=$1 AND action='SERVICE_UPDATED'", owner_id,
    ))
    assert audit["before"]["base_price_stars"] == 37 and audit["after"]["base_price_stars"] == 54


@pytest.mark.asyncio
async def test_polling_database_failure_does_not_advance_payment_offset(monkeypatch):
    event_offer = SimpleNamespace(telegram_id=42, invoice=SimpleNamespace(
        id=uuid4(), payload="stars:" + uuid4().hex))
    incoming = update(event_offer, 22)
    db = SimpleNamespace(execute=AsyncMock(side_effect=[OSError("synthetic DB outage"), None]),
                         close=AsyncMock())
    calls = []
    real_sleep = asyncio.sleep

    async def get_updates(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return [incoming]
        if len(calls) == 2:
            assert kwargs["offset"] is None
            return [incoming]
        assert kwargs["offset"] == 23
        raise asyncio.CancelledError()

    async def no_backoff(delay):
        await real_sleep(0)

    bot = SimpleNamespace(id=123, get_updates=get_updates)
    dispatcher = SimpleNamespace(resolve_used_update_types=lambda: ["message"], feed_update=AsyncMock())
    monkeypatch.setattr(ui.asyncpg, "connect", AsyncMock(return_value=db))
    monkeypatch.setattr(ui, "get_settings", lambda: SimpleNamespace(database_url="postgresql://test"))
    monkeypatch.setattr(ui.asyncio, "sleep", no_backoff)
    with pytest.raises(asyncio.CancelledError):
        await ui.poll_updates(bot, dispatcher)
    assert db.execute.await_count == 2
    assert dispatcher.feed_update.await_count == 1
