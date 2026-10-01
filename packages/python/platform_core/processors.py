"""Service processor adapters; Telegram and order state do not depend on a specific tool."""

import asyncio
from uuid import UUID

import asyncpg

from platform_core.files import Storage, read_file, upload_file
from platform_core.pdf_isolation import MAX_INPUT_BYTES, merge_pdfs_isolated
from platform_core.pdf_merge import InvalidPDF
from platform_core.pdf_sandbox_client import merge_pdfs_in_sandbox


async def process_pdf_merge(
    connection: asyncpg.Connection, storage: Storage, bucket: str,
    order_id: UUID, *, max_upload_bytes: int, retention_days: int,
    sandbox_root: str | None = None,
) -> UUID:
    if type(max_upload_bytes) is not int or max_upload_bytes < 1:
        raise ValueError("invalid processor byte limit")
    order = await connection.fetchrow("SELECT user_id FROM orders WHERE id=$1", order_id)
    if not order:
        raise ValueError("order missing")
    rows = await connection.fetch(
        """SELECT f.id,f.size_bytes,
           (f.owner_user_id=$2 AND f.file_type='INPUT' AND f.mime_type='application/pdf'
            AND f.status='READY' AND f.retention_until>now()) AS available
           FROM order_files o JOIN files f ON f.id=o.file_id
           WHERE o.order_id=$1 ORDER BY o.position LIMIT 11""",
        order_id, order["user_id"],
    )
    if not 2 <= len(rows) <= 10:
        raise ValueError("PDF input count invalid")
    # Reject all known oversized/unavailable inputs before even a storage HEAD/GET.
    if any(not row["available"] for row in rows):
        raise ValueError("PDF input unavailable or wrong type")
    if (any(not 0 < row["size_bytes"] <= max_upload_bytes for row in rows)
            or sum(row["size_bytes"] for row in rows) > MAX_INPUT_BYTES):
        raise InvalidPDF("PDF input byte budget exceeded")
    documents = []
    remaining = MAX_INPUT_BYTES
    for row in rows:
        # Recheck current ownership/readiness/expiry and size before each bounded GET.
        # Metadata may change after the aggregate preflight; never expand this budget.
        document = await read_file(
            connection, storage, bucket, order["user_id"], row["id"],
            max_bytes=min(max_upload_bytes, remaining),
        )
        remaining -= len(document)
        documents.append(document)
    if sandbox_root is None:
        # Direct internal callers/tests can use the local bounded subprocess.
        result = await asyncio.to_thread(merge_pdfs_isolated, documents)
    else:
        result = await asyncio.to_thread(merge_pdfs_in_sandbox, documents, sandbox_root)
    record = await upload_file(
        connection, storage, bucket, order["user_id"], "merged.pdf", "application/pdf",
        result, order_id=order_id, file_type="OUTPUT", limit=max_upload_bytes,
        retention_days=retention_days,
    )
    return record.id


PROCESSORS = {"merge-pdf": process_pdf_merge}
