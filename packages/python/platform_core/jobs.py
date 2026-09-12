"""Durable job claiming and failure recovery; processor integration follows separately."""

from dataclasses import dataclass
from uuid import UUID, uuid4

import asyncpg

from platform_core.ledger import settle


@dataclass(frozen=True)
class Claim:
    job_id: UUID
    order_id: UUID
    attempt_number: int


async def pending_jobs(connection: asyncpg.Connection, limit: int = 100) -> list[tuple[UUID, int]]:
    if limit < 1 or limit > 1000:
        raise ValueError("invalid dispatch batch size")
    rows = await connection.fetch(
        """SELECT id,attempt_count + 1 AS next_attempt
           FROM jobs WHERE status='PENDING' ORDER BY created_at,id LIMIT $1""",
        limit,
    )
    return [(row["id"], row["next_attempt"]) for row in rows]


async def claim_job(connection: asyncpg.Connection, job_id: UUID) -> Claim | None:
    async with connection.transaction():
        job = await connection.fetchrow(
            """SELECT j.order_id,j.status,j.attempt_count,j.max_attempts,o.status AS order_status
               FROM jobs j JOIN orders o ON o.id=j.order_id WHERE j.id=$1 FOR UPDATE OF j,o""",
            job_id,
        )
        if not job or job["status"] != "PENDING" or job["order_status"] not in {
            "RESERVED", "QUEUED", "PROCESSING",
        }:
            return None
        attempt = job["attempt_count"] + 1
        if attempt > job["max_attempts"]:
            raise ValueError("job exhausted attempts without settlement")
        await connection.execute(
            """UPDATE jobs SET status='PROCESSING', attempt_count=$2, started_at=now(),
               error_code=NULL WHERE id=$1""",
            job_id, attempt,
        )
        await connection.execute("UPDATE orders SET status='PROCESSING' WHERE id=$1", job["order_id"])
        await connection.execute(
            """INSERT INTO job_attempts (id,job_id,attempt_number,status)
               VALUES ($1,$2,$3,'PROCESSING')""",
            uuid4(), job_id, attempt,
        )
        return Claim(job_id, job["order_id"], attempt)


async def fail_job(
    connection: asyncpg.Connection, claim: Claim, error_code: str, *, retryable: bool,
) -> bool:
    """Return True when permanently failed and held funds have been released."""
    if not error_code or len(error_code) > 100:
        raise ValueError("invalid error code")
    async with connection.transaction():
        job = await connection.fetchrow(
            """SELECT j.order_id,j.status,j.attempt_count,j.max_attempts,o.user_id
               FROM jobs j JOIN orders o ON o.id=j.order_id WHERE j.id=$1 FOR UPDATE OF j,o""",
            claim.job_id,
        )
        if not job or job["order_id"] != claim.order_id:
            raise ValueError("job not found")
        if job["status"] != "PROCESSING" or job["attempt_count"] != claim.attempt_number:
            raise ValueError("attempt no longer active")
        exhausted = not retryable or job["attempt_count"] >= job["max_attempts"]
        await connection.execute(
            """UPDATE job_attempts SET status='FAILED', error_code=$3, completed_at=now()
               WHERE job_id=$1 AND attempt_number=$2 AND status='PROCESSING'""",
            claim.job_id, claim.attempt_number, error_code,
        )
        await connection.execute(
            """UPDATE jobs SET status=$2,error_code=$3,completed_at=CASE WHEN $4 THEN now()
               ELSE NULL END WHERE id=$1""",
            claim.job_id, "FAILED" if exhausted else "PENDING", error_code, exhausted,
        )
        if exhausted:
            await connection.execute("UPDATE orders SET status='FAILED' WHERE id=$1", claim.order_id)
            price = await connection.fetchval(
                "SELECT price_snapshot_halalas FROM orders WHERE id=$1", claim.order_id,
            )
            if price:
                await settle(
                    connection, job["user_id"], claim.order_id,
                    f"release:{claim.order_id}", kind="RELEASE",
                )
        return exhausted


async def complete_job(
    connection: asyncpg.Connection, claim: Claim, result_file_id: UUID,
) -> None:
    """Move validated output to delivery queue; capture only after actual delivery."""
    async with connection.transaction():
        row = await connection.fetchrow(
            """SELECT j.status,j.attempt_count,o.user_id FROM jobs j
               JOIN orders o ON o.id=j.order_id WHERE j.id=$1 AND j.order_id=$2
               FOR UPDATE OF j,o""",
            claim.job_id, claim.order_id,
        )
        if not row or row["status"] != "PROCESSING" or row["attempt_count"] != claim.attempt_number:
            raise ValueError("attempt no longer active")
        valid = await connection.fetchval(
            """SELECT 1 FROM files WHERE id=$1 AND owner_user_id=$2 AND order_id=$3
               AND file_type='OUTPUT' AND status='READY' AND retention_until>now()""",
            result_file_id, row["user_id"], claim.order_id,
        )
        if not valid:
            raise ValueError("validated output file is not ready")
        channel = await connection.fetchval(
            "SELECT channel FROM orders WHERE id=$1", claim.order_id,
        )
        if channel != "telegram":
            raise ValueError("delivery channel unavailable")
        await connection.execute(
            """UPDATE job_attempts SET status='COMPLETED',completed_at=now()
               WHERE job_id=$1 AND attempt_number=$2 AND status='PROCESSING'""",
            claim.job_id, claim.attempt_number,
        )
        await connection.execute(
            """UPDATE jobs SET status='COMPLETED',result_file_id=$2,completed_at=now()
               WHERE id=$1""",
            claim.job_id, result_file_id,
        )
        await connection.execute(
            "UPDATE orders SET status='AWAITING_FULFILLMENT' WHERE id=$1", claim.order_id,
        )
        await connection.execute(
            """INSERT INTO delivery_outbox (id,order_id,channel,status)
               VALUES ($1,$2,'telegram','PENDING')""",
            uuid4(), claim.order_id,
        )


async def recover_stale_jobs(connection: asyncpg.Connection, timeout_seconds: int = 300) -> int:
    """Retry expired processing attempts; exhausted attempts release held funds."""
    if timeout_seconds < 180:
        raise ValueError("timeout must exceed the ARQ job execution limit")
    async with connection.transaction():
        rows = await connection.fetch(
            """SELECT j.id,j.order_id,j.attempt_count FROM jobs j
               JOIN orders o ON o.id=j.order_id
               WHERE j.status='PROCESSING' AND j.started_at < now() - ($1 * interval '1 second')
               ORDER BY j.started_at LIMIT 100 FOR UPDATE OF j,o SKIP LOCKED""",
            timeout_seconds,
        )
        for row in rows:
            await fail_job(
                connection, Claim(row["id"], row["order_id"], row["attempt_count"]),
                "WORKER_TIMEOUT", retryable=True,
            )
        return len(rows)
