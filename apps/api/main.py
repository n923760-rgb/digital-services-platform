import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

import asyncpg
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from platform_core.config import get_settings
from platform_core.logging import configure_logging
from redis.asyncio import Redis
from redis.exceptions import RedisError

from apps.api.admin import router as admin_router

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.redis = Redis.from_url(settings.redis_url)
    application.state.storage = boto3.client(
        "s3",
        endpoint_url=settings.object_storage_endpoint,
        aws_access_key_id=settings.object_storage_access_key,
        aws_secret_access_key=settings.object_storage_secret_key,
        region_name=settings.object_storage_region,
        config=Config(s3={"addressing_style": "path"}, connect_timeout=2, read_timeout=2, retries={"max_attempts": 0}),
    )
    yield
    await application.state.redis.aclose()


app = FastAPI(title="Digital Services Platform API", lifespan=lifespan, docs_url=None, redoc_url=None)
app.include_router(admin_router)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = str(uuid4())
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed", extra={"request_id": request_id})
        return JSONResponse({"detail": "Internal error", "request_id": request_id}, status_code=500)
    response.headers["X-Request-ID"] = request_id
    logger.info("request_completed", extra={"request_id": request_id})
    return response


@app.get("/api/health/live")
async def live():
    return {"status": "ok", "component": "api"}


@app.get("/api/health/ready")
async def ready(request: Request):
    checks = {}
    try:
        conn = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""), timeout=3)
        try:
            await conn.fetchval("SELECT version_num FROM alembic_version LIMIT 1")
            checks["database"] = "ok"
        finally:
            await conn.close()
    except (asyncpg.PostgresError, OSError, TimeoutError):
        logger.warning("database_health_failed", exc_info=True)
        checks["database"] = "unavailable"
    try:
        await request.app.state.redis.ping()
        checks["redis"] = "ok"
    except (RedisError, OSError, TimeoutError):
        logger.warning("redis_health_failed", exc_info=True)
        checks["redis"] = "unavailable"
    try:
        await asyncio.wait_for(
            asyncio.to_thread(request.app.state.storage.head_bucket, Bucket=settings.object_storage_bucket),
            timeout=4,
        )
        checks["object_storage"] = "ok"
    except (BotoCoreError, ClientError, OSError, TimeoutError):
        logger.warning("object_storage_health_failed", exc_info=True)
        checks["object_storage"] = "unavailable"
    healthy = all(value == "ok" for value in checks.values())
    return JSONResponse({"status": "ok" if healthy else "unavailable", "checks": checks},
                        status_code=200 if healthy else 503)
