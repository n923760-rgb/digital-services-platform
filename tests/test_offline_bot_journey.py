"""Offline customer acceptance through the real aiogram dispatcher and disposable DB."""

import os
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import asyncpg
import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import (
    AnswerCallbackQuery,
    AnswerPreCheckoutQuery,
    GetMe,
    RefundStarPayment,
    SendDocument,
    SendInvoice,
    SendMessage,
)
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    Chat,
    Document,
    Message,
    MessageEntity,
    PhotoSize,
    PreCheckoutQuery,
    SuccessfulPayment,
    Update,
    User,
)
from platform_core.admin_auth import create_admin
from platform_core.ledger import Balance, balance
from platform_core.office_trial import OfficeTrial
from platform_core.service_registry import create_category, create_service, update_service
from platform_core.stars_inbox import persist_payment_update
from platform_core.text_summary import SLUG, TEXT_INPUT_SCHEMA

from apps.telegram_bot import customer_status, office_ui, stars_payments, summary_ui, v0

TEXT = "تقدم المنصة خدمات رقمية للسوق السعودي. تحافظ المنصة على أسعار واضحة وسجل الدفع."
TERMS = "شروط اصطناعية للاختبار فقط؛ لا تمثل شروط شراء حقيقية."


class SyntheticTelegramSession(BaseSession):
    """Return typed SDK responses; fail on every unimplemented method, with no network."""

    def __init__(self):
        super().__init__()
        self.calls = []
        self.messages = []
        self.result_attempts = 0
        self.fail_next_result = False
        self.document_attempts = 0
        self.fail_next_document = False

    async def close(self):
        pass

    async def stream_content(self, *args, **kwargs):
        raise AssertionError("Offline acceptance must never download from Telegram")
        yield b""  # The SDK requires an async generator, even though downloads are forbidden.

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, GetMe):
            return User(id=bot.id, is_bot=True, first_name="Synthetic bot",
                        username="synthetic_office_bot")
        if isinstance(method, SendDocument):
            if not isinstance(method.document, BufferedInputFile):
                raise TypeError("Offline document delivery requires bounded in-memory bytes")
            self.document_attempts += 1
            if self.fail_next_document:
                self.fail_next_document = False
                raise OSError("synthetic-private-document-body")
            response = Message(
                message_id=len(self.messages) + 100, date=datetime.now(UTC),
                chat=Chat(id=method.chat_id, type="private"),
                from_user=User(id=bot.id, is_bot=True, first_name="Synthetic bot"),
                document=Document(file_id="synthetic-docx", file_unique_id="synthetic-docx",
                                  file_name=method.document.filename,
                                  mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                  file_size=len(method.document.data)),
                caption=method.caption, reply_markup=method.reply_markup,
            )
            self.messages.append(response)
            return response
        if isinstance(method, (AnswerCallbackQuery, AnswerPreCheckoutQuery)):
            return True
        if isinstance(method, RefundStarPayment):
            # Existing disposable-suite refunds must not be confirmed by this fixture.
            return False
        if not isinstance(method, (SendMessage, SendInvoice)):
            raise TypeError(f"Unexpected offline API method: {type(method).__name__}")
        text = method.text if isinstance(method, SendMessage) else "Synthetic invoice"
        if text.startswith("ملخص محلي — الطلب"):
            self.result_attempts += 1
            if self.fail_next_result:
                self.fail_next_result = False
                raise OSError("synthetic-private-transport-body")
        response = Message(
            message_id=len(self.messages) + 100, date=datetime.now(UTC),
            chat=Chat(id=method.chat_id, type="private"),
            from_user=User(id=bot.id, is_bot=True, first_name="Synthetic bot"),
            text=text,
        )
        self.messages.append(response)
        return response


@pytest.fixture
async def trial(monkeypatch):
    db = await asyncpg.connect(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
    session = SyntheticTelegramSession()
    bot = Bot(token=f"{uuid4().int % 2**40 + 1}:synthetic-fixture-only", session=session)
    product = None
    owner = await create_admin(db, "offline-" + uuid4().hex,
                               "synthetic offline fixture password", role_code="OWNER")
    settings = SimpleNamespace(
        database_url=os.environ["DATABASE_URL"], telegram_orders_enabled=True,
        telegram_stars_enabled=True, telegram_payment_terms=TERMS,
        telegram_payment_support="دعم اصطناعي للاختبار", file_retention_days=1,
    )
    for module in (customer_status, stars_payments, summary_ui, v0):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    try:
        category = await create_category(
            db, owner, slug="offline-" + uuid4().hex, name_ar="فئة اختبار",
            reason="Disposable offline customer acceptance",
        )
        product = await create_service(
            db, owner, category_id=category, slug="offline-" + uuid4().hex,
            name_ar="منتج تلخيص للاختبار", description_ar="تلخيص محلي تجريبي",
            processor_type="tool", processor_key=SLUG, base_price_halalas=0,
            base_price_stars=31, input_schema=TEXT_INPUT_SCHEMA,
            reason="Disposable offline customer acceptance",
        )
        await update_service(
            db, product, owner, expected_revision=1, enabled=True, confirm=True,
            allow_activation=True, reason="Activate only disposable test product",
        )
        yield SimpleNamespace(
            db=db, bot=bot, session=session, product=product, owner=owner, settings=settings,
            user=User(id=uuid4().int % 2**40 + 1, is_bot=False, first_name="Synthetic buyer"),
            sequence=0,
        )
    finally:
        if product is not None:
            revision = await db.fetchval("SELECT revision FROM services WHERE id=$1", product)
            await update_service(
                db, product, owner, expected_revision=revision, enabled=False, confirm=True,
                reason="Withdraw disposable acceptance product",
            )
        await bot.session.close()
        await db.close()


def incoming(trial, text=None, **fields):
    entities = [MessageEntity(type="bot_command", offset=0, length=len(text.split(maxsplit=1)[0]))] if text and text.startswith("/") else None
    return Message(
        message_id=trial.sequence + 1, date=datetime.now(UTC),
        chat=Chat(id=trial.user.id, type="private"), from_user=trial.user,
        text=text, entities=entities, **fields,
    )


async def feed(trial, **fields):
    trial.sequence += 1
    update = Update(update_id=trial.sequence, **fields)
    if update.message and update.message.successful_payment:
        # Model the production durable-before-dispatch boundary; polling has separate tests.
        await persist_payment_update(trial.db, trial.bot.id, update)
    await v0.dispatcher.feed_update(trial.bot, update)
    return update


async def press(trial, message, data):
    await feed(trial, callback_query=CallbackQuery(
        id=uuid4().hex, chat_instance="synthetic-private", from_user=trial.user,
        message=message, data=data,
    ))


def calls(trial, kind):
    return [method for method in trial.session.calls if isinstance(method, kind)]


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["success", "uncertain_delivery", "stale_price"])
async def test_offline_selected_product_invoice_receipt_delivery_and_replay(trial, scenario, caplog):
    db, session = trial.db, trial.session
    await feed(trial, message=incoming(trial, "/start"))
    menu = calls(trial, SendMessage)[-1]
    button = next(button for row in menu.reply_markup.inline_keyboard for button in row
                  if button.callback_data == f"product:select:{trial.product.hex}")
    assert "31 ⭐" in button.text
    await press(trial, session.messages[-1], button.callback_data)
    assert await db.fetchval(
        """SELECT w.service_id FROM telegram_workflows w JOIN users u ON u.id=w.user_id
           WHERE u.telegram_user_id=$1 AND w.status='COLLECTING'""", trial.user.id,
    ) == trial.product

    await feed(trial, message=incoming(trial, TEXT))
    assert session.messages[-2].text == TERMS
    quote_message = session.messages[-1]
    quote_call = calls(trial, SendMessage)[-1]
    confirm = quote_call.reply_markup.inline_keyboard[0][0].callback_data
    assert "31 ⭐" in quote_message.text and "منتج تلخيص للاختبار" in quote_message.text
    await press(trial, quote_message, confirm)
    first_invoice = calls(trial, SendInvoice)[-1]
    await press(trial, quote_message, confirm)
    assert calls(trial, SendInvoice)[-1].payload == first_invoice.payload
    assert await db.fetchval(
        "SELECT count(*) FROM star_invoices WHERE id=$1", UUID(first_invoice.payload.removeprefix("stars:")),
    ) == 1

    invoice = first_invoice
    amount = 31
    if scenario == "stale_price":
        await update_service(
            db, trial.product, trial.owner, expected_revision=2, base_price_stars=39,
            reason="Change price before synthetic checkout",
        )
        await feed(trial, pre_checkout_query=PreCheckoutQuery(
            id=uuid4().hex, from_user=trial.user, currency="XTR", total_amount=31,
            invoice_payload=first_invoice.payload,
        ))
        assert calls(trial, AnswerPreCheckoutQuery)[-1].ok is False
        assert await db.fetchval(
            "SELECT count(*) FROM orders o JOIN users u ON u.id=o.user_id WHERE u.telegram_user_id=$1",
            trial.user.id,
        ) == 0
        await feed(trial, message=incoming(trial, TEXT))
        quote_message = session.messages[-1]
        assert "39 ⭐" in quote_message.text
        confirm = calls(trial, SendMessage)[-1].reply_markup.inline_keyboard[0][0].callback_data
        await press(trial, quote_message, confirm)
        invoice, amount = calls(trial, SendInvoice)[-1], 39
        assert invoice.payload != first_invoice.payload

    assert invoice.currency == "XTR" and invoice.provider_token == ""
    assert invoice.chat_id == trial.user.id
    assert len(invoice.prices) == 1 and invoice.prices[0].amount == amount
    assert invoice.start_parameter and invoice.protect_content

    foreign = trial.user.model_copy(update={"id": trial.user.id + 1})
    await feed(trial, pre_checkout_query=PreCheckoutQuery(
        id=uuid4().hex, from_user=foreign, currency="XTR", total_amount=amount,
        invoice_payload=invoice.payload,
    ))
    assert calls(trial, AnswerPreCheckoutQuery)[-1].ok is False
    assert calls(trial, AnswerPreCheckoutQuery)[-1].error_message
    await feed(trial, pre_checkout_query=PreCheckoutQuery(
        id=uuid4().hex, from_user=trial.user, currency="XTR", total_amount=amount,
        invoice_payload=invoice.payload,
    ))
    assert calls(trial, AnswerPreCheckoutQuery)[-1].ok is True
    assert await db.fetchval("SELECT order_id FROM star_invoices WHERE id=$1", UUID(invoice.payload.removeprefix("stars:"))) is None

    # Approved purchase stays at the displayed price even if the catalog changes afterwards.
    revision = await db.fetchval("SELECT revision FROM services WHERE id=$1", trial.product)
    await update_service(
        db, trial.product, trial.owner, expected_revision=revision, base_price_stars=50,
        reason="Change catalog after approved checkout",
    )
    charge = uuid4().hex
    payment = SuccessfulPayment(
        currency="XTR", total_amount=amount, invoice_payload=invoice.payload,
        telegram_payment_charge_id=charge, provider_payment_charge_id="",
    )
    session.fail_next_result = scenario == "uncertain_delivery"
    update = await feed(trial, message=incoming(trial, successful_payment=payment))
    order = await db.fetchval("SELECT order_id FROM star_charges WHERE charge_id=$1", charge)
    assert order is not None
    if scenario == "uncertain_delivery":
        assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order) == "AWAITING_FULFILLMENT"
        assert await db.fetchval("SELECT status FROM star_charges WHERE charge_id=$1", charge) == "PAID"
        cached = await db.fetchval("SELECT result_text FROM summary_results WHERE order_id=$1", order)
        await feed(trial, message=incoming(trial, "/orders"))
        assert await db.fetchval("SELECT result_text FROM summary_results WHERE order_id=$1", order) == cached
        assert "summary_delivery_uncertain" in caplog.text

    await persist_payment_update(db, trial.bot.id, update)
    await v0.dispatcher.feed_update(trial.bot, update)
    await feed(trial, message=incoming(trial, successful_payment=payment))
    assert await db.fetchval("SELECT status FROM orders WHERE id=$1", order) == "COMPLETED"
    assert await db.fetchval("SELECT price_snapshot_stars FROM orders WHERE id=$1", order) == amount
    assert await db.fetchval("SELECT service_id FROM orders WHERE id=$1", order) == trial.product
    assert await db.fetchval("SELECT count(*) FROM jobs WHERE order_id=$1", order) == 0
    buyer = await db.fetchval("SELECT id FROM users WHERE telegram_user_id=$1", trial.user.id)
    assert await balance(db, buyer) == Balance(0, 0)
    assert await db.fetchval("SELECT count(*) FROM orders WHERE user_id=$1", buyer) == 1
    for event in ("PAID", "DELIVERED"):
        assert await db.fetchval(
            "SELECT count(*) FROM star_payment_events WHERE charge_id=$1 AND event_type=$2",
            charge, event,
        ) == 1
    assert await db.fetchval(
        "SELECT status FROM telegram_payment_inbox WHERE bot_id=$1 AND update_id=$2",
        trial.bot.id, update.update_id,
    ) == "DONE"
    assert session.result_attempts == (2 if scenario == "uncertain_delivery" else 1)
    result_messages = [m.text for m in session.messages if m.text.startswith("ملخص محلي — الطلب")]
    assert len(result_messages) == 1 and "المنصة" in result_messages[0]
    assert "synthetic-private-transport-body" not in caplog.text
    assert "summary_handler_failed" not in caplog.text


@pytest.mark.asyncio
async def test_offline_closed_checkout_routes_commands_media_and_private_scope(trial, caplog):
    trial.settings.telegram_orders_enabled = False
    trial.settings.telegram_stars_enabled = False
    trial.settings.telegram_payment_terms = ""
    trial.settings.telegram_payment_support = ""
    for command in ("/start", "/services", "/summary", "/terms", "/paysupport", "/cancel", "/unknown"):
        await feed(trial, message=incoming(trial, command))
    await feed(trial, message=incoming(trial, TEXT))
    await feed(trial, message=incoming(trial, photo=[
        PhotoSize(file_id="synthetic-photo", file_unique_id="synthetic-unique", width=10, height=10),
    ]))
    text = "\n".join(message.text for message in trial.session.messages)
    assert "الدفع غير متاح" in text
    assert "لا يوجد عرض غير مدفوع" in text
    assert "الأوامر:" in text and "الملفات والصور والتسجيلات غير مدعومة" in text
    assert calls(trial, SendInvoice) == []
    before = len(trial.session.messages)
    group_message = incoming(trial, "/services").model_copy(update={
        "chat": Chat(id=-12345, type="group", title="Synthetic group"),
    })
    await feed(trial, message=group_message)
    assert len(trial.session.messages) == before
    assert await trial.db.fetchval(
        "SELECT count(*) FROM orders o JOIN users u ON u.id=o.user_id WHERE u.telegram_user_id=$1",
        trial.user.id,
    ) == 0
    assert await trial.db.fetchval(
        "SELECT count(*) FROM star_invoices i JOIN users u ON u.id=i.user_id WHERE u.telegram_user_id=$1",
        trial.user.id,
    ) == 0
    assert "summary_handler_failed" not in caplog.text


@pytest.fixture
def office(trial, monkeypatch):
    clock = SimpleNamespace(now=100.0)
    cache = OfficeTrial(clock=lambda: clock.now)
    trial.settings.telegram_orders_enabled = False
    trial.settings.telegram_stars_enabled = False
    trial.settings.office_trial_enabled = True
    trial.settings.office_trial_user_ids = [trial.user.id, trial.user.id + 1]
    trial.settings.office_trial_ttl_seconds = 60
    monkeypatch.setattr(office_ui, "get_settings", lambda: trial.settings)
    monkeypatch.setattr(office_ui, "trial", cache)
    trial.clock, trial.cache = clock, cache
    return trial


async def assert_office_unpaid(office):
    assert calls(office, SendInvoice) == []
    assert calls(office, RefundStarPayment) == []
    assert await office.db.fetchval(
        "SELECT count(*) FROM users WHERE telegram_user_id=$1", office.user.id,
    ) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["success", "uncertain_delivery"])
async def test_offline_word_dispatch_receipt_replay_and_explicit_resend(office, scenario, caplog):
    payload = 'تقرير العمل\nنص عربي وEnglish والطلب INV-2026 والتاريخ 2026-10-03.'
    office.session.fail_next_document = scenario == "uncertain_delivery"
    update = await feed(office, message=incoming(
        office, "/word@synthetic_office_bot " + payload,
    ))
    result = office.cache._files[office.user.id]
    first_call = calls(office, SendDocument)[0]
    assert first_call.chat_id == office.user.id and first_call.protect_content is True
    assert first_call.document.filename == "document.docx"
    assert first_call.document.data == result.artifact.content
    assert "تجريبي" in first_call.caption
    assert result.delivery_state == ("uncertain" if scenario == "uncertain_delivery" else "delivered")
    if scenario == "uncertain_delivery":
        assert result.delivered_message_id is None
        assert "تعذر تأكيد" in office.session.messages[-1].text
        assert "office_delivery_uncertain" in caplog.text
    else:
        assert result.delivered_message_id == office.session.messages[-1].message_id
        assert office.session.messages[-1].document.mime_type == result.artifact.mime_type

    await v0.dispatcher.feed_update(office.bot, update)
    assert len(calls(office, SendDocument)) == 1
    assert office.cache._files[office.user.id].expires_at == result.expires_at
    await press(office, office.session.messages[-1], f"office:get:{result.token}")
    assert len(calls(office, SendDocument)) == 2
    assert calls(office, SendDocument)[-1].document.data == first_call.document.data
    delivered = office.cache._files[office.user.id]
    assert delivered.delivery_state == "delivered"
    assert delivered.delivered_message_id == office.session.messages[-1].message_id
    assert "synthetic-private-document-body" not in caplog.text
    assert payload not in caplog.text
    assert "summary_handler_failed" not in caplog.text
    await assert_office_unpaid(office)


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["disabled", "not_allowlisted", "group", "wrong_chat"])
async def test_offline_word_dispatch_denies_intake_without_files_or_payment(office, reason, caplog):
    incoming_message = incoming(office, "/word عنوان\nنص تجريبي")
    if reason == "disabled":
        office.settings.office_trial_enabled = False
    elif reason == "not_allowlisted":
        office.settings.office_trial_user_ids = []
    else:
        incoming_message = incoming_message.model_copy(update={
            "chat": Chat(id=-12345 if reason == "group" else office.user.id + 1,
                         type="group" if reason == "group" else "private"),
        })
    await feed(office, message=incoming_message)
    assert office.cache._files == {}
    assert calls(office, SendDocument) == []
    assert "summary_handler_failed" not in caplog.text
    await assert_office_unpaid(office)


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["foreign_owner", "expired", "replaced", "disabled"])
async def test_offline_word_dispatch_rechecks_retrieval_permissions(office, reason, caplog):
    await feed(office, message=incoming(office, "/word عنوان\nنص تجريبي"))
    result = office.cache._files[office.user.id]
    response = office.session.messages[-1]
    if reason == "foreign_owner":
        office.user = office.user.model_copy(update={"id": office.user.id + 1})
        # Model a copied button in the other allowlisted owner's private chat.
        response = response.model_copy(update={"chat": Chat(id=office.user.id, type="private")})
    elif reason == "expired":
        office.clock.now += 60
    elif reason == "replaced":
        await feed(office, message=incoming(office, "/word عنوان جديد\nنص جديد"))
    else:
        office.settings.office_trial_enabled = False
    before = len(calls(office, SendDocument))
    await press(office, response, f"office:get:{result.token}")
    assert len(calls(office, SendDocument)) == before
    assert calls(office, AnswerCallbackQuery)[-1].show_alert is True
    assert "summary_handler_failed" not in caplog.text
    await assert_office_unpaid(office)


@pytest.mark.asyncio
async def test_offline_word_dispatch_help_and_invalid_text_do_not_reach_checkout(office, caplog):
    await feed(office, message=incoming(office, "/word"))
    assert "4,000" in office.session.messages[-1].text
    assert "لا تكتب أو تعيد صياغة" in office.session.messages[-1].text
    for payload in ("عنوان", "أ" * 4001, "عنوان\nprivate\u202e"):
        await feed(office, message=incoming(office, "/word " + payload))
    assert office.cache._files == {}
    assert calls(office, SendDocument) == []
    assert "private" not in caplog.text
    assert "summary_handler_failed" not in caplog.text
    await assert_office_unpaid(office)
