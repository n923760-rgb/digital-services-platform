"""Validate types before upload, track failures and block expired/missing objects."""

import os
from uuid import uuid4

import asyncpg
import pytest
from platform_core.files import (
    FileUnavailable,
    InvalidFile,
    cleanup_expired_files,
    identify,
    upload_file,
    verify_file,
)
from platform_core.orders import ensure_telegram_user

PNG = b"\x89PNG\r\n\x1a\n" + b"test-bytes"


class FakeStorage:
    def __init__(self):
        self.objects = {}
        self.fail = False

    def put_object(self, *, Bucket, Key, Body, ContentType):
        if self.fail:
            raise OSError("storage unavailable")
        self.objects[Key] = Body

    def head_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise FileNotFoundError(Key)
        return {"ContentLength": len(self.objects[Key])}

    def delete_object(self, *, Bucket, Key):
        self.objects.pop(Key, None)


@pytest.fixture
async def db():
    connection = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    try:
        yield connection
    finally:
        await connection.close()


@pytest.mark.parametrize(
    "name,mime,data,limit",
    [
        ("a.exe", "application/octet-stream", PNG, 1024),
        ("a.jpg", "image/jpeg", PNG, 1024),
        ("a.png", "image/jpeg", PNG, 1024),
        ("../a.png", "image/png", PNG, 1024),
        ("a.png", "image/png", b"", 1024),
        ("a.png", "image/png", PNG, 4),
    ],
)
def test_upload_validation_rejects_unsafe_input(name, mime, data, limit):
    with pytest.raises(InvalidFile):
        identify(data, name, mime, limit)


@pytest.mark.asyncio
async def test_valid_upload_and_missing_or_expired_object(db):
    user_id = await ensure_telegram_user(db, uuid4().int % (2**63 - 1) + 1)
    storage = FakeStorage()
    record = await upload_file(db, storage, "test", user_id, "صورة.png", "image/png", PNG)
    assert await verify_file(db, storage, "test", user_id, record.id) == record
    with pytest.raises(FileUnavailable):
        await verify_file(db, storage, "test", uuid4(), record.id)
    storage.objects.clear()
    with pytest.raises(FileUnavailable, match="missing"):
        await verify_file(db, storage, "test", user_id, record.id)
    storage.objects[record.storage_key] = PNG
    await db.execute("UPDATE files SET retention_until=now()-interval '1 second' WHERE id=$1", record.id)
    with pytest.raises(FileUnavailable, match="expired"):
        await verify_file(db, storage, "test", user_id, record.id)
    assert await cleanup_expired_files(db, storage, "test") >= 1
    assert record.storage_key not in storage.objects
    assert await db.fetchval("SELECT status FROM files WHERE id=$1", record.id) == "EXPIRED"


@pytest.mark.asyncio
async def test_failed_storage_write_keeps_visible_failure(db):
    user_id = await ensure_telegram_user(db, uuid4().int % (2**63 - 1) + 1)
    storage = FakeStorage()
    storage.fail = True
    with pytest.raises(OSError, match="unavailable"):
        await upload_file(db, storage, "test", user_id, "image.png", "image/png", PNG)
    assert await db.fetchval(
        "SELECT status FROM files WHERE owner_user_id=$1", user_id,
    ) == "FAILED"
