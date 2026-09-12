"""Durable, retryable delivery attempts independent of processing jobs."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0006_delivery_outbox"
down_revision = "0005_order_inputs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_outbox",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), unique=True, nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("external_receipt", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("channel = 'telegram'", name="delivery_channel_supported"),
        sa.CheckConstraint("status IN ('PENDING','SENDING','SENT','FAILED')", name="delivery_status_valid"),
        sa.CheckConstraint("attempt_count >= 0 AND max_attempts > 0", name="delivery_attempts_valid"),
    )
    op.create_index("delivery_pending_idx", "delivery_outbox", ["status", "created_at"])


def downgrade() -> None:
    op.drop_table("delivery_outbox")
