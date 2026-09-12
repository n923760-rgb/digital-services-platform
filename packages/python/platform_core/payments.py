"""Provider-independent top-up accounting; only a verified adapter may confirm payment."""

import re
from dataclasses import dataclass
from typing import Mapping, Protocol
from uuid import UUID, uuid4

import asyncpg

from platform_core.ledger import Balance, IdempotencyConflict, balance, credit

PROVIDER = re.compile(r"[a-z][a-z0-9_-]{1,39}\Z")


class PaymentMismatch(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedTopup:
    provider: str
    event_id: str
    payment_id: UUID
    provider_reference: str
    amount_halalas: int
    currency: str


class PaymentProviderAdapter(Protocol):
    def verify_paid_event(self, raw_body: bytes, headers: Mapping[str, str]) -> VerifiedTopup:
        """Reject invalid signatures; only return fully verified paid events."""
        ...


def _valid_text(value: str) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 200 and value == value.strip()


async def create_topup_intent(
    connection: asyncpg.Connection, user_id: UUID, amount_halalas: int,
    provider: str, client_request_key: str,
) -> UUID:
    """Trusted application entrypoint; checkout initiation is not exposed until a provider exists."""
    if not PROVIDER.fullmatch(provider) or not _valid_text(client_request_key):
        raise ValueError("invalid top-up identity")
    if not 0 < amount_halalas <= 10_000_000:
        raise ValueError("invalid top-up amount")
    async with connection.transaction():
        # User row lock serializes concurrent submissions sharing the same client request key.
        if not await connection.fetchval("SELECT 1 FROM users WHERE id=$1 FOR UPDATE", user_id):
            raise ValueError("user missing")
        if not await connection.fetchval("SELECT 1 FROM wallets WHERE user_id=$1", user_id):
            raise ValueError("wallet missing")
        existing = await connection.fetchrow(
            """SELECT id,amount_halalas,provider FROM payments
               WHERE user_id=$1 AND client_request_key=$2""", user_id, client_request_key,
        )
        if existing:
            if (existing["amount_halalas"], existing["provider"]) != (amount_halalas, provider):
                raise IdempotencyConflict("request key reused for different top-up")
            return existing["id"]
        payment_id = uuid4()
        await connection.execute(
            """INSERT INTO payments
               (id,user_id,provider,payment_type,amount_halalas,client_request_key)
               VALUES ($1,$2,$3,'WALLET_TOPUP',$4,$5)""",
            payment_id, user_id, provider, amount_halalas, client_request_key,
        )
        return payment_id


async def bind_provider_reference(
    connection: asyncpg.Connection, payment_id: UUID, provider_reference: str,
) -> None:
    """Persist the provider checkout reference before accepting its paid event."""
    if not _valid_text(provider_reference):
        raise ValueError("invalid provider reference")
    try:
        async with connection.transaction():
            row = await connection.fetchrow(
                "SELECT status,provider_reference FROM payments WHERE id=$1 FOR UPDATE", payment_id,
            )
            if not row:
                raise ValueError("top-up missing")
            if row["provider_reference"] is not None:
                if row["provider_reference"] != provider_reference:
                    raise IdempotencyConflict("top-up already bound to another checkout")
                return
            if row["status"] != "PENDING":
                raise ValueError("top-up is not pending")
            await connection.execute(
                "UPDATE payments SET provider_reference=$2 WHERE id=$1", payment_id, provider_reference,
            )
    except asyncpg.UniqueViolationError as exc:
        raise IdempotencyConflict("provider reference is already attached") from exc


async def accept_verified_webhook(
    connection: asyncpg.Connection, adapter: PaymentProviderAdapter,
    raw_body: bytes, headers: Mapping[str, str],
) -> Balance:
    """Provider-specific signature verification occurs before any database or ledger mutation."""
    event = adapter.verify_paid_event(raw_body, headers)
    if not isinstance(event, VerifiedTopup):
        raise PaymentMismatch("unverified payment event")
    return await apply_verified_topup(connection, event)


async def apply_verified_topup(
    connection: asyncpg.Connection, event: VerifiedTopup,
) -> Balance:
    """Atomic paid receipt + single wallet credit, including duplicate/out-of-order events."""
    if (not PROVIDER.fullmatch(event.provider) or not _valid_text(event.event_id)
            or not _valid_text(event.provider_reference) or event.currency != "SAR"
            or not isinstance(event.payment_id, UUID)
            or type(event.amount_halalas) is not int or event.amount_halalas <= 0):
        raise PaymentMismatch("invalid verified event")
    async with connection.transaction():
        payment = await connection.fetchrow(
            """SELECT user_id,provider,provider_reference,amount_halalas,currency,status,payment_type
               FROM payments WHERE id=$1 FOR UPDATE""", event.payment_id,
        )
        if not payment or (payment["provider"], payment["provider_reference"],
                           payment["amount_halalas"], payment["currency"], payment["payment_type"]) != (
            event.provider, event.provider_reference, event.amount_halalas, event.currency,
            "WALLET_TOPUP",
        ) or payment["status"] == "FAILED":
            raise PaymentMismatch("paid event does not match a pending top-up")
        inserted = await connection.fetchval(
            """INSERT INTO payment_events
               (provider,event_id,payment_id,provider_reference,amount_halalas,currency,event_type)
               VALUES ($1,$2,$3,$4,$5,$6,'TOPUP_PAID')
               ON CONFLICT (provider,event_id) DO NOTHING RETURNING 1""",
            event.provider, event.event_id, event.payment_id,
            event.provider_reference, event.amount_halalas, event.currency,
        )
        if not inserted:
            prior = await connection.fetchrow(
                """SELECT payment_id,provider_reference,amount_halalas,currency
                   FROM payment_events WHERE provider=$1 AND event_id=$2""",
                event.provider, event.event_id,
            )
            if (prior["payment_id"], prior["provider_reference"],
                    prior["amount_halalas"], prior["currency"]) != (
                event.payment_id, event.provider_reference, event.amount_halalas, event.currency,
            ):
                raise PaymentMismatch("provider event id reused with different data")
        if payment["status"] == "PAID":
            credited = await connection.fetchval(
                """SELECT 1 FROM wallet_transactions WHERE wallet_user_id=$1
                   AND idempotency_key=$2 AND transaction_type='TOP_UP' AND amount_halalas=$3""",
                payment["user_id"], f"payment:{event.payment_id}", event.amount_halalas,
            )
            if not credited:
                raise PaymentMismatch("paid top-up missing matching ledger entry")
            return await balance(connection, payment["user_id"])
        updated_balance = await credit(
            connection, payment["user_id"], event.amount_halalas,
            f"payment:{event.payment_id}", kind="TOP_UP",
        )
        await connection.execute(
            "UPDATE payments SET status='PAID',paid_at=now() WHERE id=$1", event.payment_id,
        )
        return updated_balance
