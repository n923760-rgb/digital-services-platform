"""Validated file metadata and S3 adapter boundary; no public upload endpoint yet."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Protocol
from uuid import UUID, uuid4

import asyncpg


class Storage(Protocol):
    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> object: ...
    def read_object(self, *, Bucket: str, Key: str, MaxBytes: int) -> bytes: ...
    def head_object(self, *, Bucket: str, Key: str) -> object: ...
    def delete_object(self, *, Bucket: str, Key: str) -> object: ...


class InvalidFile(ValueError):
    pass


class FileUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class FileRecord:
    id: UUID
    storage_key: str
    mime_type: str
    size_bytes: int


def identify(data: bytes, name: str, claimed_mime: str, limit: int) -> str:
    if not name or len(name) > 200 or name != PurePosixPath(name.replace("\\", "/")).name:
        raise InvalidFile("invalid file name")
    if limit < 1 or not 0 < len(data) <= limit:
        raise InvalidFile("file is empty or exceeds the size limit")
    suffix = PurePosixPath(name).suffix.lower()
    signatures = {
        ".pdf": ("application/pdf", data.startswith(b"%PDF-")),
        ".png": ("image/png", data.startswith(b"\x89PNG\r\n\x1a\n")),
        ".jpg": ("image/jpeg", data.startswith(b"\xff\xd8\xff")),
        ".jpeg": ("image/jpeg", data.startswith(b"\xff\xd8\xff")),
        ".webp": ("image/webp", data.startswith(b"RIFF") and data[8:12] == b"WEBP"),
    }
    expected = signatures.get(suffix)
    if expected is None or not expected[1] or claimed_mime.lower() != expected[0]:
        raise InvalidFile("unsupported file or mismatched type")
    return expected[0]


async def upload_file(
    connection: asyncpg.Connection, storage: Storage, bucket: str,
    owner_user_id: UUID, file_name: str, claimed_mime: str, data: bytes,
    *, order_id: UUID | None = None, file_type: str = "INPUT",
    limit: int = 20 * 1024 * 1024, retention_days: int = 30,
) -> FileRecord:
    mime = identify(data, file_name, claimed_mime, limit)
    if file_type not in {"INPUT", "OUTPUT"} or not 1 <= retention_days <= 3650:
        raise InvalidFile("invalid retention or file type")
    if order_id is not None:
        owner = await connection.fetchval("SELECT user_id FROM orders WHERE id=$1", order_id)
        if owner != owner_user_id:
            raise InvalidFile("file order does not belong to owner")
    file_id = uuid4()
    key = f"users/{owner_user_id}/{file_id}{PurePosixPath(file_name).suffix.lower()}"
    expires = datetime.now(UTC) + timedelta(days=retention_days)
    # An intent row survives object-storage failure; a later cleanup can inspect FAILED rows.
    await connection.execute(
        """INSERT INTO files
           (id,owner_user_id,order_id,storage_key,file_name,mime_type,size_bytes,
            file_type,status,retention_until)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'UPLOADING',$9)""",
        file_id, owner_user_id, order_id, key, file_name, mime, len(data), file_type, expires,
    )
    try:
        await asyncio.to_thread(
            storage.put_object, Bucket=bucket, Key=key, Body=data, ContentType=mime,
        )
    except Exception:
        await connection.execute("UPDATE files SET status='FAILED' WHERE id=$1", file_id)
        raise
    await connection.execute("UPDATE files SET status='READY' WHERE id=$1", file_id)
    return FileRecord(file_id, key, mime, len(data))


async def verify_file(
    connection: asyncpg.Connection, storage: Storage, bucket: str,
    owner_user_id: UUID, file_id: UUID,
) -> FileRecord:
    row = await connection.fetchrow(
        """SELECT storage_key,mime_type,size_bytes FROM files
           WHERE id=$1 AND owner_user_id=$2 AND status='READY' AND retention_until>now()""",
        file_id, owner_user_id,
    )
    if not row:
        raise FileUnavailable("file unavailable or expired")
    try:
        response = await asyncio.to_thread(
            storage.head_object, Bucket=bucket, Key=row["storage_key"],
        )
    except FileNotFoundError as exc:
        raise FileUnavailable("object missing from storage") from exc
    if response["ContentLength"] != row["size_bytes"]:
        raise FileUnavailable("stored object size differs from metadata")
    return FileRecord(file_id, row["storage_key"], row["mime_type"], row["size_bytes"])


async def read_file(
    connection: asyncpg.Connection, storage: Storage, bucket: str,
    owner_user_id: UUID, file_id: UUID,
) -> bytes:
    record = await verify_file(connection, storage, bucket, owner_user_id, file_id)
    try:
        data = await asyncio.to_thread(
            storage.read_object, Bucket=bucket, Key=record.storage_key,
            MaxBytes=record.size_bytes,
        )
    except FileNotFoundError as exc:
        raise FileUnavailable("object missing from storage") from exc
    if len(data) != record.size_bytes:
        raise FileUnavailable("stored object changed during download")
    return data


async def cleanup_expired_files(connection: asyncpg.Connection, storage: Storage, bucket: str) -> int:
    """Delete expired objects before marking metadata expired; failures remain retryable."""
    async with connection.transaction():
        rows = await connection.fetch(
            """SELECT id,storage_key FROM files WHERE status <> 'EXPIRED'
               AND retention_until<=now() ORDER BY retention_until LIMIT 100
               FOR UPDATE SKIP LOCKED""",
        )
        for row in rows:
            await asyncio.to_thread(storage.delete_object, Bucket=bucket, Key=row["storage_key"])
            await connection.execute("UPDATE files SET status='EXPIRED' WHERE id=$1", row["id"])
        return len(rows)
