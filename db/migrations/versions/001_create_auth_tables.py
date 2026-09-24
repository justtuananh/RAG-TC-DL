"""Sprint 0+1: Create app_user and audit_log tables

Revision ID: 001_create_auth_tables
Revises: None
Create Date: 2026-09-22 21:06:27.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001_create_auth_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ENUM type for user roles
    user_role_enum = sa.Enum("viewer", "technician", "approver", "admin", name="user_role")

    # Create app_user table
    op.create_table(
        "app_user",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role_enum, default="viewer", nullable=False),
        sa.Column("is_active", sa.Integer, default=1, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_app_user_username", "app_user", ["username"])

    # Create audit_log table
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column("before", sa.JSON, nullable=True),
        sa.Column("after", sa.JSON, nullable=True),
        sa.Column("at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_at", "audit_log", ["at"])
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])


def downgrade() -> None:
    # Drop audit_log table
    op.drop_index("ix_audit_log_at", table_name="audit_log")
    op.drop_index("ix_audit_log_actor_id", table_name="audit_log")
    op.drop_table("audit_log")

    # Drop app_user table
    op.drop_index("ix_app_user_username", table_name="app_user")
    op.drop_table("app_user")

    # Drop ENUM type
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
