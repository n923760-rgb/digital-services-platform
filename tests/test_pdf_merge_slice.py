"""Proof of the internal file → wallet → order → job → quality → delivery flow."""

import os
from io import BytesIO
from uuid import uuid4

import asyncpg
import pytest
from pypdf import PdfReader, PdfWriter

from platform_core.files import upload_file
from platform_core.jobs import claim_job, complete_job, fail_job
from platform_core.ledger import Balance, IdempotencyConflict, balance, credit
from platform_core.orders import acknowledge_delivery, confirm_order, ensure_telegram_user
from platform_core.pdf_merge import InvalidPDF, merge_pdfs
from platform_core.processors import process_pdf_merge


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
    await acknowledge_delivery(db, user_id, order_id, "telegram:123")
    await acknowledge_delivery(db, user_id, order_id, "telegram:123")
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
async def test_input_guard_rejects_cross_user_file_without_charging(db, setup_order):
    user_id, service_id, _, files = setup_order
    other_user = await ensure_telegram_user(db, uuid4().int % (2**63 - 1) + 1)
    await credit(db, other_user, 700, "payment:test")
    with pytest.raises(ValueError, match="input file"):
        await confirm_order(db, other_user, service_id, "foreign-inputs", file_ids=files)
    assert await db.fetchval("SELECT count(*) FROM orders WHERE user_id=$1", other_user) == 0
    assert await balance(db, other_user) == Balance(700, 0)
