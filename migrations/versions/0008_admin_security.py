"""Server-enforced admin roles, sessions and append-only audit events."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0008_admin_security"
down_revision = "0007_telegram_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.CheckConstraint("code IN ('OWNER','OPERATOR')", name="role_code_valid"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_code", sa.Text(), sa.ForeignKey("roles.code"), primary_key=True),
        sa.Column("permission", sa.Text(), primary_key=True),
    )
    op.create_table(
        "admins",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.Text(), unique=True, nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role_code", sa.Text(), sa.ForeignKey("roles.code"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("username = lower(username)", name="admin_username_lowercase"),
    )
    op.create_table(
        "admin_sessions",
        sa.Column("token_hash", sa.LargeBinary(), primary_key=True),
        sa.Column("admin_id", UUID(as_uuid=True), sa.ForeignKey("admins.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("admin_sessions_expiration_idx", "admin_sessions", ["expires_at"])
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_admin_id", UUID(as_uuid=True), sa.ForeignKey("admins.id"), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute("INSERT INTO roles (code) VALUES ('OWNER'),('OPERATOR')")
    op.execute("""INSERT INTO role_permissions (role_code,permission) VALUES
               ('OWNER','admin:view'),('OWNER','admin:audit'),('OWNER','admin:manage'),
               ('OPERATOR','admin:view')""")
    op.execute("""CREATE FUNCTION reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
               BEGIN RAISE EXCEPTION 'audit entries are immutable'; END; $$;""")
    op.execute("""CREATE TRIGGER audit_logs_immutable BEFORE UPDATE OR DELETE ON audit_logs
               FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation();""")


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_logs_immutable ON audit_logs")
    op.execute("DROP FUNCTION reject_audit_mutation()")
    op.drop_table("audit_logs")
    op.drop_table("admin_sessions")
    op.drop_table("admins")
    op.drop_table("role_permissions")
    op.drop_table("roles")
