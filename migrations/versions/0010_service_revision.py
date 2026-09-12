"""Optimistic revision for audited service registry edits."""

import sqlalchemy as sa
from alembic import op

revision = "0010_service_revision"
down_revision = "0009_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("services", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.create_check_constraint("services_revision_positive", "services", "revision > 0")


def downgrade() -> None:
    op.drop_constraint("services_revision_positive", "services", type_="check")
    op.drop_column("services", "revision")
