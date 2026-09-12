"""Users, service registry, immutable wallet ledger, orders and jobs."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0002_core_ledger"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), unique=True, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "service_categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("name_ar", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "services",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("category_id", UUID(as_uuid=True), sa.ForeignKey("service_categories.id"), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("name_ar", sa.Text(), nullable=False),
        sa.Column("description_ar", sa.Text(), nullable=False, server_default=""),
        sa.Column("processor_type", sa.Text(), nullable=False),
        sa.Column("base_price_halalas", sa.BigInteger(), nullable=False),
        sa.Column("input_schema", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("processor_type IN ('ai','tool','template','manual','hybrid')", name="service_processor_valid"),
        sa.CheckConstraint("base_price_halalas >= 0", name="service_price_nonnegative"),
    )
    op.create_table(
        "wallets",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SAR"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("currency = 'SAR'", name="wallet_sar_only"),
    )
    op.create_table(
        "orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("service_id", UUID(as_uuid=True), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("client_request_key", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("price_snapshot_halalas", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SAR"),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "client_request_key", name="order_user_request_unique"),
        sa.CheckConstraint("price_snapshot_halalas >= 0", name="order_price_nonnegative"),
        sa.CheckConstraint("currency = 'SAR'", name="order_sar_only"),
        sa.CheckConstraint("status IN ('DRAFT','AWAITING_PAYMENT','RESERVED','QUEUED','PROCESSING','COMPLETED','WAITING_CUSTOMER','AWAITING_FULFILLMENT','FULFILLING','FAILED','CANCELLED','REFUNDED')", name="order_status_valid"),
    )
    op.create_table(
        "wallet_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("wallet_user_id", UUID(as_uuid=True), sa.ForeignKey("wallets.user_id"), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("transaction_type", sa.Text(), nullable=False),
        sa.Column("amount_halalas", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("wallet_user_id", "idempotency_key", name="wallet_idempotency_unique"),
        sa.CheckConstraint("transaction_type IN ('TOP_UP','BONUS','RESERVE','CAPTURE','RELEASE','REFUND','ADMIN_ADJUSTMENT')", name="wallet_transaction_type_valid"),
        sa.CheckConstraint("(transaction_type = 'ADMIN_ADJUSTMENT' AND amount_halalas <> 0 AND nullif(trim(reason), '') IS NOT NULL) OR (transaction_type <> 'ADMIN_ADJUSTMENT' AND amount_halalas > 0)", name="wallet_amount_and_reason_valid"),
        sa.CheckConstraint("(transaction_type IN ('RESERVE','CAPTURE','RELEASE','REFUND')) = (order_id IS NOT NULL)", name="wallet_order_reference_valid"),
    )
    op.create_index("wallet_transactions_order_idx", "wallet_transactions", ["order_id"])
    op.create_index("wallet_one_reserve_per_order", "wallet_transactions", ["order_id"], unique=True,
                    postgresql_where=sa.text("transaction_type = 'RESERVE'"))
    op.create_index("wallet_one_settlement_per_order", "wallet_transactions", ["order_id"], unique=True,
                    postgresql_where=sa.text("transaction_type IN ('CAPTURE', 'RELEASE')"))
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('PENDING','QUEUED','PROCESSING','COMPLETED','FAILED')", name="job_status_valid"),
        sa.CheckConstraint("attempt_count >= 0 AND max_attempts > 0", name="job_attempts_valid"),
    )
    op.create_index("jobs_order_idx", "jobs", ["order_id"])
    op.execute("""
        CREATE FUNCTION reject_wallet_transaction_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'wallet ledger entries are immutable'; END; $$;
    """)
    op.execute("""
        CREATE TRIGGER wallet_transactions_immutable BEFORE UPDATE OR DELETE ON wallet_transactions
        FOR EACH ROW EXECUTE FUNCTION reject_wallet_transaction_mutation();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER wallet_transactions_immutable ON wallet_transactions")
    op.execute("DROP FUNCTION reject_wallet_transaction_mutation()")
    op.drop_table("jobs")
    op.drop_table("wallet_transactions")
    op.drop_table("orders")
    op.drop_table("wallets")
    op.drop_table("services")
    op.drop_table("service_categories")
    op.drop_table("users")
