import logging
from contextlib import asynccontextmanager
from uuid import uuid4

import asyncpg
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from platform_core.config import get_settings
from platform_core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.redis = Redis.from_url(settings.redis_url)
    application.state.http = httpx.AsyncClient(timeout=3)
    yield
    await application.state.http.aclose()
    await application.state.redis.aclose()


app = FastAPI(title="Digital Services Platform API", lifespan=lifespan, docs_url=None, redoc_url=None)


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
    except Exception:
        checks["database"] = "unavailable"
    try:
        await request.app.state.redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
    try:
        response = await request.app.state.http.get(
            f"{settings.object_storage_endpoint}/minio/health/ready"
        )
        checks["object_storage"] = "ok" if response.status_code == 200 else "unavailable"
    except Exception:
        checks["object_storage"] = "unavailable"
    healthy = all(value == "ok" for value in checks.values())
    return JSONResponse({"status": "ok" if healthy else "unavailable", "checks": checks},
                        status_code=200 if healthy else 503)
