"""Customer-facing completed results; ownership and delivery state checked in SQL."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class CustomerFile:
    id: UUID
    name: str
    retention_until: datetime


async def recent_results(connection: asyncpg.Connection, telegram_user_id: int) -> list[CustomerFile]:
    rows = await connection.fetch("""SELECT f.id,f.file_name,f.retention_until
      FROM users u JOIN files f ON f.owner_user_id=u.id
      JOIN orders o ON o.id=f.order_id AND o.user_id=u.id
      WHERE u.telegram_user_id=$1 AND f.file_type='OUTPUT'
      AND f.mime_type='application/pdf'
      AND f.status='READY' AND f.retention_until>now() AND o.status='COMPLETED'
      AND f.size_bytes<=20971520
      ORDER BY f.created_at DESC,f.id DESC LIMIT 10""", telegram_user_id)
    return [CustomerFile(row["id"], row["file_name"], row["retention_until"])
            for row in rows]


async def completed_result_owner(
    connection: asyncpg.Connection, telegram_user_id: int, file_id: UUID,
) -> UUID | None:
    return await connection.fetchval("""SELECT u.id FROM users u
      JOIN files f ON f.owner_user_id=u.id
      JOIN orders o ON o.id=f.order_id AND o.user_id=u.id
      WHERE u.telegram_user_id=$1 AND f.id=$2 AND f.file_type='OUTPUT'
      AND f.mime_type='application/pdf'
      AND f.status='READY' AND f.retention_until>now() AND o.status='COMPLETED'
      AND f.size_bytes<=20971520""",
      telegram_user_id, file_id)
