"""Give the authenticated review queue a complete keyset ordering index."""

import sqlalchemy as sa
from alembic import op

revision = "0014_review_queue_cursor"
down_revision = "0013_telegram_quote_revision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("custom_request_review_queue", table_name="custom_service_requests")
    op.create_index(
        "custom_request_review_queue", "custom_service_requests", ["updated_at", "id"],
        postgresql_where=sa.text("status IN ('NEW','IN_REVIEW')"),
    )


def downgrade() -> None:
    op.drop_index("custom_request_review_queue", table_name="custom_service_requests")
    op.create_index(
        "custom_request_review_queue", "custom_service_requests", ["updated_at"],
        postgresql_where=sa.text("status IN ('NEW','IN_REVIEW')"),
    )
