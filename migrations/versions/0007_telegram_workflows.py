"""Persistent customer workflows and idempotent Telegram file attachments."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0007_telegram_workflows"
down_revision = "0006_delivery_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_workflows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("service_id", UUID(as_uuid=True), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("quoted_price_halalas", sa.BigInteger(), nullable=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('COLLECTING','CONFIRMING','SUBMITTED','CANCELLED')",
            name="telegram_workflow_status_valid",
        ),
        sa.CheckConstraint("quoted_price_halalas >= 0", name="telegram_quote_nonnegative"),
    )
    op.create_index(
        "telegram_one_active_workflow_per_user", "telegram_workflows", ["user_id"],
        unique=True, postgresql_where=sa.text("status IN ('COLLECTING','CONFIRMING')"),
    )
    op.create_table(
        "telegram_workflow_files",
        sa.Column("workflow_id", UUID(as_uuid=True), sa.ForeignKey("telegram_workflows.id"), primary_key=True),
        sa.Column("position", sa.Integer(), primary_key=True),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("file_id", UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=False),
        sa.UniqueConstraint("workflow_id", "telegram_message_id", name="telegram_upload_once"),
        sa.UniqueConstraint("workflow_id", "file_id", name="telegram_workflow_file_once"),
        sa.CheckConstraint("position >= 0", name="telegram_file_position_valid"),
    )


def downgrade() -> None:
    op.drop_table("telegram_workflow_files")
    op.drop_table("telegram_workflows")
