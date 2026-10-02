"""Direct XTR invoices and immutable receipts; never credit or convert the SAR wallet."""

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID, uuid4

import asyncpg

from platform_core.ledger import _lock_wallet
from platform_core.telegram_workflow import StaleQuote
from platform_core.text_summary import SLUG, TEXT_INPUT_SCHEMA

MAX_STARS = 100_000


class StarsMismatch(ValueError):
    pass


@dataclass(frozen=True)
class StarInvoice:
    id: UUID
    amount_stars: int
    order_id: UUID | None = None
    title: str = "دمج ملفات PDF"

    @property
    def payload(self) -> str:
        return f"stars:{self.id.hex}"


def invoice_id(payload: str) -> UUID:
    if not isinstance(payload, str) or len(payload) != 38 or not payload.startswith("stars:"):
        raise StarsMismatch("invalid invoice payload")
    try:
        parsed = UUID(hex=payload[6:])
    except ValueError as exc:
        raise StarsMismatch("invalid invoice payload") from exc
    if payload != f"stars:{parsed.hex}":
        raise StarsMismatch("noncanonical invoice payload")
    return parsed


async def _offer(connection, user_id, workflow_id):
    row = await connection.fetchrow(
        """SELECT w.*,s.base_price_stars,s.enabled,c.enabled AS category_enabled,
           s.slug,s.name_ar,s.processor_type,s.input_schema,
           t.input_digest,t.retention_until AS text_retention_until FROM telegram_workflows w
           JOIN services s ON s.id=w.service_id JOIN service_categories c ON c.id=s.category_id
           LEFT JOIN summary_inputs t ON t.workflow_id=w.id
           WHERE w.id=$1 AND w.user_id=$2 FOR UPDATE OF w,s""", workflow_id, user_id,
    )
    if not row:
        raise StarsMismatch("workflow not owned")
    files = await connection.fetch(
        "SELECT file_id FROM telegram_workflow_files WHERE workflow_id=$1 ORDER BY position",
        workflow_id,
    )
    return row, [f["file_id"] for f in files]


async def _files_ready(connection, user_id, file_ids) -> bool:
    if not 2 <= len(file_ids) <= 10 or len(set(file_ids)) != len(file_ids):
        return False
    count = await connection.fetchval(
        """SELECT count(*) FROM files WHERE id=ANY($1::uuid[]) AND owner_user_id=$2
           AND file_type='INPUT' AND mime_type='application/pdf' AND status='READY'
           AND retention_until>now()""", list(file_ids), user_id,
    )
    return count == len(file_ids)


def _current_offer(row, files, invoice, *, check_price=True) -> bool:
    schema = row["input_schema"]
    if isinstance(schema, str):
        schema = json.loads(schema)
    supported = (
        (row["slug"] == "merge-pdf" and schema == {"min_files": 2, "max_files": 10, "file_mime": "application/pdf"})
        or (row["slug"] == SLUG and schema == TEXT_INPUT_SCHEMA
            and row["input_digest"] == invoice.get("input_text_digest") and not files)
    )
    return (supported
            and row["status"] == "CONFIRMING" and row["quote_revision"] == invoice["quote_revision"]
            and row["enabled"] and row["category_enabled"]
            and row["processor_type"] == "tool" and files == list(invoice["file_ids"])
            and row["quoted_price_stars"] == invoice["amount_stars"]
            and row["quoted_terms_digest"] == invoice["terms_digest"]
            and (not check_price or row["base_price_stars"] == invoice["amount_stars"]))


async def _inputs_ready(connection, invoice, row, files):
    if row["slug"] == SLUG:
        return bool(await connection.fetchval(
            "SELECT 1 FROM summary_inputs WHERE workflow_id=$1 AND user_id=$2 AND retention_until>now()",
            row["id"], row["user_id"],
        ))
    return await _files_ready(connection, invoice["user_id"], files)


async def create_star_invoice(
    connection: asyncpg.Connection, user_id: UUID, workflow_id: UUID,
    quote_revision: int, terms_text: str, *, service_slug: str | None = None,
) -> StarInvoice:
    terms_text = terms_text.strip()
    terms_digest = hashlib.sha256(terms_text.encode()).hexdigest()
    if type(quote_revision) is not int or quote_revision < 1 or not terms_text:
        raise StaleQuote("invalid Stars offer")
    async with connection.transaction():
        await _lock_wallet(connection, user_id)
        row, files = await _offer(connection, user_id, workflow_id)
        if row["quote_revision"] != quote_revision or (service_slug and row["slug"] != service_slug):
            raise StaleQuote("offer changed")
        existing = await connection.fetchrow(
            "SELECT * FROM star_invoices WHERE workflow_id=$1 AND quote_revision=$2",
            workflow_id, quote_revision,
        )
        if existing and existing["order_id"]:
            return StarInvoice(existing["id"], existing["amount_stars"], existing["order_id"], row["name_ar"])
        offer = {"quote_revision": quote_revision, "file_ids": files,
                 "amount_stars": row["quoted_price_stars"], "terms_digest": terms_digest,
                 "input_text_digest": row["input_digest"], "user_id": user_id}
        if (type(offer["amount_stars"]) is not int
                or not 1 <= offer["amount_stars"] <= MAX_STARS
                or not _current_offer(row, files, offer)
                or not await _inputs_ready(connection, offer, row, files)):
            raise StaleQuote("Stars offer unavailable or changed")
        if existing:
            return StarInvoice(existing["id"], existing["amount_stars"], title=row["name_ar"])
        payment_id = uuid4()
        await connection.execute(
            """INSERT INTO star_invoices
               (id,user_id,workflow_id,quote_revision,service_id,amount_stars,file_ids,terms_digest,terms_text,input_text_digest)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
            payment_id, user_id, workflow_id, quote_revision, row["service_id"],
            row["quoted_price_stars"], files, terms_digest, terms_text, row["input_digest"],
        )
        return StarInvoice(payment_id, row["quoted_price_stars"], title=row["name_ar"])


async def _owned_invoice(connection, telegram_user_id, payload):
    row = await connection.fetchrow(
        """SELECT i.*,u.telegram_user_id FROM star_invoices i JOIN users u ON u.id=i.user_id
           WHERE i.id=$1""", invoice_id(payload),
    )
    if not row or row["telegram_user_id"] != telegram_user_id:
        raise StarsMismatch("invoice not owned")
    return row


def _amount_matches(invoice, currency, amount):
    if currency != "XTR" or type(amount) is not int or amount != invoice["amount_stars"]:
        raise StarsMismatch("invoice currency or amount mismatch")


async def approve_star_checkout(
    connection, telegram_user_id, payload, currency, amount, query_id, terms_digest,
    *, service_slug: str | None = None,
):
    async with connection.transaction():
        invoice = await _owned_invoice(connection, telegram_user_id, payload)
        _amount_matches(invoice, currency, amount)
        await _lock_wallet(connection, invoice["user_id"])
        row, files = await _offer(connection, invoice["user_id"], invoice["workflow_id"])
        invoice = await connection.fetchrow(
            "SELECT * FROM star_invoices WHERE id=$1 FOR UPDATE", invoice["id"],
        )
        if ((service_slug and row["slug"] != service_slug)
                or invoice["order_id"] or invoice["terms_digest"] != terms_digest
                or invoice["checkout_query_id"] not in (None, query_id)
                or not _current_offer(row, files, invoice)
                or not await _inputs_ready(connection, invoice, row, files)):
            raise StarsMismatch("checkout unavailable")
        await connection.execute(
            "UPDATE star_invoices SET checkout_query_id=$2 WHERE id=$1", invoice["id"], query_id,
        )


async def _event(connection, charge_id, kind, receipt=None):
    await connection.execute(
        """INSERT INTO star_payment_events (charge_id,event_type,receipt) VALUES ($1,$2,$3)
           ON CONFLICT (charge_id,event_type) DO NOTHING""", charge_id, kind, receipt,
    )


async def accept_star_payment(
    connection, telegram_user_id, payload, currency, amount, charge_id, *, allow_fulfillment,
    service_slug: str | None = None,
) -> UUID | None:
    if not isinstance(charge_id, str) or not 1 <= len(charge_id) <= 200:
        raise StarsMismatch("invalid charge identity")
    async with connection.transaction():
        invoice = await _owned_invoice(connection, telegram_user_id, payload)
        _amount_matches(invoice, currency, amount)
        await _lock_wallet(connection, invoice["user_id"])
        row, files = await _offer(connection, invoice["user_id"], invoice["workflow_id"])
        invoice = await connection.fetchrow(
            "SELECT * FROM star_invoices WHERE id=$1 FOR UPDATE", invoice["id"],
        )
        prior = await connection.fetchrow(
            "SELECT * FROM star_charges WHERE charge_id=$1 FOR UPDATE", charge_id,
        )
        if prior:
            if prior["invoice_id"] != invoice["id"]:
                raise StarsMismatch("charge reused for another invoice")
            await _event(connection, charge_id, "PAID")
            return prior["order_id"] if prior["status"] in {"PAID", "DELIVERED"} else None
        await connection.execute(
            "INSERT INTO star_charges (charge_id,invoice_id,status) VALUES ($1,$2,'PAID')",
            charge_id, invoice["id"],
        )
        await _event(connection, charge_id, "PAID")
        eligible = (allow_fulfillment and (service_slug is None or row["slug"] == service_slug)
                    and invoice["checkout_query_id"] and not invoice["order_id"]
                    and _current_offer(row, files, invoice, check_price=False)
                    and await _inputs_ready(connection, invoice, row, files))
        if not eligible:
            await connection.execute(
                "UPDATE star_charges SET status='REFUND_PENDING' WHERE charge_id=$1", charge_id,
            )
            await _event(connection, charge_id, "REFUND_REQUESTED")
            return None
        order_id = uuid4()
        await connection.execute(
            """INSERT INTO orders
               (id,user_id,service_id,client_request_key,channel,price_snapshot_halalas,
                currency,price_snapshot_stars,status)
               VALUES ($1,$2,$3,$4,'telegram',0,'XTR',$5,'QUEUED')""",
            order_id, invoice["user_id"], invoice["service_id"],
            f"stars:{invoice['id']}", invoice["amount_stars"],
        )
        for position, file_id in enumerate(invoice["file_ids"]):
            await connection.execute(
                "INSERT INTO order_files (order_id,position,file_id) VALUES ($1,$2,$3)",
                order_id, position, file_id,
            )
        if row["slug"] != SLUG:
            await connection.execute(
                "INSERT INTO jobs (id,order_id,status) VALUES ($1,$2,'PENDING')", uuid4(), order_id,
            )
        await connection.execute("UPDATE star_invoices SET order_id=$2 WHERE id=$1",
                                 invoice["id"], order_id)
        await connection.execute("UPDATE star_charges SET order_id=$2 WHERE charge_id=$1",
                                 charge_id, order_id)
        await connection.execute(
            """UPDATE telegram_workflows SET status='SUBMITTED',order_id=$2,updated_at=now()
               WHERE id=$1""", invoice["workflow_id"], order_id,
        )
        return order_id


async def mark_star_delivery(connection, order_id, receipt):
    charge = await connection.fetchrow(
        "SELECT charge_id,status FROM star_charges WHERE order_id=$1 FOR UPDATE", order_id,
    )
    if not charge or charge["status"] != "PAID":
        raise StarsMismatch("Stars charge is not available for fulfillment")
    await _event(connection, charge["charge_id"], "DELIVERED", receipt)
    await connection.execute(
        "UPDATE star_charges SET status='DELIVERED' WHERE charge_id=$1", charge["charge_id"],
    )


async def request_star_refund(connection, order_id):
    charge = await connection.fetchrow(
        "SELECT charge_id,status FROM star_charges WHERE order_id=$1 FOR UPDATE", order_id,
    )
    if charge and charge["status"] == "PAID":
        await connection.execute(
            "UPDATE star_charges SET status='REFUND_PENDING' WHERE charge_id=$1", charge["charge_id"],
        )
        await _event(connection, charge["charge_id"], "REFUND_REQUESTED")


async def confirm_star_refund(connection, telegram_user_id, payload, currency, amount, charge_id):
    async with connection.transaction():
        invoice = await _owned_invoice(connection, telegram_user_id, payload)
        _amount_matches(invoice, currency, amount)
        await _lock_wallet(connection, invoice["user_id"])
        # Lock an existing order before its charge, matching processing/delivery lock order.
        order_id = await connection.fetchval(
            "SELECT order_id FROM star_charges WHERE charge_id=$1", charge_id,
        )
        if order_id:
            await connection.fetchval("SELECT id FROM orders WHERE id=$1 FOR UPDATE", order_id)
        prior = await connection.fetchrow(
            "SELECT * FROM star_charges WHERE charge_id=$1 FOR UPDATE", charge_id,
        )
        if prior and prior["invoice_id"] != invoice["id"]:
            raise StarsMismatch("refund charge does not match")
        if not prior:
            await connection.execute(
                "INSERT INTO star_charges (charge_id,invoice_id,status) VALUES ($1,$2,'REFUNDED')",
                charge_id, invoice["id"],
            )
        else:
            await connection.execute(
                "UPDATE star_charges SET status='REFUNDED' WHERE charge_id=$1", charge_id,
            )
        await _event(connection, charge_id, "REFUNDED")
        if order_id:
            await connection.execute("UPDATE orders SET status='REFUNDED' WHERE id=$1", order_id)

