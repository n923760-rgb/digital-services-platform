"""Direct summary application functions; every financial transition stays atomic."""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

from platform_core.ledger import _lock_wallet
from platform_core.orders import ensure_telegram_user
from platform_core.service_catalog import available_summary_products
from platform_core.stars_payments import mark_star_delivery, request_star_refund
from platform_core.telegram_workflow import cancel_active
from platform_core.text_summary import (
    SLUG,
    TEXT_INPUT_SCHEMA,
    LocalSummarizer,
    validate_summary,
    validate_text,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SummaryQuote:
    workflow_id: UUID
    revision: int
    price_stars: int
    service_name: str = ""


async def quote_summary(connection, telegram_user_id, message_id, text, terms, *, retention_days=30):
    text = validate_text(text)
    await purge_expired_summary_text(connection)
    if not terms.strip() or message_id <= 0 or not 1 <= retention_days <= 365:
        raise ValueError("invalid_summary_offer")
    async with connection.transaction():
        user_id = await ensure_telegram_user(connection, telegram_user_id)
        await _lock_wallet(connection, user_id)
        existing = await connection.fetchrow(
            """SELECT t.input_text,w.id,w.quote_revision,w.quoted_price_stars,s.name_ar FROM summary_inputs t
               JOIN telegram_workflows w ON w.id=t.workflow_id JOIN services s ON s.id=w.service_id
               WHERE t.user_id=$1 AND t.telegram_message_id=$2""", user_id, message_id,
        )
        if existing:
            if existing["input_text"] != text:
                raise ValueError("summary_message_reused")
            return SummaryQuote(existing["id"], existing["quote_revision"], existing["quoted_price_stars"], existing["name_ar"])
        selected = await connection.fetchval(
            """SELECT w.service_id FROM telegram_workflows w JOIN services s ON s.id=w.service_id
               WHERE w.user_id=$1 AND w.status IN ('COLLECTING','CONFIRMING')
               AND s.processor_key=$2 ORDER BY w.updated_at DESC,w.id DESC LIMIT 1""", user_id, SLUG,
        )
        if selected is None:
            products = await available_summary_products(connection)
            if len(products) != 1:
                raise ValueError("summary_product_selection_required")
            selected = products[0].id
        service = await connection.fetchrow(
            """SELECT s.id,s.name_ar,s.base_price_stars,s.input_schema FROM services s
               JOIN service_categories c ON c.id=s.category_id
               WHERE s.id=$1 AND s.processor_key=$2 AND s.processor_type='tool' AND s.enabled AND c.enabled
               AND s.base_price_stars IS NOT NULL FOR UPDATE OF s""", selected, SLUG,
        )
        if not service:
            raise ValueError("summary_service_unavailable")
        schema = service["input_schema"]
        if isinstance(schema, str):
            schema = json.loads(schema)
        if schema != TEXT_INPUT_SCHEMA:
            raise ValueError("summary_schema_unavailable")
        await connection.execute(
            """UPDATE telegram_workflows SET status='CANCELLED',updated_at=now()
               WHERE user_id=$1 AND status IN ('COLLECTING','CONFIRMING')""", user_id,
        )
        workflow_id = uuid4()
        await connection.execute(
            """INSERT INTO telegram_workflows
               (id,user_id,service_id,status,quote_revision,quoted_price_stars,quoted_terms_digest)
               VALUES ($1,$2,$3,'CONFIRMING',1,$4,$5)""", workflow_id, user_id,
            service["id"], service["base_price_stars"], hashlib.sha256(terms.strip().encode()).hexdigest(),
        )
        await connection.execute(
            """INSERT INTO summary_inputs
               (workflow_id,user_id,telegram_message_id,input_text,input_digest,retention_until)
               VALUES ($1,$2,$3,$4,$5,now()+$6*interval '1 day')""", workflow_id, user_id,
            message_id, text, hashlib.sha256(text.encode()).hexdigest(), retention_days,
        )
        return SummaryQuote(workflow_id, 1, service["base_price_stars"], service["name_ar"])


async def _owned_order(connection, telegram_user_id, order_id):
    user_id = await connection.fetchval(
        "SELECT user_id FROM orders o JOIN users u ON u.id=o.user_id WHERE o.id=$1 AND u.telegram_user_id=$2",
        order_id, telegram_user_id,
    )
    if not user_id:
        raise ValueError("summary_order_not_owned")
    await _lock_wallet(connection, user_id)
    row = await connection.fetchrow(
        """SELECT o.id,o.status,o.user_id,c.status AS charge_status,t.input_text,
                  t.retention_until,(t.retention_until>now() AND t.input_digest=i.input_text_digest) AS input_available,
                  r.result_text,r.retention_until>now() AS result_available
           FROM orders o JOIN services s ON s.id=o.service_id
           JOIN star_invoices i ON i.order_id=o.id JOIN star_charges c ON c.order_id=o.id
           LEFT JOIN summary_inputs t ON t.workflow_id=i.workflow_id
           LEFT JOIN summary_results r ON r.order_id=o.id
           WHERE o.id=$1 AND s.processor_key=$2 FOR UPDATE OF o""", order_id, SLUG,
    )
    if not row:
        raise ValueError("not_summary_order")
    return row


async def fail_summary(connection, telegram_user_id, order_id):
    async with connection.transaction():
        row = await _owned_order(connection, telegram_user_id, order_id)
        if row["status"] in {"QUEUED", "PROCESSING", "AWAITING_FULFILLMENT"}:
            await connection.execute("UPDATE orders SET status='FAILED' WHERE id=$1", order_id)
            await request_star_refund(connection, order_id)


async def execute_summary(connection, telegram_user_id, order_id, summarizer=None):
    """One direct attempt; result reuse prevents repeating successful provider work."""
    async with connection.transaction():
        row = await _owned_order(connection, telegram_user_id, order_id)
        if row["status"] == "AWAITING_FULFILLMENT" and row["charge_status"] == "PAID":
            if row["result_available"]:
                return row["result_text"]
            await fail_summary(connection, telegram_user_id, order_id)
            return None
        if row["status"] != "QUEUED" or row["charge_status"] != "PAID":
            return None
        if not row["input_available"]:
            await fail_summary(connection, telegram_user_id, order_id)
            return None
        await connection.execute("UPDATE orders SET status='PROCESSING' WHERE id=$1", order_id)
        source, retention = row["input_text"], row["retention_until"]
    # No database transaction/lock spans external provider work.
    try:
        async with asyncio.timeout(5):
            result = validate_summary(await (summarizer or LocalSummarizer()).summarize(source))
    except Exception as exc:  # Classify, refund atomically and propagate; never hide provider faults.
        logger.warning("summary_provider_failed:%s", type(exc).__name__)
        await fail_summary(connection, telegram_user_id, order_id)
        raise
    async with connection.transaction():
        row = await _owned_order(connection, telegram_user_id, order_id)
        if row["status"] != "PROCESSING" or row["charge_status"] != "PAID":
            return None
        if not row["input_available"]:
            await fail_summary(connection, telegram_user_id, order_id)
            return None
        await connection.execute(
            "INSERT INTO summary_results (order_id,result_text,retention_until) VALUES ($1,$2,$3)",
            order_id, result, retention,
        )
        await connection.execute("UPDATE orders SET status='AWAITING_FULFILLMENT' WHERE id=$1", order_id)
    return result


async def acknowledge_summary(connection, telegram_user_id, order_id, receipt):
    if not receipt or len(receipt) > 200:
        raise ValueError("invalid_summary_receipt")
    async with connection.transaction():
        row = await _owned_order(connection, telegram_user_id, order_id)
        if row["status"] == "COMPLETED":
            return
        if row["status"] != "AWAITING_FULFILLMENT" or not row["result_available"]:
            raise ValueError("summary_not_deliverable")
        await mark_star_delivery(connection, order_id, receipt)
        await connection.execute(
            """UPDATE orders SET status='COMPLETED',completed_at=now(),delivery_receipt=$2
               WHERE id=$1""", order_id, receipt,
        )


async def paid_summary_orders(connection, telegram_user_id=None):
    rows = await connection.fetch(
        """SELECT o.id,u.telegram_user_id FROM orders o JOIN services s ON s.id=o.service_id
           JOIN users u ON u.id=o.user_id WHERE s.processor_key=$1
           AND o.status IN ('QUEUED','AWAITING_FULFILLMENT')
           AND ($2::bigint IS NULL OR u.telegram_user_id=$2)
           ORDER BY o.created_at,o.id LIMIT 20""", SLUG, telegram_user_id,
    )
    return rows


async def recover_interrupted_summaries(connection):
    """One-poller startup recovery: uncertain interrupted work refunds, never auto-recharges."""
    rows = await connection.fetch(
        """SELECT o.id,u.telegram_user_id FROM orders o JOIN services s ON s.id=o.service_id
           JOIN users u ON u.id=o.user_id WHERE s.processor_key=$1 AND o.status='PROCESSING'""", SLUG,
    )
    for row in rows:
        await fail_summary(connection, row["telegram_user_id"], row["id"])
        logger.warning("summary_interrupted_refund_requested")


async def require_no_legacy_work(connection):
    active = await connection.fetchval(
        """SELECT count(*) FROM orders o JOIN services s ON s.id=o.service_id
           WHERE s.processor_key IS DISTINCT FROM $1 AND o.status IN
           ('RESERVED','QUEUED','PROCESSING','AWAITING_FULFILLMENT','FULFILLING')""", SLUG,
    )
    if active:
        raise RuntimeError("Resolve outstanding legacy orders before switching the active bot")


async def purge_expired_summary_text(connection):
    """Purge raw text on application activity/startup; retain financial hashes and history."""
    async with connection.transaction():
        await connection.execute("DELETE FROM summary_results WHERE retention_until<=now()")
        await connection.execute("DELETE FROM summary_inputs WHERE retention_until<=now()")


async def cancel_summary_offer(connection, telegram_user_id):
    user_id = await connection.fetchval(
        "SELECT id FROM users WHERE telegram_user_id=$1", telegram_user_id,
    )
    return await cancel_active(connection, user_id) if user_id else False


async def select_summary_product(connection, telegram_user_id, service_id):
    """Persist private selection in the existing workflow; superseded unpaid quotes stop working."""
    async with connection.transaction():
        user_id = await ensure_telegram_user(connection, telegram_user_id)
        await _lock_wallet(connection, user_id)
        products = await available_summary_products(connection, service_id=service_id)
        if not products:
            raise ValueError("summary_product_unavailable")
        current = await connection.fetchrow(
            """SELECT id,service_id FROM telegram_workflows WHERE user_id=$1
               AND status IN ('COLLECTING','CONFIRMING') FOR UPDATE""", user_id,
        )
        if current and current["service_id"] == service_id:
            return products[0]
        await connection.execute(
            """UPDATE telegram_workflows SET status='CANCELLED',updated_at=now()
               WHERE user_id=$1 AND status IN ('COLLECTING','CONFIRMING')""", user_id,
        )
        await connection.execute(
            """INSERT INTO telegram_workflows (id,user_id,service_id,status)
               VALUES ($1,$2,$3,'COLLECTING')""", uuid4(), user_id, service_id,
        )
        return products[0]
