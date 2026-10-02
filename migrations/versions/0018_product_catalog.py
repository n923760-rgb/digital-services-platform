"""Bind product identities to known executors and support DB-only admin login limits."""

import sqlalchemy as sa
from alembic import op

revision = "0018_product_catalog"
down_revision = "0017_direct_text_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("services", sa.Column("processor_key", sa.Text(), nullable=True))
    op.create_check_constraint(
        "service_processor_key_valid", "services",
        "processor_key IS NULL OR processor_key IN ('summarize-text','merge-pdf')",
    )
    op.execute("UPDATE services SET processor_key=slug WHERE slug IN ('summarize-text','merge-pdf')")
    op.create_table(
        "admin_login_counters",
        sa.Column("login_key", sa.Text(), primary_key=True),
        sa.Column("attempts", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempts>0", name="admin_login_attempts_positive"),
    )
    op.create_index("admin_login_counters_expiry_idx", "admin_login_counters", ["expires_at"])


def downgrade() -> None:
    raise RuntimeError("Keep executor bindings and financial history; roll back application code only")
