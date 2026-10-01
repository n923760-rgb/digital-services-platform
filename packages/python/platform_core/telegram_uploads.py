"""Bounded Telegram upload admission; no database transaction spans network I/O."""

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg

from platform_core.files import Storage
from platform_core.telegram_workflow import Workflow, attach_pdf

MAX_WORKFLOW_BYTES = 40 * 1024 * 1024
UPLOAD_INTENT_SECONDS = 3600


class UploadBusy(ValueError):
    pass


class UploadRejected(ValueError):
    pass


@dataclass(frozen=True)
class UploadAdmission:
    workflow_id: UUID
    byte_limit: int


@asynccontextmanager
async def upload_lock(connection: asyncpg.Connection, user_id: UUID):
    # Session lock covers admission, bounded download, storage and attach across bot processes.
    # Confirmation/cancellation remain free to run; attach checks the original workflow ID.
    key = f"telegram-upload:{user_id}"
    acquired = await connection.fetchval(
        "SELECT pg_try_advisory_lock(hashtextextended($1,0))", key,
    )
    if not acquired:
        raise UploadBusy("another upload is in progress")
    try:
        yield
    finally:
        await connection.fetchval("SELECT pg_advisory_unlock(hashtextextended($1,0))", key)
        # A disconnected/crashed session also releases this lock in PostgreSQL.


async def admit_pdf_upload(
    connection: asyncpg.Connection, user_id: UUID, declared_bytes: int,
    *, max_upload_bytes: int, max_user_upload_bytes: int,
) -> UploadAdmission:
    """Caller holds upload_lock; no bytes may download before this gate passes."""
    if (type(declared_bytes) is not int or declared_bytes < 1
            or max_upload_bytes < 1 or max_user_upload_bytes < 1):
        raise UploadRejected("invalid upload size or configuration")
    row = await connection.fetchrow(
        """SELECT w.id,s.input_schema FROM telegram_workflows w
           JOIN services s ON s.id=w.service_id
           JOIN service_categories c ON c.id=s.category_id
           WHERE w.user_id=$1 AND w.status IN ('COLLECTING','CONFIRMING')
           AND s.enabled=true AND c.enabled=true
           AND s.slug='merge-pdf' AND s.processor_type='tool'""", user_id,
    )
    if not row:
        raise UploadRejected("no available upload workflow")
    schema = row["input_schema"]
    if isinstance(schema, str):
        schema = json.loads(schema)
    maximum = schema.get("max_files") if isinstance(schema, dict) else None
    if type(maximum) is not int or not 2 <= maximum <= 10:
        raise UploadRejected("invalid file count policy")
    usage = await connection.fetchrow(
        """SELECT count(*) AS count,COALESCE(sum(f.size_bytes),0) AS bytes
           FROM telegram_workflow_files a JOIN files f ON f.id=a.file_id
           WHERE a.workflow_id=$1""", row["id"],
    )
    if usage["count"] >= maximum:
        raise UploadRejected("maximum number of files reached")
    retained_bytes = await connection.fetchval(
        """SELECT COALESCE(sum(size_bytes),0) FROM files
           WHERE owner_user_id=$1 AND file_type='INPUT'
           AND status<>'EXPIRED' AND retention_until>now()""", user_id,
    )
    limit = min(
        max_upload_bytes, MAX_WORKFLOW_BYTES - usage["bytes"],
        max_user_upload_bytes - retained_bytes,
    )
    if declared_bytes > limit:
        raise UploadRejected("upload byte budget exceeded")
    return UploadAdmission(row["id"], limit)


async def finish_pdf_upload(
    connection: asyncpg.Connection, user_id: UUID, file_id: UUID, message_id: int,
    admission: UploadAdmission, *, retention_days: int,
) -> Workflow:
    if not 1 <= retention_days <= 3650:
        raise UploadRejected("invalid retention")
    async with connection.transaction():
        workflow = await attach_pdf(
            connection, user_id, file_id, message_id,
            expected_workflow_id=admission.workflow_id,
        )
        attached = await connection.fetchval(
            """SELECT 1 FROM telegram_workflow_files
               WHERE workflow_id=$1 AND file_id=$2 AND telegram_message_id=$3""",
            admission.workflow_id, file_id, message_id,
        )
        if not attached:
            raise UploadRejected("upload was not attached")
        await connection.execute(
            "UPDATE files SET retention_until=$2 WHERE id=$1",
            file_id, datetime.now(UTC) + timedelta(days=retention_days),
        )
        return workflow


async def discard_unattached_input(
    connection: asyncpg.Connection, storage: Storage, bucket: str,
    user_id: UUID, file_id: UUID,
) -> bool:
    """Expire first, then delete; failed storage deletion remains visible to hourly cleanup."""
    async with connection.transaction():
        row = await connection.fetchrow(
            """SELECT f.storage_key FROM files f WHERE f.id=$1 AND f.owner_user_id=$2
               AND f.file_type='INPUT' AND f.order_id IS NULL AND f.status<>'EXPIRED'
               FOR UPDATE OF f""", file_id, user_id,
        )
        if not row:
            return False
        referenced = await connection.fetchval(
            """SELECT EXISTS (SELECT 1 FROM order_files WHERE file_id=$1)
               OR EXISTS (SELECT 1 FROM telegram_workflow_files WHERE file_id=$1)""", file_id,
        )
        if referenced:
            return False
        await connection.execute("UPDATE files SET retention_until=now() WHERE id=$1", file_id)
    await asyncio.to_thread(storage.delete_object, Bucket=bucket, Key=row["storage_key"])
    await connection.execute("UPDATE files SET status='EXPIRED' WHERE id=$1", file_id)
    return True
