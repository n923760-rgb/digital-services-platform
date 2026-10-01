"""Native Stars invoices/charge history remain separate from the SAR wallet."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "0016_telegram_stars"
down_revision = "0015_file_cleanup_retry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("services", sa.Column("base_price_stars", sa.Integer(), nullable=True))
    op.create_check_constraint("service_stars_price_valid", "services",
                               "base_price_stars BETWEEN 1 AND 100000")
    op.add_column("telegram_workflows", sa.Column("quoted_price_stars", sa.Integer()))
    op.add_column("telegram_workflows", sa.Column("quoted_terms_digest", sa.Text()))
    op.add_column("orders", sa.Column("price_snapshot_stars", sa.Integer()))
    op.drop_constraint("order_sar_only", "orders", type_="check")
    op.create_check_constraint(
        "order_currency_amount_valid", "orders",
        "(currency='SAR' AND price_snapshot_stars IS NULL) OR "
        "(currency='XTR' AND price_snapshot_halalas=0 AND price_snapshot_stars IS NOT NULL AND price_snapshot_stars BETWEEN 1 AND 100000)",
    )
    op.create_table(
        "star_invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workflow_id", UUID(as_uuid=True),
                  sa.ForeignKey("telegram_workflows.id"), nullable=False),
        sa.Column("quote_revision", sa.Integer(), nullable=False),
        sa.Column("service_id", UUID(as_uuid=True), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("amount_stars", sa.Integer(), nullable=False),
        sa.Column("file_ids", ARRAY(UUID(as_uuid=True)), nullable=False),
        sa.Column("terms_digest", sa.Text(), nullable=False),
        sa.Column("terms_text", sa.Text(), nullable=False),
        sa.Column("checkout_query_id", sa.Text(), unique=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workflow_id", "quote_revision", name="star_invoice_offer_unique"),
        sa.CheckConstraint("amount_stars BETWEEN 1 AND 100000", name="star_invoice_amount_valid"),
    )
    op.create_table(
        "star_charges",
        sa.Column("charge_id", sa.Text(), primary_key=True),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("star_invoices.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), unique=True),
        sa.Column("refund_attempted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('PAID','DELIVERED','REFUND_PENDING','REFUNDED')",
                           name="star_charge_status_valid"),
    )
    op.create_index("star_refund_queue_idx", "star_charges",
                    [sa.text("COALESCE(refund_attempted_at, created_at)"), "charge_id"],
                    postgresql_where=sa.text("status='REFUND_PENDING'"))
    op.create_table(
        "star_payment_events",
        sa.Column("charge_id", sa.Text(), sa.ForeignKey("star_charges.charge_id"), primary_key=True),
        sa.Column("event_type", sa.Text(), primary_key=True),
        sa.Column("receipt", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("event_type IN ('PAID','DELIVERED','REFUND_REQUESTED','REFUNDED')",
                           name="star_event_type_valid"),
    )
    op.execute("""CREATE TRIGGER star_events_immutable BEFORE UPDATE OR DELETE ON star_payment_events
               FOR EACH ROW EXECUTE FUNCTION reject_payment_event_mutation();""")
    op.create_table(
        "telegram_payment_inbox",
        sa.Column("bot_id", sa.BigInteger(), primary_key=True),
        sa.Column("update_id", sa.BigInteger(), primary_key=True),
        sa.Column("event", JSONB(), nullable=False),
        sa.Column("status", sa.Text(), server_default="PENDING", nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('PENDING','DONE','REJECTED')", name="star_inbox_status_valid"),
    )

    op.execute("""CREATE FUNCTION protect_star_invoice_snapshot() RETURNS trigger
               LANGUAGE plpgsql AS $
               BEGIN
                 IF ROW(NEW.user_id,NEW.workflow_id,NEW.quote_revision,NEW.service_id,
                        NEW.amount_stars,NEW.file_ids,NEW.terms_digest,NEW.terms_text,NEW.created_at)
                    IS DISTINCT FROM
                    ROW(OLD.user_id,OLD.workflow_id,OLD.quote_revision,OLD.service_id,
                        OLD.amount_stars,OLD.file_ids,OLD.terms_digest,OLD.terms_text,OLD.created_at)
                    OR (OLD.order_id IS NOT NULL AND NEW.order_id IS DISTINCT FROM OLD.order_id)
                    OR (OLD.checkout_query_id IS NOT NULL
                        AND NEW.checkout_query_id IS DISTINCT FROM OLD.checkout_query_id) THEN
                   RAISE EXCEPTION 'Stars invoice snapshot is immutable';
                 END IF;
                 RETURN NEW;
               END; $;""")
    op.execute("""CREATE TRIGGER star_invoice_snapshot BEFORE UPDATE ON star_invoices
               FOR EACH ROW EXECUTE FUNCTION protect_star_invoice_snapshot();""")
    op.create_index(
        "star_inbox_queue_idx", "telegram_payment_inbox",
        ["bot_id", sa.text("COALESCE(attempted_at, created_at)"), "update_id"],
        postgresql_where=sa.text("status='PENDING'"),
    )


def downgrade() -> None:
    # Financial history must survive rollback; revert the application with the schema intact.
    raise RuntimeError("Stars downgrade is disabled to preserve charge and receipt history")
