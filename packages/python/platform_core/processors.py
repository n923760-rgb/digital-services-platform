"""Service processor adapters; Telegram and order state do not depend on a specific tool."""

import asyncio
from uuid import UUID

import asyncpg

from platform_core.files import Storage, read_file, upload_file
from platform_core.pdf_isolation import merge_pdfs_isolated


async def process_pdf_merge(
    connection: asyncpg.Connection, storage: Storage, bucket: str,
    order_id: UUID, *, max_upload_bytes: int, retention_days: int,
) -> UUID:
    order = await connection.fetchrow("SELECT user_id FROM orders WHERE id=$1", order_id)
    if not order:
        raise ValueError("order missing")
    rows = await connection.fetch(
        """SELECT f.id FROM order_files o JOIN files f ON f.id=o.file_id
           WHERE o.order_id=$1 AND f.mime_type='application/pdf'
           ORDER BY o.position""",
        order_id,
    )
    if not 2 <= len(rows) <= 10:
        raise ValueError("PDF input count invalid")
    documents = [
        await read_file(connection, storage, bucket, order["user_id"], row["id"])
        for row in rows
    ]
    result = await asyncio.to_thread(merge_pdfs_isolated, documents)
    record = await upload_file(
        connection, storage, bucket, order["user_id"], "merged.pdf", "application/pdf",
        result, order_id=order_id, file_type="OUTPUT", limit=max_upload_bytes,
        retention_days=retention_days,
    )
    return record.id


PROCESSORS = {"merge-pdf": process_pdf_merge}
