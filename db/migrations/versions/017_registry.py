"""Sổ đăng ký danh mục 877: nguồn danh mục + quy trình, năng lực, chuẩn mẫu và dải đo.

Thiết kế: docs/KIEN_TRUC_DANH_MUC_877.md mục 5.2. Mỗi lần nạp một file danh mục là một dòng
``catalog_source`` (bản nháp, chờ duyệt); các dòng dữ liệu xoá theo nguồn. Khoá của quy trình là
``code_key`` (tiền tố + số + năm), KHÔNG phải số: danh mục có các cặp trùng số khác năm là hai quy trình
khác nhau. Bảng ``procedure`` (tài liệu QTKĐ đang có trong kho) giữ nguyên: nó ghi phiên bản hiện hành
của từng tài liệu, còn sổ đăng ký ghi danh mục được công nhận; liên kết giữa hai bên tính theo mã lúc đọc.

Tên ``capability`` đã dùng ở migration 011 và bị xoá ở 014; bảng mới có cấu trúc khác.

Revision ID: 017_registry
Revises: 016_document_summary
"""

import sqlalchemy as sa
from alembic import op

revision = "017_registry"
down_revision = "016_document_summary"
branch_labels = None
depends_on = None

_SI = sa.Numeric(38, 12)


def _source_fk() -> sa.Column:
    return sa.Column(
        "source_id", sa.Integer, sa.ForeignKey("catalog_source.id", ondelete="CASCADE"), nullable=False
    )


def _range_columns(owner: str, owner_table: str) -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(owner, sa.Integer, sa.ForeignKey(f"{owner_table}.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ord", sa.Integer, nullable=False, server_default="0"),
        sa.Column("label", sa.Text, nullable=True),
        sa.Column("quantity", sa.String(32), nullable=False),
        sa.Column("min_si", _SI, nullable=True),
        sa.Column("max_si", _SI, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "catalog_source",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("file_name", sa.String(512), nullable=False),
        sa.Column("stored_path", sa.String(1024), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("row_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("issues", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
        sa.Column("uploaded_by", sa.Integer, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime, nullable=True),
        sa.Column("review_note", sa.Text, nullable=True),
    )
    op.create_index("ix_catalog_source_kind", "catalog_source", ["kind"])
    op.create_index("ix_catalog_source_sha256", "catalog_source", ["sha256"])
    op.create_index("ix_catalog_source_status", "catalog_source", ["status"])

    op.create_table(
        "catalog_procedure",
        sa.Column("id", sa.Integer, primary_key=True),
        _source_fk(),
        sa.Column("row", sa.Integer, nullable=False),
        sa.Column("code_raw", sa.Text, nullable=False),
        sa.Column("code_key", sa.String(64), nullable=True),
        sa.Column("prefix", sa.String(16), nullable=True),
        sa.Column("number", sa.String(32), nullable=True),
        sa.Column("year", sa.Integer, nullable=True),
        sa.Column("title", sa.Text, nullable=False, server_default=""),
        sa.Column("issuer", sa.Text, nullable=True),
        sa.Column("field", sa.Text, nullable=True),
        sa.Column("kind", sa.String(16), nullable=False, server_default="kiem_dinh"),
    )
    op.create_index("ix_catalog_procedure_source_id", "catalog_procedure", ["source_id"])
    op.create_index("ix_catalog_procedure_code_key", "catalog_procedure", ["code_key"])

    op.create_table(
        "capability",
        sa.Column("id", sa.Integer, primary_key=True),
        _source_fk(),
        sa.Column("row", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("field", sa.Text, nullable=True),
        sa.Column("params_raw", sa.Text, nullable=True),
        sa.Column("procedures_raw", sa.Text, nullable=True),
    )
    op.create_index("ix_capability_source_id", "capability", ["source_id"])

    op.create_table("capability_range", *_range_columns("capability_id", "capability"))
    op.create_index("ix_capability_range_capability_id", "capability_range", ["capability_id"])

    op.create_table(
        "capability_procedure",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "capability_id", sa.Integer, sa.ForeignKey("capability.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("ord", sa.Integer, nullable=False, server_default="0"),
        sa.Column("code_raw", sa.Text, nullable=False),
        sa.Column("code_key", sa.String(64), nullable=False),
    )
    op.create_index("ix_capability_procedure_capability_id", "capability_procedure", ["capability_id"])
    op.create_index("ix_capability_procedure_code_key", "capability_procedure", ["code_key"])

    op.create_table(
        "reference_standard",
        sa.Column("id", sa.Integer, primary_key=True),
        _source_fk(),
        sa.Column("row", sa.Integer, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("serial", sa.String(255), nullable=True),
        sa.Column("characteristics_raw", sa.Text, nullable=True),
        sa.Column("interval_raw", sa.String(128), nullable=True),
        sa.Column("interval_months", sa.Integer, nullable=True),
        sa.Column("field", sa.Text, nullable=True),
    )
    op.create_index("ix_reference_standard_source_id", "reference_standard", ["source_id"])

    op.create_table("standard_range", *_range_columns("standard_id", "reference_standard"))
    op.create_index("ix_standard_range_standard_id", "standard_range", ["standard_id"])


def downgrade() -> None:
    op.drop_index("ix_standard_range_standard_id", table_name="standard_range")
    op.drop_table("standard_range")
    op.drop_index("ix_reference_standard_source_id", table_name="reference_standard")
    op.drop_table("reference_standard")
    op.drop_index("ix_capability_procedure_code_key", table_name="capability_procedure")
    op.drop_index("ix_capability_procedure_capability_id", table_name="capability_procedure")
    op.drop_table("capability_procedure")
    op.drop_index("ix_capability_range_capability_id", table_name="capability_range")
    op.drop_table("capability_range")
    op.drop_index("ix_capability_source_id", table_name="capability")
    op.drop_table("capability")
    op.drop_index("ix_catalog_procedure_code_key", table_name="catalog_procedure")
    op.drop_index("ix_catalog_procedure_source_id", table_name="catalog_procedure")
    op.drop_table("catalog_procedure")
    op.drop_index("ix_catalog_source_status", table_name="catalog_source")
    op.drop_index("ix_catalog_source_sha256", table_name="catalog_source")
    op.drop_index("ix_catalog_source_kind", table_name="catalog_source")
    op.drop_table("catalog_source")
