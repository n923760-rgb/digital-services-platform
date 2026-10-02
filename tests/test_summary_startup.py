"""Startup authentication failures must never mutate customer financial state."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.methods import GetMe

from apps.telegram_bot import v0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing", "malformed", "unauthorized", "timeout"])
async def test_failed_bot_authentication_never_opens_database(monkeypatch, caplog, failure):
    settings = SimpleNamespace(
        log_level="INFO", telegram_bot_token="" if failure == "missing" else "synthetic",
    )
    bot = SimpleNamespace(get_me=AsyncMock(), session=SimpleNamespace(close=AsyncMock()))
    constructor = Mock(return_value=bot)
    if failure == "malformed":
        constructor.side_effect = ValueError("sensitive-token-validation")
    elif failure == "unauthorized":
        bot.get_me.side_effect = TelegramUnauthorizedError(
            method=GetMe(), message="sensitive-provider-response",
        )
    elif failure == "timeout":
        bot.get_me.side_effect = TimeoutError("sensitive-network-response")
    connect, billing = AsyncMock(), AsyncMock()
    monkeypatch.setattr(v0, "get_settings", lambda: settings)
    monkeypatch.setattr(v0, "configure_logging", lambda _level: None)
    monkeypatch.setattr(v0, "Bot", constructor)
    monkeypatch.setattr(v0.summary_ui, "connect", connect)
    monkeypatch.setattr(v0.summary_ui, "billing", billing)

    with pytest.raises(RuntimeError, match="required|authentication failed") as rejected:
        await v0.main()

    connect.assert_not_awaited()
    billing.assert_not_awaited()
    assert "summary_startup_" in caplog.text
    assert "sensitive-" not in caplog.text
    assert "sensitive-" not in str(rejected.value)
    if failure in {"unauthorized", "timeout"}:
        bot.session.close.assert_awaited_once()
        assert rejected.value.__suppress_context__
    else:
        bot.session.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_authenticated_startup_keeps_legacy_guard_before_recovery(monkeypatch):
    settings = SimpleNamespace(log_level="INFO", telegram_bot_token="synthetic")
    authenticated = False

    async def authenticate():
        nonlocal authenticated
        authenticated = True

    async def connect():
        assert authenticated
        return connection

    connection = SimpleNamespace(close=AsyncMock())
    bot = SimpleNamespace(get_me=authenticate, session=SimpleNamespace(close=AsyncMock()))
    guard = AsyncMock(side_effect=RuntimeError("unresolved legacy orders"))
    purge, recover, billing = AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setattr(v0, "get_settings", lambda: settings)
    monkeypatch.setattr(v0, "configure_logging", lambda _level: None)
    monkeypatch.setattr(v0, "Bot", lambda **_kwargs: bot)
    monkeypatch.setattr(v0.summary_ui, "connect", connect)
    monkeypatch.setattr(v0, "require_no_legacy_work", guard)
    monkeypatch.setattr(v0, "purge_expired_summary_text", purge)
    monkeypatch.setattr(v0, "recover_interrupted_summaries", recover)
    monkeypatch.setattr(v0.summary_ui, "billing", billing)

    with pytest.raises(RuntimeError, match="unresolved legacy"):
        await v0.main()

    guard.assert_awaited_once_with(connection)
    purge.assert_not_awaited()
    recover.assert_not_awaited()
    billing.assert_not_awaited()
    connection.close.assert_awaited_once()
    bot.session.close.assert_awaited_once()
