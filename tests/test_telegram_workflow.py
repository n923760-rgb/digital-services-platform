"""Database-backed Telegram resume, price quote and duplicate-click invariants."""

import asyncio
import os
from uuid import uuid4

import asyncpg
import pytest
from platform_core.files import InvalidFile, upload_file
from platform_core.ledger import Balance, balance, credit
from platform_core.orders import ensure_telegram_user
from platform_core.telegram_workflow import (
    active_workflow,
    attach_pdf,
    cancel_active,
    confirm_pdf_merge,
    has_upload,
    quote_pdf_merge,
    start_pdf_merge,
)

from apps.telegram_bot.pdf_workflow import BoundedBuffer


class MemoryStorage:
    def __init__(self):
        self.objects = {}

    def put_object(self, *, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body


@pytest.fixture
async def db():
    connection = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    try:
        yield connection
    finally:
        await connection.close()


@pytest.fixture
async def prepared(db):
    category_id, proposed_id = uuid4(), uuid4()
    await db.execute(
        "INSERT INTO service_categories (id,slug,name_ar) VALUES ($1,$2,'أدوات')",
        category_id, str(category_id),
    )
    await db.execute(
        """INSERT INTO services
           (id,category_id,slug,name_ar,processor_type,base_price_halalas,input_schema,enabled)
           VALUES ($1,$2,'merge-pdf','دمج PDF','tool',700,$3::jsonb,true)
           ON CONFLICT (slug) DO NOTHING""",
        proposed_id, category_id,
        '{"min_files":2,"max_files":10,"file_mime":"application/pdf"}',
    )
    service_id = await db.fetchval("SELECT id FROM services WHERE slug='merge-pdf'")
    await db.execute(
        """UPDATE services SET enabled=true,base_price_halalas=700,
           input_schema=$2::jsonb WHERE id=$1""",
        service_id, '{"min_files":2,"max_files":10,"file_mime":"application/pdf"}',
    )
    user_id = await ensure_telegram_user(db, uuid4().int % (2**63 - 1) + 1)
    storage = MemoryStorage()
    files = [
        (await upload_file(db, storage, "test", user_id, f"file-{i}.pdf",
                           "application/pdf", b"%PDF-fake-test-input")).id
        for i in (1, 2)
    ]
    return user_id, service_id, files


def test_streaming_buffer_enforces_limit():
    buffer = BoundedBuffer(5)
    assert buffer.write(b"abc") == 3
    with pytest.raises(InvalidFile):
        buffer.write(b"def")
    assert buffer.getvalue() == b"abc"


@pytest.mark.asyncio
async def test_resume_upload_quote_reprice_and_confirm(db, prepared):
    user_id, service_id, files = prepared
    workflow = await start_pdf_merge(db, user_id)
    assert await start_pdf_merge(db, user_id) == workflow
    with pytest.raises(ValueError, match="more PDF"):
        await quote_pdf_merge(db, user_id)
    one = await attach_pdf(db, user_id, files[0], 101)
    assert one.file_count == 1
    assert await attach_pdf(db, user_id, files[0], 101) == one
    assert await has_upload(db, user_id, 101)
    two = await attach_pdf(db, user_id, files[1], 102)
    assert two.file_count == 2
    assert (await active_workflow(db, user_id)).id == workflow.id
    quote = await quote_pdf_merge(db, user_id)
    assert quote.quoted_price_halalas == 700
    await credit(db, user_id, 800, "payment:test")
    await db.execute("UPDATE services SET base_price_halalas=800 WHERE id=$1", service_id)
    with pytest.raises(ValueError, match="price changed"):
        await confirm_pdf_merge(db, user_id, workflow.id)
    assert await db.fetchval("SELECT count(*) FROM orders WHERE user_id=$1", user_id) == 0
    quote = await quote_pdf_merge(db, user_id)
    assert quote.quoted_price_halalas == 800
    order_id = await confirm_pdf_merge(db, user_id, workflow.id)
    assert await confirm_pdf_merge(db, user_id, workflow.id) == order_id
    assert await balance(db, user_id) == Balance(0, 800)
    assert await db.fetchval("SELECT count(*) FROM jobs WHERE order_id=$1", order_id) == 1
    assert await db.fetchval(
        "SELECT price_snapshot_halalas FROM orders WHERE id=$1", order_id,
    ) == 800
    assert await active_workflow(db, user_id) is None
    assert (await start_pdf_merge(db, user_id)).id != workflow.id
    assert await cancel_active(db, user_id)
    assert await active_workflow(db, user_id) is None


@pytest.mark.asyncio
async def test_concurrent_confirmation_one_order(db, prepared):
    user_id, _, files = prepared
    workflow = await start_pdf_merge(db, user_id)
    for index, file_id in enumerate(files, start=201):
        await attach_pdf(db, user_id, file_id, index)
    await quote_pdf_merge(db, user_id)
    await credit(db, user_id, 700, "payment:test")
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "")

    async def confirm():
        connection = await asyncpg.connect(url)
        try:
            return await confirm_pdf_merge(connection, user_id, workflow.id)
        finally:
            await connection.close()

    first, second = await asyncio.gather(confirm(), confirm())
    assert first == second
    assert await db.fetchval("SELECT count(*) FROM orders WHERE user_id=$1", user_id) == 1
    assert await balance(db, user_id) == Balance(0, 700)
