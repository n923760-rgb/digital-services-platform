"""Durable custom requests with bounded, audited admin triage."""

import json
from uuid import UUID, uuid4

import asyncpg


class CustomRequestNotFound(ValueError):
    pass


class CustomRequestRevisionConflict(ValueError):
    pass


class CustomRequestTransitionRejected(ValueError):
    pass


async def triage_request(
    connection: asyncpg.Connection,
    request_id: UUID,
    actor_id: UUID,
    *,
    expected_revision: int,
    action: str,
    reason: str,
) -> dict:
    """Start review or decline a request without pricing, charging, or creating an order."""
    reason = reason.strip()
    if expected_revision < 1:
        raise CustomRequestTransitionRejected("invalid revision")
    if action not in {"START_REVIEW", "DECLINE"}:
        raise CustomRequestTransitionRejected("unknown triage action")
    if not 10 <= len(reason) <= 500:
        raise CustomRequestTransitionRejected("reason must be 10–500 characters")

    async with connection.transaction():
        row = await connection.fetchrow(
            """SELECT id,status,revision,reviewed_by_admin_id FROM custom_service_requests
               WHERE id=$1 FOR UPDATE""",
            request_id,
        )
        if row is None:
            raise CustomRequestNotFound("custom request not found")
        if row["revision"] != expected_revision:
            raise CustomRequestRevisionConflict("custom request changed; reload before saving")

        if action == "START_REVIEW":
            if row["status"] != "NEW":
                raise CustomRequestTransitionRejected("only a new request can enter review")
            status = "IN_REVIEW"
            decision_reason = None
        else:
            if row["status"] != "IN_REVIEW":
                raise CustomRequestTransitionRejected("request cannot be declined in its current state")
            if row["reviewed_by_admin_id"] != actor_id:
                raise CustomRequestTransitionRejected("request is assigned to another administrator")
            status = "DECLINED"
            decision_reason = reason

        revision = row["revision"] + 1
        await connection.execute(
            """UPDATE custom_service_requests SET status=$2,revision=$3,
               reviewed_by_admin_id=$4,reviewed_at=now(),decision_reason=$5,updated_at=now()
               WHERE id=$1""",
            request_id,
            status,
            revision,
            actor_id,
            decision_reason,
        )
        metadata = {
            "custom_request_id": str(request_id),
            "status_before": row["status"],
            "status_after": status,
            "revision_before": row["revision"],
            "revision_after": revision,
        }
        await connection.execute(
            """INSERT INTO audit_logs (id,actor_admin_id,action,reason,metadata)
               VALUES ($1,$2,$3,$4,$5::jsonb)""",
            uuid4(),
            actor_id,
            "CUSTOM_REQUEST_REVIEW_STARTED" if action == "START_REVIEW"
            else "CUSTOM_REQUEST_DECLINED",
            reason,
            json.dumps(metadata),
        )
        return {"id": str(request_id), "status": status, "revision": revision}


async def begin_request(
    connection: asyncpg.Connection, user_id: UUID, *, channel: str = "telegram",
) -> UUID:
    if not channel or len(channel) > 40:
        raise ValueError("invalid channel")
    return await connection.fetchval("""INSERT INTO custom_service_requests (id,user_id,channel,status)
      VALUES ($1,$2,$3,'COLLECTING')
      ON CONFLICT (user_id,channel) WHERE status='COLLECTING'
      DO UPDATE SET updated_at=now() RETURNING id""", uuid4(), user_id, channel)


async def draft_user_id(connection: asyncpg.Connection, telegram_user_id: int) -> UUID | None:
    return await connection.fetchval("""SELECT u.id FROM custom_service_requests r
      JOIN users u ON u.id=r.user_id
      WHERE u.telegram_user_id=$1 AND r.channel='telegram' AND r.status='COLLECTING'""",
      telegram_user_id)


async def submitted_telegram_request(
    connection: asyncpg.Connection, telegram_user_id: int, message_id: int,
) -> UUID | None:
    return await connection.fetchval("""SELECT r.id FROM custom_service_requests r
      JOIN users u ON u.id=r.user_id WHERE u.telegram_user_id=$1
      AND r.channel='telegram' AND r.source_message_key=$2
      AND r.status IN ('NEW','IN_REVIEW','DECLINED')""",
      telegram_user_id, str(message_id))


async def submit_request(
    connection: asyncpg.Connection, user_id: UUID, source_message_key: str, description: str,
    *, channel: str = "telegram",
) -> UUID:
    if (not source_message_key or len(source_message_key) > 160
            or not channel or len(channel) > 40):
        raise ValueError("invalid source message key or channel")
    description = description.strip()
    if not 10 <= len(description) <= 2000:
        raise ValueError("description must be 10–2000 characters")
    async with connection.transaction():
        # Serialize repeat deliveries before checking the message idempotency key.
        if not await connection.fetchval("SELECT id FROM users WHERE id=$1 FOR UPDATE", user_id):
            raise ValueError("customer not found")
        previous = await connection.fetchrow("""SELECT id,description FROM custom_service_requests
          WHERE user_id=$1 AND channel=$2 AND source_message_key=$3""",
          user_id, channel, source_message_key)
        if previous:
            if previous["description"] != description:
                raise ValueError("message content changed")
            return previous["id"]
        draft = await connection.fetchrow("""SELECT id FROM custom_service_requests
          WHERE user_id=$1 AND channel=$2 AND status='COLLECTING' FOR UPDATE""",
          user_id, channel)
        if not draft:
            raise ValueError("no draft request")
        await connection.execute("""UPDATE custom_service_requests
          SET status='NEW',description=$2,source_message_key=$3,updated_at=now()
          WHERE id=$1""", draft["id"], description, source_message_key)
        return draft["id"]


async def cancel_draft(connection: asyncpg.Connection, telegram_user_id: int) -> bool:
    result = await connection.execute("""UPDATE custom_service_requests r
      SET status='CANCELLED',updated_at=now() FROM users u
      WHERE u.id=r.user_id AND u.telegram_user_id=$1
      AND r.channel='telegram' AND r.status='COLLECTING'""",
      telegram_user_id)
    return result == "UPDATE 1"
