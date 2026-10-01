"""Bounded customer-owned status reads; no financial or sending side effects."""

import asyncpg


async def recent_telegram_requests(
    connection: asyncpg.Connection, telegram_user_id: int, *, limit: int = 10,
) -> list[dict]:
    if type(telegram_user_id) is not int or telegram_user_id < 1 or not 1 <= limit <= 10:
        raise ValueError("invalid customer status query")
    rows = await connection.fetch(
        """SELECT id,kind,status,created_at FROM (
             SELECT r.id,'review' AS kind,r.status,r.created_at FROM custom_service_requests r
             JOIN users u ON u.id=r.user_id WHERE u.telegram_user_id=$1
             AND r.channel='telegram' AND r.status IN ('NEW','IN_REVIEW','DECLINED')
             UNION ALL
             SELECT o.id,'order' AS kind,o.status,o.created_at FROM orders o
             JOIN users u ON u.id=o.user_id WHERE u.telegram_user_id=$1 AND o.channel='telegram'
           ) AS owned ORDER BY created_at DESC,id DESC LIMIT $2""", telegram_user_id, limit,
    )
    return [dict(row) for row in rows]
