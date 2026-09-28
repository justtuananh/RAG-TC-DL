"""Pha D1: bốn bảng danh mục hồ sơ NAS + view đã duyệt (P3).

Mỗi dòng danh mục (chuẩn mẫu, kiểm định viên, danh mục quy trình, lĩnh vực công
nhận) gắn một ``extraction`` giữ xuất xứ nguyên văn (P1) và trạng thái duyệt (P3).
Danh sách lưu JSON; ``search_text`` là bản không dấu phục vụ tìm kiếm; hạn KĐ/HC
kế tiếp của chuẩn mẫu là giá trị dẫn xuất kèm cờ ``next_due_derived``.

Bốn view ``v_lab_standard``/``v_inspector``/``v_procedure_catalog``/``v_capability``
chỉ lộ dòng đã duyệt, kèm tên tài liệu; nguồn sự thật chung ở ``db/views.py``.

Revision ID: 011_nas_catalogs
Revises: 010_measurement_error_unit
"""

import sqlalchemy as sa
from alembic import op

from db.views import create_catalog_views, drop_catalog_views

revision = "011_nas_catalogs"
down_revision = "010_measurement_error_unit"
branch_labels = None
depends_on = None


def _catalog_columns() -> list[sa.Column]:
    """Cột chung của mọi bảng danh mục: xuất xứ + thứ tự + nguyên văn + tìm kiếm."""
    return [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.String(128), sa.ForeignKey("document.id"), nullable=False),
        sa.Column("extraction_id", sa.Integer, sa.ForeignKey("extraction.id"), nullable=False),
        sa.Column("ord", sa.Integer, nullable=True),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("search_text", sa.Text, nullable=True),
    ]


def _create_lab_standard() -> None:
    op.create_table(
        "lab_standard",
        *_catalog_columns(),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("serial", sa.String(255), nullable=True),
        sa.Column("characteristics", sa.Text, nullable=True),
        sa.Column("interval_text", sa.String(128), nullable=True),
        sa.Column("interval_months", sa.Integer, nullable=True),
        sa.Column("last_cal_text", sa.Text, nullable=True),
        sa.Column("last_cal_year", sa.Integer, nullable=True),
        sa.Column("last_cal_month", sa.Integer, nullable=True),
        sa.Column("last_cal_place", sa.Text, nullable=True),
        sa.Column("usage_text", sa.Text, nullable=True),
        sa.Column("usage_refs", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("inherited", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("next_due_year", sa.Integer, nullable=True),
        sa.Column("next_due_month", sa.Integer, nullable=True),
        sa.Column("next_due_derived", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_lab_standard_document_id", "lab_standard", ["document_id"])
    op.create_index("ix_lab_standard_extraction_id", "lab_standard", ["extraction_id"])


def _create_inspector() -> None:
    op.create_table(
        "inspector",
        *_catalog_columns(),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("birth_year", sa.Integer, nullable=True),
        sa.Column("rank", sa.String(128), nullable=True),
        sa.Column("position", sa.Text, nullable=True),
        sa.Column("education", sa.Text, nullable=True),
        sa.Column("specialization", sa.Text, nullable=True),
        sa.Column("fields", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("card_no", sa.String(128), nullable=True),
        sa.Column("card_date", sa.Date, nullable=True),
    )
    op.create_index("ix_inspector_document_id", "inspector", ["document_id"])
    op.create_index("ix_inspector_extraction_id", "inspector", ["extraction_id"])


def _create_procedure_catalog() -> None:
    op.create_table(
        "procedure_catalog",
        *_catalog_columns(),
        sa.Column("domain", sa.Text, nullable=True),
        sa.Column("group_code", sa.String(16), nullable=True),
        sa.Column("group_title", sa.Text, nullable=True),
        sa.Column("code_text", sa.Text, nullable=False),
        sa.Column("codes", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("issuer", sa.Text, nullable=True),
        sa.Column("year_issued", sa.Integer, nullable=True),
        sa.Column("inherited", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("procedure_number", sa.String(32), nullable=True),
    )
    op.create_index("ix_procedure_catalog_document_id", "procedure_catalog", ["document_id"])
    op.create_index("ix_procedure_catalog_extraction_id", "procedure_catalog", ["extraction_id"])
    op.create_index("ix_procedure_catalog_procedure_number", "procedure_catalog", ["procedure_number"])


def _create_capability() -> None:
    op.create_table(
        "capability",
        *_catalog_columns(),
        sa.Column("group_code", sa.String(16), nullable=True),
        sa.Column("group_title", sa.Text, nullable=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("parameters", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("procedure_codes", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("inspector_count", sa.Integer, nullable=True),
        sa.Column("recognition", sa.String(32), nullable=True),
    )
    op.create_index("ix_capability_document_id", "capability", ["document_id"])
    op.create_index("ix_capability_extraction_id", "capability", ["extraction_id"])


def upgrade() -> None:
    _create_lab_standard()
    _create_inspector()
    _create_procedure_catalog()
    _create_capability()
    create_catalog_views(op.get_bind())


def downgrade() -> None:
    drop_catalog_views(op.get_bind())

    op.drop_index("ix_capability_extraction_id", table_name="capability")
    op.drop_index("ix_capability_document_id", table_name="capability")
    op.drop_table("capability")

    op.drop_index("ix_procedure_catalog_procedure_number", table_name="procedure_catalog")
    op.drop_index("ix_procedure_catalog_extraction_id", table_name="procedure_catalog")
    op.drop_index("ix_procedure_catalog_document_id", table_name="procedure_catalog")
    op.drop_table("procedure_catalog")

    op.drop_index("ix_inspector_extraction_id", table_name="inspector")
    op.drop_index("ix_inspector_document_id", table_name="inspector")
    op.drop_table("inspector")

    op.drop_index("ix_lab_standard_extraction_id", table_name="lab_standard")
    op.drop_index("ix_lab_standard_document_id", table_name="lab_standard")
    op.drop_table("lab_standard")
