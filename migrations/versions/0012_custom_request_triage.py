"""Add audited, optimistic admin triage for custom service requests."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0012_custom_request_triage"
down_revision = "0011_custom_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("custom_request_status_valid", "custom_service_requests", type_="check")
    op.drop_index("custom_request_review_queue", table_name="custom_service_requests")
    op.add_column(
        "custom_service_requests",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "custom_service_requests",
        sa.Column("reviewed_by_admin_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column("custom_service_requests", sa.Column("decision_reason", sa.Text(), nullable=True))
    op.add_column(
        "custom_service_requests",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "custom_request_reviewer_fk",
        "custom_service_requests",
        "admins",
        ["reviewed_by_admin_id"],
        ["id"],
    )
    op.create_check_constraint(
        "custom_request_status_valid",
        "custom_service_requests",
        "status IN ('COLLECTING','NEW','IN_REVIEW','DECLINED','CANCELLED')",
    )
    op.create_check_constraint(
        "custom_request_revision_positive", "custom_service_requests", "revision >= 1",
    )
    op.create_check_constraint(
        "custom_request_review_fields_valid",
        "custom_service_requests",
        "(status NOT IN ('IN_REVIEW','DECLINED') OR "
        "(reviewed_by_admin_id IS NOT NULL AND reviewed_at IS NOT NULL)) AND "
        "(status != 'DECLINED' OR "
        "char_length(decision_reason) BETWEEN 10 AND 500)",
    )
    op.create_index(
        "custom_request_review_queue",
        "custom_service_requests",
        ["updated_at"],
        postgresql_where=sa.text("status IN ('NEW','IN_REVIEW')"),
    )


def downgrade() -> None:
    op.drop_index("custom_request_review_queue", table_name="custom_service_requests")
    op.drop_constraint(
        "custom_request_review_fields_valid", "custom_service_requests", type_="check",
    )
    op.drop_constraint(
        "custom_request_revision_positive", "custom_service_requests", type_="check",
    )
    op.drop_constraint("custom_request_status_valid", "custom_service_requests", type_="check")
    op.execute(
        "UPDATE custom_service_requests SET status='NEW' WHERE status='IN_REVIEW'"
    )
    op.execute(
        "UPDATE custom_service_requests SET status='CANCELLED' WHERE status='DECLINED'"
    )
    op.create_check_constraint(
        "custom_request_status_valid",
        "custom_service_requests",
        "status IN ('COLLECTING','NEW','CANCELLED')",
    )
    op.drop_constraint("custom_request_reviewer_fk", "custom_service_requests", type_="foreignkey")
    op.drop_column("custom_service_requests", "reviewed_at")
    op.drop_column("custom_service_requests", "decision_reason")
    op.drop_column("custom_service_requests", "reviewed_by_admin_id")
    op.drop_column("custom_service_requests", "revision")
    op.create_index(
        "custom_request_review_queue",
        "custom_service_requests",
        ["created_at"],
        postgresql_where=sa.text("status='NEW'"),
    )
