from typing import ClassVar
from urllib.parse import urlparse

from arq.connections import RedisSettings
from arq.cron import cron

from platform_core.config import get_settings
from platform_core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
redis_url = urlparse(settings.redis_url)


async def worker_heartbeat(ctx) -> None:
    # ARQ writes its own health key; this no-op proves scheduled tasks can execute.
    return None


class WorkerSettings:
    # Real service jobs are registered in CORE-001, with explicit idempotency and retry rules.
    functions: ClassVar[list] = []
    cron_jobs: ClassVar[list] = [cron(worker_heartbeat, second={0, 30})]
    redis_settings = RedisSettings(
        host=redis_url.hostname or "localhost",
        port=redis_url.port or 6379,
        database=int(redis_url.path.strip("/") or 0),
        password=redis_url.password,
    )
    health_check_key = "platform:worker:health"
