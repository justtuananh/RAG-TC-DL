"""Trang Hồ sơ QTKĐ: ``v_procedure`` lộ tên tài liệu gốc.

Trang tri thức của một QTKĐ cần mở được tài liệu gốc (``file_stem``, tên hiển thị)
trong khi tầng ``query/`` chỉ được đọc view. Migration này tạo lại ``v_procedure``
với hai cột ``document_file_stem`` và ``document_name`` (LEFT JOIN ``document``).
Không đổi dữ liệu; ``downgrade`` khôi phục định nghĩa Sprint 9.

Revision ID: 013_procedure_document
Revises: 012_record_fields
"""

from alembic import op

from db.views import recreate_procedure_view

revision = "013_procedure_document"
down_revision = "012_record_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    recreate_procedure_view(op.get_bind())


def downgrade() -> None:
    recreate_procedure_view(op.get_bind(), with_document=False)
