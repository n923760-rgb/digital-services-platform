"""Private unpaid Word experiment; no catalog, order, wallet or Stars calls."""

import asyncio
import logging

from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from platform_core.config import get_settings
from platform_core.office_docx import InvalidOfficeInput, OfficeOutputLimitExceeded
from platform_core.office_trial import OfficeTrial, TrialPolicy, TrialRejected

logger = logging.getLogger(__name__)
trial = OfficeTrial()
DELIVERY_TIMEOUT_SECONDS = 15
USAGE = (
    "تجربة مجانية لتنسيق النص فقط؛ لا تكتب أو تعيد صياغة المحتوى.\n"
    "أرسل في رسالة واحدة:\n/word عنوان المستند\nالنص المطلوب تنسيقه\n"
    "الحد 4,000 حرف والعنوان 200 حرف. افصل الفقرات بسطر فارغ.\n"
    "الملف مؤقت داخل البوت ويُفقد عند إعادة التشغيل. لا ترسل بيانات حساسة."
)


def policy():
    settings = get_settings()
    return TrialPolicy(settings.office_trial_enabled, frozenset(settings.office_trial_user_ids),
                       settings.office_trial_ttl_seconds)


def private(message, user):
    return (isinstance(message, Message) and message.chat.type == "private"
            and user is not None and not user.is_bot and message.chat.id == user.id)


def retry_button(token):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="إعادة إرسال الملف قبل انتهاء الصلاحية",
                             callback_data=f"office:get:{token}"),
    ]])


async def notice(message, text, **kwargs):
    try:
        await message.answer(text, **kwargs)
    except (TelegramAPIError, OSError) as exc:
        logger.warning("office_notice_unavailable:%s", type(exc).__name__)


async def deliver(message, bot, owner_id, token, current_policy, explicit_retry=False):
    try:
        result = await asyncio.to_thread(trial.claim_delivery, owner_id, token,
                                         current_policy, explicit_retry)
    except TrialRejected as exc:
        logger.info("office_retrieval_rejected:%s", exc.code)
        text = ("جارٍ تسليم الملف؛ انتظر قبل إعادة المحاولة." if exc.code == "trial_delivery_busy"
                else "الملف غير متاح أو انتهت صلاحيته. أرسل طلبًا جديدًا عبر /word.")
        await notice(message, text)
        return
    if result is None:
        return
    try:
        async with asyncio.timeout(DELIVERY_TIMEOUT_SECONDS):
            sent = await bot.send_document(
                chat_id=owner_id,
                document=BufferedInputFile(result.artifact.content, filename="document.docx"),
                caption=(f"ملف Word تجريبي — الطلب {result.request_id}. "
                         "تنسيق للنص، وليس كتابة بالذكاء الاصطناعي. "
                         "قد يحتوي النص المنسوخ على علامات اتجاه غير مرئية. "
                         "اختبره على Word والجوال؛ احفظ نسختك."),
                reply_markup=retry_button(token), protect_content=True,
            )
        try:
            await asyncio.to_thread(trial.acknowledge, owner_id, token, sent.chat.id,
                                     sent.message_id, current_policy)
        except TrialRejected as exc:
            # Expiry/replacement during remote I/O does not undo an accepted send.
            logger.info("office_receipt_not_retained:%s", exc.code)
    except (TelegramAPIError, OSError) as exc:
        # An accepted send can still end in timeout. Keep the cached bytes for
        # explicit retry only; never claim success or automatically send twice.
        logger.warning("office_delivery_uncertain:%s", type(exc).__name__)
        await notice(message, "تعذر تأكيد التسليم. يمكنك إعادة الإرسال قبل انتهاء الصلاحية؛ "
                     "قد تصلك نسخة مكررة. لا يوجد دفع لهذه التجربة.",
                     reply_markup=retry_button(token))
    except Exception as exc:
        logger.error("office_delivery_failed:%s", type(exc).__name__)
        raise
    finally:
        # Also releases a cancelled send. Cancellation itself still propagates.
        try:
            await asyncio.to_thread(trial.release_delivery, owner_id, token, current_policy)
        except TrialRejected as exc:
            logger.info("office_delivery_release_unavailable:%s", exc.code)


async def create(message, bot, payload):
    if not private(message, message.from_user):
        logger.info("office_private_intake_rejected")
        return
    current_policy = policy()
    try:
        trial.require_access(message.from_user.id, current_policy)
        if not payload:
            await notice(message, USAGE)
            return
        result = await asyncio.to_thread(
            trial.create, message.from_user.id, message.message_id, payload, current_policy,
        )
    except TrialRejected as exc:
        logger.info("office_intake_rejected:%s", exc.code)
        if exc.code in ("trial_unavailable", "invalid_trial_policy"):
            await notice(message, "تجربة Word غير متاحة لهذا الحساب.")
        elif not payload or exc.code in ("trial_text_limit", "trial_title_and_body_required"):
            await notice(message, USAGE)
        else:
            await notice(message, "تعذر إنشاء الملف المؤقت. أرسل طلبًا جديدًا لاحقًا عبر /word.")
        return
    except InvalidOfficeInput as exc:
        logger.info("office_format_input_rejected:%s", exc.code)
        await notice(message, "تحقق من طول العنوان والنص وعلامات الاتجاه.\n" + USAGE)
        return
    except OfficeOutputLimitExceeded:
        logger.warning("office_output_limit")
        await notice(message, "تعذر إنشاء ملف ضمن حدود التجربة. جرّب نصًا أقصر.")
        return
    except Exception as exc:
        logger.error("office_generation_failed:%s", type(exc).__name__)
        raise
    await deliver(message, bot, message.from_user.id, result.token, current_policy)


async def resend(callback, bot):
    if not private(callback.message, callback.from_user):
        logger.info("office_private_callback_rejected")
        await callback.answer("الملف غير متاح.", show_alert=True)
        return
    token = (callback.data or "").removeprefix("office:get:")
    try:
        await asyncio.to_thread(trial.get, callback.from_user.id, token, policy())
    except TrialRejected as exc:
        logger.info("office_callback_rejected:%s", exc.code)
        await callback.answer("الملف غير متاح أو انتهت صلاحيته.", show_alert=True)
        return
    await callback.answer()
    await deliver(callback.message, bot, callback.from_user.id, token, policy(), explicit_retry=True)
