"""Bảng ``document_summary``: tóm tắt tài liệu do LLM viết lúc nạp, chờ người duyệt.

Mỗi tài liệu có tối đa một bản tóm tắt. Trạng thái lưu dạng chuỗi
(generating/draft/approved/rejected/error) để thêm trạng thái sau này không phải
đổi kiểu enum của PostgreSQL. Xoá tài liệu thì xoá luôn bản tóm tắt.

Revision ID: 016_document_summary
Revises: 015_document_superseded
"""

import sqlalchemy as sa
from alembic import op

revision = "016_document_summary"
down_revision = "015_document_superseded"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_summary",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "document_id",
            sa.String(128),
            sa.ForeignKey("document.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="generating"),
        sa.Column("text", sa.Text, nullable=True),
        sa.Column("generated_text", sa.Text, nullable=True),
        sa.Column("warnings", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("source_sha256", sa.String(64), nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
        sa.Column("generated_at", sa.DateTime, nullable=True),
        sa.Column("edited_by", sa.Integer, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("edited_at", sa.DateTime, nullable=True),
        sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime, nullable=True),
        sa.Column("review_note", sa.Text, nullable=True),
    )
    # Một chỉ mục unique (khớp model ``unique=True, index=True``), không thêm ràng buộc unique riêng.
    op.create_index("ix_document_summary_document_id", "document_summary", ["document_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_document_summary_document_id", table_name="document_summary")
    op.drop_table("document_summary")
