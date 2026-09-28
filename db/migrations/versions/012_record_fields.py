"""Pha R: trường đầu mục biên bản + nguyên văn từng ô + phạm vi đo của thiết bị.

- bảng ``record_field``: mọi trường đầu mục của một biên bản (phạm vi đo, cấp
  chính xác, phương tiện kiểm định, A0, uCmax...), giữ nguyên văn + trích dẫn;
- cột ``measurement_point.cells``: nguyên văn mọi ô của dòng kèm tên cột;
- view ``v_record_field`` (chỉ hồ sơ đã duyệt, P3);
- ``v_record_detail`` lấy phạm vi đo/cấp chính xác của CHÍNH thiết bị, chỉ rơi về
  MỘT dữ kiện QTKĐ khi biên bản không ghi; ``v_measurement_detail`` lộ ``cells``.

Không tính lại số nào (P2). ``downgrade`` khôi phục view Sprint M rồi bỏ bảng/cột.

Revision ID: 012_record_fields
Revises: 011_nas_catalogs
"""

import sqlalchemy as sa
from alembic import op

from db.views import create_field_views, drop_field_views, recreate_record_detail_views

revision = "012_record_fields"
down_revision = "011_nas_catalogs"
branch_labels = None
depends_on = None


def _create_record_field() -> None:
    op.create_table(
        "record_field",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "record_id", sa.Integer, sa.ForeignKey("calibration_record.id"), nullable=False
        ),
        sa.Column("ord", sa.Integer, nullable=True),
        sa.Column("field_key", sa.String(128), nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("value_text", sa.Text, nullable=True),
        sa.Column("quote", sa.Text, nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="appendix"),
        sa.Column("rel_op", sa.String(16), nullable=True),
        sa.Column("value_min", sa.Float, nullable=True),
        sa.Column("value_max", sa.Float, nullable=True),
        sa.Column("unit_id", sa.Integer, sa.ForeignKey("unit.id"), nullable=True),
        sa.Column("unit_text", sa.String(64), nullable=True),
    )
    op.create_index("ix_record_field_record_id", "record_field", ["record_id"])
    op.create_index("ix_record_field_field_key", "record_field", ["field_key"])


def upgrade() -> None:
    _create_record_field()
    op.add_column("measurement_point", sa.Column("cells", sa.JSON, nullable=True))
    bind = op.get_bind()
    create_field_views(bind)
    recreate_record_detail_views(bind, with_record_fields=True)


def downgrade() -> None:
    bind = op.get_bind()
    # Khôi phục view cũ TRƯỚC khi bỏ bảng/cột mà view mới tham chiếu.
    recreate_record_detail_views(bind, with_record_fields=False)
    drop_field_views(bind)
    op.drop_column("measurement_point", "cells")
    op.drop_index("ix_record_field_field_key", table_name="record_field")
    op.drop_index("ix_record_field_record_id", table_name="record_field")
    op.drop_table("record_field")
