from unittest.mock import AsyncMock

import httpx
import pytest

from apps.api import main


@pytest.mark.parametrize("database_available, expected_status", [(True, 200), (False, 503)])
async def test_readiness_fails_closed_when_database_is_down(
    monkeypatch, database_available, expected_status
):
    connection = AsyncMock()
    connection.fetchval.return_value = "0001_foundation"

    async def connect(*args, **kwargs):
        if not database_available:
            raise ConnectionError("database unavailable")
        return connection

    monkeypatch.setattr(main.asyncpg, "connect", connect)
    main.app.state.redis = AsyncMock()
    main.app.state.storage = AsyncMock()
    main.app.state.storage.head_bucket = lambda **kwargs: {"ResponseMetadata": {"HTTPStatusCode": 200}}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        response = await client.get("/api/health/ready")
    assert response.status_code == expected_status
    assert response.json()["checks"]["database"] == (
        "ok" if database_available else "unavailable"
    )
