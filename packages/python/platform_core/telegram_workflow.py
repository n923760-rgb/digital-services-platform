"""Channel state backed by PostgreSQL; business and pricing stay in application services."""

import json
from dataclasses import dataclass
from uuid import UUID, uuid4

import asyncpg

from platform_core.ledger import _lock_wallet
from platform_core.orders import confirm_order


class StaleQuote(ValueError):
    pass


@dataclass(frozen=True)
class Workflow:
    id: UUID
    status: str
    file_count: int
    quoted_price_halalas: int | None
    quote_revision: int = 0


async def active_workflow(connection: asyncpg.Connection, user_id: UUID) -> Workflow | None:
    row = await connection.fetchrow(
        """SELECT w.id,w.status,w.quoted_price_halalas,w.quote_revision,
           (SELECT count(*) FROM telegram_workflow_files f WHERE f.workflow_id=w.id) AS file_count
           FROM telegram_workflows w WHERE w.user_id=$1
           AND w.status IN ('COLLECTING','CONFIRMING')""",
        user_id,
    )
    if not row:
        return None
    return Workflow(
        row["id"], row["status"], row["file_count"], row["quoted_price_halalas"],
        row["quote_revision"],
    )


async def start_pdf_merge(connection: asyncpg.Connection, user_id: UUID) -> Workflow:
    async with connection.transaction():
        await _lock_wallet(connection, user_id)
        active = await active_workflow(connection, user_id)
        if active:
            return active
        service_id = await connection.fetchval(
            """SELECT s.id FROM services s JOIN service_categories c ON c.id=s.category_id
               WHERE s.slug='merge-pdf' AND s.processor_type='tool'
               AND s.enabled=true AND c.enabled=true""",
        )
        if not service_id:
            raise ValueError("PDF merge service is unavailable")
        workflow_id = uuid4()
        await connection.execute(
            """INSERT INTO telegram_workflows (id,user_id,service_id,status)
               VALUES ($1,$2,$3,'COLLECTING')""",
            workflow_id, user_id, service_id,
        )
        return Workflow(workflow_id, "COLLECTING", 0, None)


async def has_upload(
    connection: asyncpg.Connection, user_id: UUID, telegram_message_id: int,
) -> bool:
    return bool(await connection.fetchval(
        """SELECT 1 FROM telegram_workflow_files f JOIN telegram_workflows w
           ON w.id=f.workflow_id WHERE w.user_id=$1 AND f.telegram_message_id=$2""",
        user_id, telegram_message_id,
    ))


async def attach_pdf(
    connection: asyncpg.Connection, user_id: UUID, file_id: UUID, telegram_message_id: int,
    *, expected_workflow_id: UUID | None = None,
) -> Workflow:
    if telegram_message_id <= 0:
        raise ValueError("invalid Telegram message ID")
    async with connection.transaction():
        row = await connection.fetchrow(
            """SELECT w.id,w.status,w.quote_revision,s.input_schema FROM telegram_workflows w
               JOIN services s ON s.id=w.service_id WHERE w.user_id=$1
               AND w.status IN ('COLLECTING','CONFIRMING') FOR UPDATE OF w""",
            user_id,
        )
        if not row or (expected_workflow_id is not None and row["id"] != expected_workflow_id):
            raise ValueError("no matching active file workflow")
        existing = await connection.fetchval(
            """SELECT file_id FROM telegram_workflow_files
               WHERE workflow_id=$1 AND telegram_message_id=$2""",
            row["id"], telegram_message_id,
        )
        if existing:
            return await active_workflow(connection, user_id)
        schema = row["input_schema"]
        if isinstance(schema, str):
            schema = json.loads(schema)
        limit = schema.get("max_files", 0)
        count = await connection.fetchval(
            "SELECT count(*) FROM telegram_workflow_files WHERE workflow_id=$1", row["id"],
        )
        if not isinstance(limit, int) or not 1 <= limit <= 20 or count >= limit:
            raise ValueError("maximum number of files reached")
        valid = await connection.fetchval(
            """SELECT 1 FROM files WHERE id=$1 AND owner_user_id=$2
               AND file_type='INPUT' AND mime_type='application/pdf'
               AND status='READY' AND retention_until>now() FOR UPDATE""",
            file_id, user_id,
        )
        if not valid:
            raise ValueError("invalid PDF attachment")
        await connection.execute(
            """INSERT INTO telegram_workflow_files
               (workflow_id,position,telegram_message_id,file_id) VALUES ($1,$2,$3,$4)""",
            row["id"], count, telegram_message_id, file_id,
        )
        await connection.execute(
            """UPDATE telegram_workflows SET status='COLLECTING',quoted_price_halalas=NULL,
               quote_revision=quote_revision+1,updated_at=now() WHERE id=$1""", row["id"],
        )
        return Workflow(row["id"], "COLLECTING", count + 1, None, row["quote_revision"] + 1)


async def quote_pdf_merge(connection: asyncpg.Connection, user_id: UUID) -> Workflow:
    async with connection.transaction():
        row = await connection.fetchrow(
            """SELECT w.id,s.base_price_halalas,s.input_schema FROM telegram_workflows w
               JOIN services s ON s.id=w.service_id JOIN service_categories c ON c.id=s.category_id
               WHERE w.user_id=$1 AND w.status IN ('COLLECTING','CONFIRMING')
               AND s.enabled=true AND c.enabled=true FOR UPDATE OF w""",
            user_id,
        )
        if not row:
            raise ValueError("service or workflow unavailable")
        schema = row["input_schema"]
        if isinstance(schema, str):
            schema = json.loads(schema)
        count = await connection.fetchval(
            "SELECT count(*) FROM telegram_workflow_files WHERE workflow_id=$1", row["id"],
        )
        if not schema.get("min_files", 0) <= count <= schema.get("max_files", 0):
            raise ValueError("more PDF files are required")
        price = row["base_price_halalas"]
        revision = await connection.fetchval(
            """UPDATE telegram_workflows SET status='CONFIRMING',quoted_price_halalas=$2,
               quote_revision=quote_revision+1,updated_at=now() WHERE id=$1
               RETURNING quote_revision""",
            row["id"], price,
        )
        return Workflow(row["id"], "CONFIRMING", count, price, revision)


async def confirm_pdf_merge(
    connection: asyncpg.Connection, user_id: UUID, workflow_id: UUID,
    *, expected_quote_revision: int,
) -> UUID:
    if type(expected_quote_revision) is not int or expected_quote_revision < 1:
        raise StaleQuote("invalid quote revision; review the offer again")
    async with connection.transaction():
        await _lock_wallet(connection, user_id)
        row = await connection.fetchrow(
            """SELECT id,service_id,status,quoted_price_halalas,quote_revision,order_id
               FROM telegram_workflows WHERE id=$1 AND user_id=$2 FOR UPDATE""",
            workflow_id, user_id,
        )
        if not row:
            raise ValueError("workflow not found")
        if row["quote_revision"] != expected_quote_revision:
            raise StaleQuote("quote changed; review the offer again")
        if row["status"] == "SUBMITTED":
            return row["order_id"]
        if row["status"] != "CONFIRMING" or row["quoted_price_halalas"] is None:
            raise ValueError("workflow requires a fresh quote")
        files = await connection.fetch(
            "SELECT file_id FROM telegram_workflow_files WHERE workflow_id=$1 ORDER BY position",
            workflow_id,
        )
        order_id = await confirm_order(
            connection, user_id, row["service_id"], f"telegram:merge:{workflow_id}",
            file_ids=[file["file_id"] for file in files],
            expected_price_halalas=row["quoted_price_halalas"],
        )
        await connection.execute(
            """UPDATE telegram_workflows SET status='SUBMITTED',order_id=$2,updated_at=now()
               WHERE id=$1""",
            workflow_id, order_id,
        )
        return order_id


async def cancel_active(connection: asyncpg.Connection, user_id: UUID) -> bool:
    result = await connection.execute(
        """UPDATE telegram_workflows SET status='CANCELLED',updated_at=now()
           WHERE user_id=$1 AND status IN ('COLLECTING','CONFIRMING')""",
        user_id,
    )
    return result == "UPDATE 1"
