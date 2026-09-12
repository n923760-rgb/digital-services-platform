"""Track every execution attempt independently of orders and jobs."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0003_job_attempts"
down_revision = "0002_core_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_attempts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("job_id", "attempt_number", name="job_attempt_number_unique"),
        sa.CheckConstraint("attempt_number > 0", name="job_attempt_number_positive"),
        sa.CheckConstraint("status IN ('PROCESSING','FAILED','COMPLETED')", name="job_attempt_status_valid"),
    )


def downgrade() -> None:
    op.drop_table("job_attempts")
