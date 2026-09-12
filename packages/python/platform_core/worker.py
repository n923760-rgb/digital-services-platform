import logging
from typing import ClassVar
from urllib.parse import urlparse

import asyncpg
from arq.connections import RedisSettings
from arq.cron import cron

from platform_core.config import get_settings
from platform_core.jobs import claim_job, fail_job, pending_jobs, recover_stale_jobs
from platform_core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
redis_url = urlparse(settings.redis_url)
logger = logging.getLogger(__name__)


async def worker_heartbeat(ctx) -> None:
    # ARQ writes its own health key; this no-op proves scheduled tasks can execute.
    return None


async def dispatch_pending(ctx) -> None:
    """Database PENDING rows survive Redis outages and are redispatched later."""
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        for job_id, attempt in await pending_jobs(connection):
            await ctx["redis"].enqueue_job(
                "process_job", str(job_id), _job_id=f"platform:{job_id}:{attempt}",
            )
    finally:
        await connection.close()


async def recover_processing(ctx) -> None:
    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        recovered = await recover_stale_jobs(connection)
        if recovered:
            logger.warning("stale_jobs_recovered", extra={"count": recovered})
    finally:
        await connection.close()


async def process_job(ctx, job_id: str) -> None:
    """Fail closed until a validated service processor and delivery exist."""
    from uuid import UUID

    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        claim = await claim_job(connection, UUID(job_id))
        if claim is None:
            return
        logger.error("service_processor_unavailable", extra={"job_id": job_id, "order_id": str(claim.order_id)})
        await fail_job(connection, claim, "PROCESSOR_UNAVAILABLE", retryable=False)
    finally:
        await connection.close()


class WorkerSettings:
    functions: ClassVar[list] = [process_job]
    cron_jobs: ClassVar[list] = [
        cron(worker_heartbeat, second={0, 30}),
        cron(dispatch_pending, second={5, 35}),
        cron(recover_processing, second={15, 45}),
    ]
    job_timeout = 120
    redis_settings = RedisSettings(
        host=redis_url.hostname or "localhost",
        port=redis_url.port or 6379,
        database=int(redis_url.path.strip("/") or 0),
        password=redis_url.password,
    )
    health_check_key = "platform:worker:health"
