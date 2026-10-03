"""Real aiogram model/adapter tests with synthetic Telegram I/O, not live sends."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.filters import CommandObject
from aiogram.types import CallbackQuery, Chat, ErrorEvent, Message, Update, User
from platform_core.config import Settings
from platform_core.office_trial import OfficeTrial

from apps.telegram_bot import office_ui, v0

PAYLOAD = 'تقرير العمل\nنص عربي والطلب INV-2026 والنص <tag> "quote".'


def message(user_id=42, *, chat_id=42, chat_type="private", is_bot=False, message_id=10):
    return Message(message_id=message_id, date=datetime.now(UTC),
                   chat=Chat(id=chat_id, type=chat_type),
                   from_user=User(id=user_id, is_bot=is_bot, first_name="Synthetic"),
                   text="/word " + PAYLOAD)


@pytest.fixture
def setup_trial(monkeypatch):
    clock = SimpleNamespace(now=100.0)
    trial = OfficeTrial(clock=lambda: clock.now)
    settings = SimpleNamespace(office_trial_enabled=True, office_trial_user_ids=[42, 43],
                               office_trial_ttl_seconds=60)
    answer = AsyncMock()
    callback_answer = AsyncMock()
    bot = SimpleNamespace(send_document=AsyncMock(return_value=message(
        user_id=999, is_bot=True, message_id=99,
    )))
    monkeypatch.setattr(office_ui, "trial", trial)
    monkeypatch.setattr(office_ui, "get_settings", lambda: settings)
    monkeypatch.setattr(Message, "answer", answer)
    monkeypatch.setattr(CallbackQuery, "answer", callback_answer)
    return SimpleNamespace(trial=trial, settings=settings, clock=clock, bot=bot,
                           answer=answer, callback_answer=callback_answer)


def callback(token, user_id=42, *, chat_id=42, chat_type="private"):
    return CallbackQuery(id="synthetic", chat_instance="synthetic",
                         from_user=User(id=user_id, is_bot=False, first_name="Synthetic"),
                         message=message(user_id=999, is_bot=True, chat_id=chat_id,
                                         chat_type=chat_type),
                         data=f"office:get:{token}")


def test_trial_defaults_off_and_new_handlers_precede_generic_text():
    settings = Settings(_env_file=None)
    assert settings.office_trial_enabled is False
    assert settings.office_trial_user_ids == []
    callbacks = [h.callback.__name__ for h in v0.dispatcher.message.handlers]
    assert callbacks.index("word") < callbacks.index("text")


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["disabled", "not_allowlisted", "group", "wrong_chat", "bot"])
async def test_rejected_intake_never_generates_or_sends(setup_trial, reason, caplog):
    env = setup_trial
    incoming = message()
    if reason == "disabled":
        env.settings.office_trial_enabled = False
    elif reason == "not_allowlisted":
        env.settings.office_trial_user_ids = []
    elif reason == "group":
        incoming = message(chat_id=-100, chat_type="group")
    elif reason == "wrong_chat":
        incoming = message(chat_id=43)
    else:
        incoming = message(is_bot=True)
    await office_ui.create(incoming, env.bot, PAYLOAD)
    assert env.trial._files == {}
    env.bot.send_document.assert_not_awaited()
    assert PAYLOAD not in caplog.text


@pytest.mark.asyncio
async def test_word_wrapper_sends_to_owner_records_receipt_and_deduplicates(setup_trial):
    env = setup_trial
    await v0.word(message(), env.bot, CommandObject(command="word", args=PAYLOAD))
    await v0.word(message(), env.bot, CommandObject(command="word", args=PAYLOAD))
    env.bot.send_document.assert_awaited_once()
    args = env.bot.send_document.await_args.kwargs
    result = env.trial._files[42]
    assert args["chat_id"] == 42 and args["protect_content"] is True
    assert args["document"].data == result.artifact.content
    assert result.delivery_state == "delivered" and result.delivered_message_id == 99
    assert "تجريبي" in args["caption"] and "اتجاه" in args["caption"]


@pytest.mark.asyncio
async def test_help_and_invalid_text_never_send_file(setup_trial):
    env = setup_trial
    await office_ui.create(message(), env.bot, "")
    assert "4,000" in env.answer.await_args.args[0]
    await office_ui.create(message(), env.bot, "أ" * 4001)
    await office_ui.create(message(), env.bot, "عنوان\nprivate\u202e")
    env.bot.send_document.assert_not_awaited()
    assert env.trial._files == {}


@pytest.mark.asyncio
async def test_callback_uses_customer_not_bot_author_and_retains_identical_bytes(setup_trial):
    env = setup_trial
    await office_ui.create(message(), env.bot, PAYLOAD)
    result = env.trial._files[42]
    env.bot.send_document.reset_mock()
    await v0.word_resend(callback(result.token), env.bot)
    env.bot.send_document.assert_awaited_once()
    args = env.bot.send_document.await_args.kwargs
    assert args["chat_id"] == 42 and args["document"].data == result.artifact.content
    assert env.trial._files[42].delivered_message_id == 99


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["owner", "group", "expired", "disabled", "stale"])
async def test_resend_rechecks_access_and_expiry(setup_trial, reason):
    env = setup_trial
    result = env.trial.create(42, 10, PAYLOAD, office_ui.policy())
    request = callback(result.token)
    if reason == "owner":
        request = callback(result.token, user_id=43, chat_id=43)
    elif reason == "group":
        request = callback(result.token, chat_id=-100, chat_type="group")
    elif reason == "expired":
        env.clock.now += 60
    elif reason == "disabled":
        env.settings.office_trial_enabled = False
    else:
        env.trial.create(42, 11, PAYLOAD, office_ui.policy())
    await office_ui.resend(request, env.bot)
    env.bot.send_document.assert_not_awaited()
    assert env.callback_answer.await_args.kwargs["show_alert"] is True


@pytest.mark.asyncio
async def test_failed_send_is_uncertain_cached_and_explicitly_retryable(setup_trial, caplog):
    env = setup_trial
    env.bot.send_document.side_effect = TimeoutError("sensitive-provider-response")
    await office_ui.create(message(), env.bot, PAYLOAD)
    result = env.trial._files[42]
    assert result.delivery_state == "uncertain" and result.delivered_message_id is None
    assert "office_delivery_uncertain" in caplog.text
    assert "sensitive-provider-response" not in caplog.text
    assert "تعذر تأكيد" in env.answer.await_args.args[0]
    await office_ui.create(message(), env.bot, PAYLOAD)
    assert env.bot.send_document.await_count == 1
    env.bot.send_document.side_effect = None
    await office_ui.resend(callback(result.token), env.bot)
    assert env.bot.send_document.await_count == 2
    assert env.bot.send_document.await_args.kwargs["document"].data == result.artifact.content


@pytest.mark.asyncio
async def test_cancellation_propagates_and_releases_sending_state(setup_trial):
    env = setup_trial
    env.bot.send_document.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await office_ui.create(message(), env.bot, PAYLOAD)
    assert env.trial._files[42].delivery_state == "uncertain"
    assert env.trial._files[42].delivered_message_id is None


@pytest.mark.asyncio
async def test_notice_failure_is_sanitized_and_does_not_claim_success(setup_trial, caplog):
    env = setup_trial
    env.settings.office_trial_enabled = False
    env.answer.side_effect = OSError("private-notice-response")
    await office_ui.create(message(), env.bot, PAYLOAD)
    assert "office_notice_unavailable" in caplog.text
    assert "private-notice-response" not in caplog.text
    env.bot.send_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_slow_provider_has_bounded_timeout_and_explicit_retry(setup_trial, monkeypatch):
    env = setup_trial

    async def stalled(**_kwargs):
        await asyncio.Event().wait()

    env.bot.send_document.side_effect = stalled
    monkeypatch.setattr(office_ui, "DELIVERY_TIMEOUT_SECONDS", 0.01)
    await asyncio.wait_for(office_ui.create(message(), env.bot, PAYLOAD), timeout=1)
    assert env.trial._files[42].delivery_state == "uncertain"
    assert "تعذر تأكيد" in env.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_expiry_during_accepted_send_does_not_ack_newer_result(setup_trial):
    env = setup_trial

    async def accepted(**_kwargs):
        env.clock.now += 60
        env.trial.create(42, 11, PAYLOAD, office_ui.policy())
        return message(user_id=999, is_bot=True, message_id=99)

    env.bot.send_document.side_effect = accepted
    await office_ui.create(message(), env.bot, PAYLOAD)
    assert env.trial._files[42].request_id == 11
    assert env.trial._files[42].delivery_state == "pending"
    assert env.trial._files[42].delivered_message_id is None


@pytest.mark.asyncio
async def test_unexpected_delivery_fault_propagates_and_releases_claim(setup_trial, caplog):
    env = setup_trial
    env.bot.send_document.side_effect = RuntimeError("private-unexpected-response")
    with pytest.raises(RuntimeError):
        await office_ui.create(message(), env.bot, PAYLOAD)
    assert env.trial._files[42].delivery_state == "uncertain"
    assert "office_delivery_failed:RuntimeError" in caplog.text
    assert "private-unexpected-response" not in caplog.text


@pytest.mark.asyncio
async def test_global_word_fault_notice_is_unpaid_and_sanitized(setup_trial, caplog):
    env = setup_trial
    env.bot.send_message = AsyncMock()
    event = ErrorEvent(update=Update(update_id=1, message=message()),
                       exception=RuntimeError("private-unexpected-response"))
    assert await v0.errors(event, env.bot) is True
    env.bot.send_message.assert_awaited_once()
    text = env.bot.send_message.await_args.args[1]
    assert "لا يوجد دفع" in text and "/orders" not in text
    assert "private-unexpected-response" not in caplog.text
