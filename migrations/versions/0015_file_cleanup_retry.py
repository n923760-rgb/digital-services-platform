"""Rotate failed object deletions without changing file retention or batch bounds."""

import sqlalchemy as sa
from alembic import op

revision = "0015_file_cleanup_retry"
down_revision = "0014_review_queue_cursor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("files", sa.Column("cleanup_attempted_at", sa.DateTime(timezone=True)))
    op.create_index(
        "files_cleanup_queue_idx", "files",
        [sa.text("COALESCE(cleanup_attempted_at, retention_until)"), "id"],
        postgresql_where=sa.text("status <> 'EXPIRED'"),
    )


def downgrade() -> None:
    op.drop_index("files_cleanup_queue_idx", table_name="files")
    op.drop_column("files", "cleanup_attempted_at")
