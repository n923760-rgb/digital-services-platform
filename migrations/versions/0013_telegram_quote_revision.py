"""Bind Telegram confirmation buttons to a specific persisted offer revision."""

import sqlalchemy as sa
from alembic import op

revision = "0013_telegram_quote_revision"
down_revision = "0012_custom_request_triage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "telegram_workflows",
        sa.Column("quote_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "telegram_quote_revision_nonnegative", "telegram_workflows", "quote_revision >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "telegram_quote_revision_nonnegative", "telegram_workflows", type_="check",
    )
    op.drop_column("telegram_workflows", "quote_revision")
