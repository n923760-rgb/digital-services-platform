"""Ordered service inputs and durable job results."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0005_order_inputs"
down_revision = "0004_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_files",
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), primary_key=True),
        sa.Column("position", sa.Integer(), primary_key=True),
        sa.Column("file_id", UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=False),
        sa.UniqueConstraint("order_id", "file_id", name="order_file_once"),
        sa.CheckConstraint("position >= 0", name="order_file_position_valid"),
    )
    op.add_column("jobs", sa.Column("result_file_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("job_result_file_fk", "jobs", "files", ["result_file_id"], ["id"])
    op.add_column("orders", sa.Column("delivery_receipt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "delivery_receipt")
    op.drop_constraint("job_result_file_fk", "jobs", type_="foreignkey")
    op.drop_column("jobs", "result_file_id")
    op.drop_table("order_files")
