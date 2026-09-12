"""File lifecycle and configurable retention metadata."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0004_files"
down_revision = "0003_job_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=False, unique=True),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("size_bytes > 0", name="file_size_positive"),
        sa.CheckConstraint("file_type IN ('INPUT','OUTPUT')", name="file_type_valid"),
        sa.CheckConstraint("status IN ('UPLOADING','READY','FAILED','EXPIRED')", name="file_status_valid"),
    )
    op.create_index("files_retention_idx", "files", ["retention_until"])


def downgrade() -> None:
    op.drop_table("files")
