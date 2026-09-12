"""Proof of the internal file → wallet → order → job → quality → delivery flow."""

import os
import subprocess
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import asyncpg
import pytest
from platform_core import pdf_isolation
from platform_core.delivery import (
    claim_delivery,
    fail_delivery,
    finish_delivery,
    recover_stale_deliveries,
)
from platform_core.files import upload_file
from platform_core.jobs import claim_job, complete_job, fail_job
from platform_core.ledger import Balance, IdempotencyConflict, balance, credit
from platform_core.orders import acknowledge_delivery, confirm_order, ensure_telegram_user
from platform_core.pdf_isolation import MAX_INPUT_BYTES, merge_pdfs_isolated
from platform_core.pdf_merge import InvalidPDF, merge_pdfs
from platform_core.processors import process_pdf_merge
from pypdf import PdfReader, PdfWriter

from apps.telegram_bot.delivery import send_result


class MemoryStorage:
    def __init__(self):
        self.objects = {}

    def put_object(self, *, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body

    def head_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise FileNotFoundError(Key)
        return {"ContentLength": len(self.objects[Key])}

    def read_object(self, *, Bucket, Key, MaxBytes):
        if Key not in self.objects:
            raise FileNotFoundError(Key)
        return self.objects[Key][:MaxBytes + 1]


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_document(self, *, chat_id, document, caption):
        self.sent.append((chat_id, document.data, caption))
        return SimpleNamespace(message_id=42)


def blank_pdf(width=100):
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=100)
    stream = BytesIO()
    writer.write(stream)
    writer.close()
    return stream.getvalue()


def test_deterministic_pdf_merge_checks_pages_and_rejects_bad_input():
    result = merge_pdfs([blank_pdf(100), blank_pdf(200)])
    reader = PdfReader(BytesIO(result))
    assert len(reader.pages) == 2
    assert [int(page.mediabox.width) for page in reader.pages] == [100, 200]
    with pytest.raises(InvalidPDF):
        merge_pdfs([blank_pdf(100), b"%PDF-not-a-real-file"])
    with pytest.raises(InvalidPDF):
        merge_pdfs([blank_pdf(100)])


def test_pdf_merge_process_is_separate_bounded_and_rejects_bad_data(monkeypatch):
    monkeypatch.setenv("PAYMENT_SECRET_IN_PARENT", "not-for-pdf-child")
    actual_popen = subprocess.Popen
    observed = []

    def capture_child(*args, **kwargs):
        observed.append(kwargs)
        return actual_popen(*args, **kwargs)

    monkeypatch.setattr(pdf_isolation.subprocess, "Popen", capture_child)
    result = merge_pdfs_isolated([blank_pdf(100), blank_pdf(200)])
    assert len(PdfReader(BytesIO(result)).pages) == 2
    assert "PAYMENT_SECRET_IN_PARENT" not in observed[0]["env"]
    assert observed[0]["close_fds"] and observed[0]["start_new_session"]
    with pytest.raises(InvalidPDF):
        merge_pdfs_isolated([blank_pdf(), b"%PDF-corrupted"])
    with pytest.raises(InvalidPDF):
        merge_pdfs_isolated([b"%PDF-" + b"x" * MAX_INPUT_BYTES, blank_pdf()])


@pytest.fixture
async def db():
    connection = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    try:
        yield connection
    finally:
        await connection.close()


@pytest.fixture
async def setup_order(db):
    user_id = await ensure_telegram_user(db, uuid4().int % (2**63 - 1) + 1)
    category_id, service_id = uuid4(), uuid4()
    await db.execute(
        "INSERT INTO service_categories (id,slug,name_ar) VALUES ($1,$2,'أدوات')",
        category_id, str(category_id),
    )
    await db.execute(
        """INSERT INTO services
           (id,category_id,slug,name_ar,processor_type,base_price_halalas,input_schema,enabled)
           VALUES ($1,$2,'merge-pdf','دمج PDF','tool',700,$3::jsonb,true)
           ON CONFLICT (slug) DO NOTHING""",
        service_id, category_id,
        '{"min_files":2,"max_files":10,"file_mime":"application/pdf"}',
    )
    service_id = await db.fetchval("SELECT id FROM services WHERE slug='merge-pdf'")
    storage = MemoryStorage()
    records = [
        await upload_file(db, storage, "test", user_id, f"page-{index}.pdf",
                          "application/pdf", blank_pdf(index * 100))
        for index in (1, 2)
    ]
    return user_id, service_id, storage, [record.id for record in records]


@pytest.mark.asyncio
async def test_pdf_merge_waits_for_delivery_before_capture(db, setup_order):
    user_id, service_id, storage, files = setup_order
    await credit(db, user_id, 1000, "payment:test")
    order_id = await confirm_order(db, user_id, service_id, "request:merge", file_ids=files)
    assert await confirm_order(db, user_id, service_id, "request:merge", file_ids=files) == order_id
    with pytest.raises(IdempotencyConflict):
        await confirm_order(db, user_id, service_id, "request:merge", file_ids=list(reversed(files)))
    assert await balance(db, user_id) == Balance(300, 700)
    job_id = await db.fetchval("SELECT id FROM jobs WHERE order_id=$1", order_id)
    claim = await claim_job(db, job_id)
    with pytest.raises(ValueError, match="not ready"):
        await acknowledge_delivery(db, user_id, order_id, "telegram:123")
    output_id = await process_pdf_merge(
        db, storage, "test", order_id, max_upload_bytes=20 * 1024 * 1024, retention_days=30,
    )
    await complete_job(db, claim, output_id)
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order_id) == "AWAITING_FULFILLMENT"
    assert await balance(db, user_id) == Balance(300, 700)
    output_key = await db.fetchval("SELECT storage_key FROM files WHERE id=$1", output_id)
    assert len(PdfReader(BytesIO(storage.objects[output_key])).pages) == 2
    delivery = await claim_delivery(db)
    assert delivery.order_id == order_id
    bot = FakeBot()
    receipt = await send_result(bot, db, storage, "test", delivery)
    assert receipt == f"telegram:{delivery.telegram_user_id}:42"
    assert len(PdfReader(BytesIO(bot.sent[0][1])).pages) == 2
    await finish_delivery(db, delivery, receipt)
    assert await claim_delivery(db) is None
    await acknowledge_delivery(db, user_id, order_id, receipt)
    with pytest.raises(IdempotencyConflict):
        await acknowledge_delivery(db, user_id, order_id, "telegram:another")
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order_id) == "COMPLETED"
    assert await db.fetchval("SELECT count(*) FROM jobs WHERE order_id=$1", order_id) == 1
    assert await db.fetchval(
        "SELECT count(*) FROM wallet_transactions WHERE order_id=$1 AND transaction_type='CAPTURE'",
        order_id,
    ) == 1
    assert await balance(db, user_id) == Balance(300, 0)


@pytest.mark.asyncio
async def test_invalid_pdf_releases_full_reservation(db, setup_order):
    user_id, service_id, storage, files = setup_order
    key = await db.fetchval("SELECT storage_key FROM files WHERE id=$1", files[1])
    storage.objects[key] = b"%PDF-not-a-real-file"
    # Persist the actual size so parsing (not the object-size guard) rejects this file.
    await db.execute("UPDATE files SET size_bytes=$2 WHERE id=$1", files[1], len(storage.objects[key]))
    await credit(db, user_id, 700, "payment:test")
    order_id = await confirm_order(db, user_id, service_id, "bad-pdf", file_ids=files)
    job_id = await db.fetchval("SELECT id FROM jobs WHERE order_id=$1", order_id)
    claim = await claim_job(db, job_id)
    with pytest.raises(InvalidPDF):
        await process_pdf_merge(
            db, storage, "test", order_id, max_upload_bytes=20 * 1024 * 1024,
            retention_days=30,
        )
    assert await fail_job(db, claim, "INVALID_INPUT", retryable=False)
    assert await balance(db, user_id) == Balance(700, 0)
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order_id) == "FAILED"


@pytest.mark.asyncio
async def test_active_pdf_releases_reservation_without_creating_output(db, setup_order):
    user_id, service_id, storage, files = setup_order
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_js("app.alert('not allowed')")
    stream = BytesIO()
    writer.write(stream)
    writer.close()
    key = await db.fetchval("SELECT storage_key FROM files WHERE id=$1", files[1])
    storage.objects[key] = stream.getvalue()
    await db.execute("UPDATE files SET size_bytes=$2 WHERE id=$1", files[1], len(stream.getvalue()))
    await credit(db, user_id, 700, "payment:policy")
    order_id = await confirm_order(db, user_id, service_id, "active-pdf", file_ids=files)
    claim = await claim_job(db, await db.fetchval("SELECT id FROM jobs WHERE order_id=$1", order_id))
    with pytest.raises(InvalidPDF):
        await process_pdf_merge(
            db, storage, "test", order_id, max_upload_bytes=20 * 1024 * 1024,
            retention_days=30,
        )
    await fail_job(db, claim, "INVALID_INPUT", retryable=False)
    assert await balance(db, user_id) == Balance(700, 0)
    assert await db.fetchval(
        "SELECT count(*) FROM files WHERE order_id=$1 AND file_type='OUTPUT'", order_id,
    ) == 0


@pytest.mark.asyncio
async def test_input_guard_rejects_cross_user_file_without_charging(db, setup_order):
    _, service_id, _, files = setup_order
    other_user = await ensure_telegram_user(db, uuid4().int % (2**63 - 1) + 1)
    await credit(db, other_user, 700, "payment:test")
    with pytest.raises(ValueError, match="input file"):
        await confirm_order(db, other_user, service_id, "foreign-inputs", file_ids=files)
    assert await db.fetchval("SELECT count(*) FROM orders WHERE user_id=$1", other_user) == 0
    assert await balance(db, other_user) == Balance(700, 0)


@pytest.mark.asyncio
async def test_delivery_retries_then_releases_on_exhaustion(db, setup_order):
    user_id, service_id, storage, files = setup_order
    await credit(db, user_id, 700, "payment:test")
    order_id = await confirm_order(db, user_id, service_id, "delivery-retry", file_ids=files)
    job_id = await db.fetchval("SELECT id FROM jobs WHERE order_id=$1", order_id)
    claim = await claim_job(db, job_id)
    output_id = await process_pdf_merge(
        db, storage, "test", order_id, max_upload_bytes=20 * 1024 * 1024, retention_days=30,
    )
    await complete_job(db, claim, output_id)
    for number in (1, 2, 3):
        delivery = await claim_delivery(db)
        assert delivery.attempt_number == number
        assert await claim_delivery(db) is None
        assert await fail_delivery(db, delivery, "NETWORK", retryable=True) is (number == 3)
        await db.execute(
            "UPDATE delivery_outbox SET next_attempt_at=now()-interval '1 second' WHERE id=$1",
            delivery.id,
        )
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order_id) == "FAILED"
    assert await db.fetchval(
        "SELECT status FROM delivery_outbox WHERE order_id=$1", order_id,
    ) == "FAILED"
    assert await balance(db, user_id) == Balance(700, 0)
    assert await claim_delivery(db) is None


@pytest.mark.asyncio
async def test_stale_delivery_is_retried_without_capture(db, setup_order):
    user_id, service_id, storage, files = setup_order
    await credit(db, user_id, 700, "payment:test")
    order_id = await confirm_order(db, user_id, service_id, "delivery-stale", file_ids=files)
    job_id = await db.fetchval("SELECT id FROM jobs WHERE order_id=$1", order_id)
    claim = await claim_job(db, job_id)
    output_id = await process_pdf_merge(
        db, storage, "test", order_id, max_upload_bytes=20 * 1024 * 1024, retention_days=30,
    )
    await complete_job(db, claim, output_id)
    delivery = await claim_delivery(db)
    await db.execute(
        "UPDATE delivery_outbox SET claimed_at=now()-interval '4 minutes' WHERE id=$1",
        delivery.id,
    )
    assert await recover_stale_deliveries(db) >= 1
    assert await balance(db, user_id) == Balance(0, 700)
    assert await db.fetchval(
        "SELECT status FROM delivery_outbox WHERE id=$1", delivery.id,
    ) == "PENDING"
