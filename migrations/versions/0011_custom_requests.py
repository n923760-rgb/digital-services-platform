"""Persist one active custom-request draft per user/channel with deduplicated input."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0011_custom_requests"
down_revision = "0010_service_revision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_service_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="COLLECTING"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_message_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('COLLECTING','NEW','CANCELLED')",
                           name="custom_request_status_valid"),
        sa.CheckConstraint("description IS NULL OR char_length(description) BETWEEN 10 AND 2000",
                           name="custom_request_description_length"),
        sa.CheckConstraint("char_length(channel) BETWEEN 1 AND 40", name="custom_request_channel_length"),
        sa.CheckConstraint("source_message_key IS NULL OR char_length(source_message_key) BETWEEN 1 AND 160",
                           name="custom_request_source_key_length"),
        sa.CheckConstraint("status != 'NEW' OR (description IS NOT NULL AND source_message_key IS NOT NULL)",
                           name="custom_request_new_has_description"),
        sa.UniqueConstraint("user_id", "channel", "source_message_key",
                            name="custom_request_message_once"),
    )
    op.create_index("custom_request_one_draft", "custom_service_requests", ["user_id", "channel"],
                    unique=True, postgresql_where=sa.text("status='COLLECTING'"))
    op.create_index("custom_request_review_queue", "custom_service_requests", ["created_at"],
                    postgresql_where=sa.text("status='NEW'"))


def downgrade() -> None:
    op.drop_index("custom_request_review_queue", table_name="custom_service_requests")
    op.drop_index("custom_request_one_draft", table_name="custom_service_requests")
    op.drop_table("custom_service_requests")
