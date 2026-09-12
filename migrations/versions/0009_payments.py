"""Provider-independent wallet top-up intents and immutable verified event receipts."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0009_payments"
down_revision = "0008_admin_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("payment_type", sa.Text(), nullable=False),
        sa.Column("amount_halalas", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SAR"),
        sa.Column("status", sa.Text(), nullable=False, server_default="PENDING"),
        sa.Column("client_request_key", sa.Text(), nullable=False),
        sa.Column("provider_reference", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "client_request_key", name="payments_user_request_unique"),
        sa.UniqueConstraint("provider", "provider_reference", name="payments_provider_reference_unique"),
        sa.CheckConstraint("amount_halalas > 0", name="payments_positive_amount"),
        sa.CheckConstraint("currency = 'SAR'", name="payments_sar_only"),
        sa.CheckConstraint("payment_type = 'WALLET_TOPUP'", name="payments_type_supported"),
        sa.CheckConstraint("status IN ('PENDING','PAID','FAILED')", name="payments_status_valid"),
        sa.CheckConstraint("order_id IS NULL", name="payments_topup_no_order"),
    )
    op.create_table(
        "payment_events",
        sa.Column("provider", sa.Text(), primary_key=True),
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column("payment_id", UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("provider_reference", sa.Text(), nullable=False),
        sa.Column("amount_halalas", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount_halalas > 0", name="payment_event_positive_amount"),
        sa.CheckConstraint("currency = 'SAR'", name="payment_event_sar_only"),
        sa.CheckConstraint("event_type = 'TOPUP_PAID'", name="payment_event_type_valid"),
    )
    op.execute("""CREATE FUNCTION reject_payment_event_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
               BEGIN RAISE EXCEPTION 'payment events are immutable'; END; $$;""")
    op.execute("""CREATE TRIGGER payment_events_immutable BEFORE UPDATE OR DELETE ON payment_events
               FOR EACH ROW EXECUTE FUNCTION reject_payment_event_mutation();""")


def downgrade() -> None:
    op.execute("DROP TRIGGER payment_events_immutable ON payment_events")
    op.execute("DROP FUNCTION reject_payment_event_mutation()")
    op.drop_table("payment_events")
    op.drop_table("payments")
