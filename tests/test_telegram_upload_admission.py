"""Real PostgreSQL upload limits/races, with bounded fake Telegram and object storage."""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import pytest
from platform_core.files import cleanup_expired_files, upload_file
from platform_core.orders import ensure_telegram_user
from platform_core.telegram_uploads import (
    UploadBusy,
    UploadRejected,
    admit_pdf_upload,
    discard_unattached_input,
    finish_pdf_upload,
    upload_lock,
)
from platform_core.telegram_workflow import (
    active_workflow,
    attach_pdf,
    cancel_active,
    start_pdf_merge,
)

from apps.telegram_bot import pdf_workflow

DATA = b"%PDF-upload-test"


class MemoryStorage:
    def __init__(self):
        self.objects = {}
        self.fail_delete = False

    def put_object(self, *, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body

    def delete_object(self, *, Bucket, Key):
        if self.fail_delete:
            raise OSError("storage deletion unavailable")
        self.objects.pop(Key, None)


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
    await db.execute(
        """UPDATE services SET enabled=true,input_schema=$1::jsonb WHERE slug='merge-pdf'""",
        '{"min_files":2,"max_files":10,"file_mime":"application/pdf"}',
    )
    telegram_id = uuid4().int % (2**63 - 1) + 1
    user_id = await ensure_telegram_user(db, telegram_id)
    workflow = await start_pdf_merge(db, user_id)
    return user_id, telegram_id, workflow, MemoryStorage()


async def seed_inputs(db, user_id, storage, count):
    for index in range(count):
        record = await upload_file(
            db, storage, "test", user_id, f"seed-{index}.pdf", "application/pdf", DATA,
        )
        await attach_pdf(db, user_id, record.id, 100 + index)


def configure_handler(monkeypatch, telegram_id, storage, *, budget=100 * 1024 * 1024):
    original_connect = asyncpg.connect
    test_url = os.environ["DATABASE_URL"].replace("+asyncpg", "")

    async def connect(_url):
        return await original_connect(test_url)

    monkeypatch.setattr(pdf_workflow.asyncpg, "connect", connect)
    monkeypatch.setattr(pdf_workflow, "storage_client", lambda: storage)
    monkeypatch.setattr(pdf_workflow, "settings", SimpleNamespace(
        telegram_orders_enabled=True, telegram_stars_enabled=True,
        telegram_payment_terms="Synthetic purchase terms", telegram_payment_support="Synthetic support", database_url=test_url,
        max_upload_bytes=20 * 1024 * 1024, max_user_upload_bytes=budget,
        object_storage_bucket="test", file_retention_days=30,
    ))
    return SimpleNamespace(
        from_user=SimpleNamespace(id=telegram_id), message_id=500,
        document=SimpleNamespace(file_size=len(DATA), file_name="new.pdf",
                                 mime_type="application/pdf"),
        answer=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_full_workflow_never_downloads_or_persists_an_extra_file(db, prepared, monkeypatch):
    user_id, telegram_id, workflow, storage = prepared
    await seed_inputs(db, user_id, storage, 10)
    message = configure_handler(monkeypatch, telegram_id, storage)
    bot = SimpleNamespace(download=AsyncMock())
    await pdf_workflow.upload(message, bot)
    bot.download.assert_not_awaited()
    assert (await active_workflow(db, user_id)).id == workflow.id
    assert await db.fetchval("SELECT count(*) FROM files WHERE owner_user_id=$1", user_id) == 10
    assert len(storage.objects) == 10


@pytest.mark.asyncio
async def test_simultaneous_last_slot_upload_is_rejected_before_download(db, prepared, monkeypatch):
    user_id, telegram_id, workflow, storage = prepared
    await seed_inputs(db, user_id, storage, 9)
    first = configure_handler(monkeypatch, telegram_id, storage)
    second = SimpleNamespace(**vars(first))
    second.message_id = 501
    second.answer = AsyncMock()
    entered, release = asyncio.Event(), asyncio.Event()

    async def download(_document, *, destination):
        entered.set()
        await release.wait()
        destination.write(DATA)

    bot = SimpleNamespace(download=AsyncMock(side_effect=download))
    first_task = asyncio.create_task(pdf_workflow.upload(first, bot))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        await pdf_workflow.upload(second, bot)
        assert bot.download.await_count == 1
        assert "جارٍ رفع" in second.answer.await_args.args[0]
    finally:
        release.set()
        await first_task
    assert await db.fetchval(
        "SELECT count(*) FROM telegram_workflow_files WHERE workflow_id=$1", workflow.id,
    ) == 10
    assert len(storage.objects) == 10
    assert await db.fetchval("SELECT count(*) FROM files WHERE owner_user_id=$1", user_id) == 10


@pytest.mark.asyncio
async def test_cancel_and_replace_during_download_cannot_receive_old_input(db, prepared, monkeypatch):
    user_id, telegram_id, old_workflow, storage = prepared
    message = configure_handler(monkeypatch, telegram_id, storage)

    async def download(_document, *, destination):
        assert await cancel_active(db, user_id)
        await start_pdf_merge(db, user_id)
        destination.write(DATA)

    await pdf_workflow.upload(message, SimpleNamespace(download=AsyncMock(side_effect=download)))
    current = await active_workflow(db, user_id)
    assert current.id != old_workflow.id and current.file_count == 0
    assert len(storage.objects) == 0
    assert await db.fetchval("SELECT status FROM files WHERE owner_user_id=$1", user_id) == "EXPIRED"
    assert await db.fetchval(
        "SELECT count(*) FROM telegram_workflow_files WHERE workflow_id=$1", current.id,
    ) == 0


@pytest.mark.asyncio
async def test_duplicate_message_does_not_upload_again(db, prepared, monkeypatch):
    user_id, telegram_id, _, storage = prepared
    message = configure_handler(monkeypatch, telegram_id, storage)

    async def download(_document, *, destination):
        destination.write(DATA)

    bot = SimpleNamespace(download=AsyncMock(side_effect=download))
    await pdf_workflow.upload(message, bot)
    await pdf_workflow.upload(message, bot)
    assert bot.download.await_count == 1
    assert len(storage.objects) == 1
    assert (await active_workflow(db, user_id)).file_count == 1


@pytest.mark.asyncio
async def test_declared_size_cannot_bypass_actual_stream_budget(db, prepared, monkeypatch):
    user_id, telegram_id, _, storage = prepared
    message = configure_handler(monkeypatch, telegram_id, storage, budget=len(DATA) - 1)
    message.document.file_size = 1

    async def download(_document, *, destination):
        destination.write(DATA)

    await pdf_workflow.upload(message, SimpleNamespace(download=AsyncMock(side_effect=download)))
    assert len(storage.objects) == 0
    assert await db.fetchval("SELECT count(*) FROM files WHERE owner_user_id=$1", user_id) == 0


@pytest.mark.asyncio
async def test_user_budget_counts_retained_inputs_from_cancelled_workflows(db, prepared, monkeypatch):
    user_id, telegram_id, _, storage = prepared
    await seed_inputs(db, user_id, storage, 2)
    assert await cancel_active(db, user_id)
    await start_pdf_merge(db, user_id)
    message = configure_handler(monkeypatch, telegram_id, storage, budget=2 * len(DATA))
    bot = SimpleNamespace(download=AsyncMock())
    await pdf_workflow.upload(message, bot)
    bot.download.assert_not_awaited()
    assert len(storage.objects) == 2


@pytest.mark.asyncio
async def test_workflow_total_bytes_rejected_before_download(db, prepared, monkeypatch):
    user_id, telegram_id, _, storage = prepared
    await seed_inputs(db, user_id, storage, 2)
    await db.execute(
        "UPDATE files SET size_bytes=20971520 WHERE owner_user_id=$1", user_id,
    )
    message = configure_handler(monkeypatch, telegram_id, storage)
    bot = SimpleNamespace(download=AsyncMock())
    await pdf_workflow.upload(message, bot)
    bot.download.assert_not_awaited()
    assert len(storage.objects) == 2


@pytest.mark.asyncio
async def test_upload_lock_is_per_customer_and_released_after_error(db, prepared):
    user_id, _, _, _ = prepared
    other = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    try:
        with pytest.raises(RuntimeError):
            async with upload_lock(db, user_id):
                with pytest.raises(UploadBusy):
                    async with upload_lock(other, user_id):
                        raise AssertionError("must not acquire competing upload")
                async with upload_lock(other, uuid4()):
                    pass
                raise RuntimeError("simulated handler failure")
        async with upload_lock(other, user_id):
            pass
    finally:
        await other.close()


@pytest.mark.asyncio
async def test_crashed_or_failed_intent_expires_and_cleanup_retries_storage(db, prepared):
    user_id, _, _, storage = prepared
    record = await upload_file(
        db, storage, "test", user_id, "pending.pdf", "application/pdf", DATA,
        intent_retention_seconds=3600,
    )
    remaining = await db.fetchval(
        "SELECT extract(epoch FROM retention_until-now()) FROM files WHERE id=$1", record.id,
    )
    assert 0 < remaining <= 3600
    storage.fail_delete = True
    with pytest.raises(OSError):
        await discard_unattached_input(db, storage, "test", user_id, record.id)
    assert await db.fetchval("SELECT retention_until<=now() FROM files WHERE id=$1", record.id)
    assert record.storage_key in storage.objects
    storage.fail_delete = False
    await cleanup_expired_files(db, storage, "test")
    assert record.storage_key not in storage.objects
    assert await db.fetchval("SELECT status FROM files WHERE id=$1", record.id) == "EXPIRED"


@pytest.mark.asyncio
async def test_finalize_extends_retention_and_never_discards_attached_file(db, prepared):
    user_id, _, _, storage = prepared
    async with upload_lock(db, user_id):
        admission = await admit_pdf_upload(
            db, user_id, len(DATA), max_upload_bytes=1024, max_user_upload_bytes=4096,
        )
        record = await upload_file(
            db, storage, "test", user_id, "new.pdf", "application/pdf", DATA,
            intent_retention_seconds=3600,
        )
        await finish_pdf_upload(db, user_id, record.id, 900, admission, retention_days=30)
    assert await db.fetchval(
        "SELECT retention_until>now()+interval '29 days' FROM files WHERE id=$1", record.id,
    )
    assert not await discard_unattached_input(db, storage, "test", user_id, record.id)
    assert record.storage_key in storage.objects


@pytest.mark.asyncio
async def test_invalid_admission_and_disabled_service_fail_closed(db, prepared):
    user_id, _, _, _ = prepared
    with pytest.raises(UploadRejected):
        await admit_pdf_upload(
            db, user_id, 0, max_upload_bytes=1024, max_user_upload_bytes=4096,
        )
    await db.execute("UPDATE services SET enabled=false WHERE slug='merge-pdf'")
    with pytest.raises(UploadRejected):
        await admit_pdf_upload(
            db, user_id, 10, max_upload_bytes=1024, max_user_upload_bytes=4096,
        )
