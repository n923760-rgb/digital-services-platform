"""Minimal HTTP adapter; only PostgreSQL is required for this selected service."""

import logging

import asyncpg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from platform_core.config import get_settings
from platform_core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)
app = FastAPI(title="Digital Services Platform", docs_url=None, redoc_url=None)


@app.get("/api/health/live")
async def live():
    return {"status": "ok", "component": "api"}


@app.get("/api/health/ready")
async def ready():
    try:
        connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""), timeout=3)
        try:
            version = await connection.fetchval("SELECT version_num FROM alembic_version LIMIT 1")
            present = await connection.fetchval("SELECT to_regclass('summary_inputs') IS NOT NULL")
        finally:
            await connection.close(timeout=1)
        if not version or not present:
            raise ValueError("summary_schema_unavailable")
    except (asyncpg.PostgresError, OSError, ValueError):
        logger.warning("summary_database_unavailable")
        return JSONResponse({"status": "unavailable", "checks": {"database": "unavailable"}}, status_code=503)
    return {"status": "ok", "checks": {"database": "ok"}}
