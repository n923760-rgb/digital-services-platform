"""Minimal HTTP adapter; only PostgreSQL is required for this selected service."""

import logging

import asyncpg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from platform_core.config import get_settings
from platform_core.logging import configure_logging

from apps.api.admin import router as admin_router

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)
app = FastAPI(title="Digital Services Platform", docs_url=None, redoc_url=None)
app.state.postgres_login_limits = True
app.include_router(admin_router)


@app.middleware("http")
async def safe_failure_boundary(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        # Suppress provider/customer bodies while preserving classified failure reporting.
        logger.exception("direct_api_request_failed:%s", type(exc).__name__, exc_info=False)
        return JSONResponse({"detail": "Internal error"}, status_code=500)


@app.exception_handler(RequestValidationError)
async def invalid_input(request: Request, exc: RequestValidationError):
    logger.info("direct_api_invalid_input")
    return JSONResponse({"detail": "Invalid input"}, status_code=422)


@app.get("/api/health/live")
async def live():
    return {"status": "ok", "component": "api"}


@app.get("/api/health/ready")
async def ready():
    try:
        connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""), timeout=3)
        try:
            version = await connection.fetchval("SELECT version_num FROM alembic_version LIMIT 1")
            present = await connection.fetchval("SELECT to_regclass('summary_inputs') IS NOT NULL AND to_regclass('admin_login_counters') IS NOT NULL")
        finally:
            await connection.close(timeout=1)
        if not version or not present:
            raise ValueError("summary_schema_unavailable")
    except (asyncpg.PostgresError, OSError, ValueError):
        logger.warning("summary_database_unavailable")
        return JSONResponse({"status": "unavailable", "checks": {"database": "unavailable"}}, status_code=503)
    return {"status": "ok", "checks": {"database": "ok"}}
