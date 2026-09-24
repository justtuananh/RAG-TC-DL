"""Create the document ledger table.

Revision ID: 002_create_document
Revises: 001_create_auth_tables
"""
from alembic import op
import sqlalchemy as sa

revision = "002_create_document"
down_revision = "001_create_auth_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    doc_type = sa.Enum(
        "qtkd", "ho_so_kiem_dinh", "phieu_do", "danh_muc", "khac",
        name="document_type",
    )
    ingest_status = sa.Enum(
        "pending", "processing", "ready", "error",
        name="ingest_status",
    )
    op.create_table(
        "document",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("file_stem", sa.String(255), unique=True, nullable=False),
        sa.Column("display_name", sa.String(512), nullable=False),
        sa.Column("ext", sa.String(16), nullable=False),
        sa.Column("doc_type", doc_type, nullable=False, server_default="khac"),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("uploaded_by", sa.Integer, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("ingest_status", ingest_status, nullable=False, server_default="pending"),
        sa.Column("ingest_error", sa.Text, nullable=True),
    )
    op.create_index("ix_document_file_stem", "document", ["file_stem"], unique=True)
    op.create_index("ix_document_sha256", "document", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_document_sha256", table_name="document")
    op.drop_index("ix_document_file_stem", table_name="document")
    op.drop_table("document")
    sa.Enum(name="ingest_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="document_type").drop(op.get_bind(), checkfirst=True)
