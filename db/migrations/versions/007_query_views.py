"""Sprint 8: view bề mặt tra cứu + index phục vụ bảng lọc dữ liệu.

Bề mặt tra cứu (tab "Dữ liệu", lịch sử thiết bị, xuất Excel) chỉ được đọc view đã
duyệt (P3). Migration này tạo:

- ``v_extraction`` — extraction đã duyệt kèm ``file_stem`` để dựng xuất xứ P1.
- ``v_record_detail`` — một dòng/hồ sơ đã duyệt đã nối sẵn thiết bị, loại, đại
  lượng, QTKĐ và phạm vi/cấp chính xác đã duyệt của QTKĐ.

Hai index trên ``calibration_record`` phục vụ lọc/sắp xếp theo thời gian và kết
luận của bảng dữ liệu 10 nghìn hồ sơ.

Revision ID: 007_query_views
Revises: 006_create_records
"""

from alembic import op

from db.views import create_query_views, drop_query_views

revision = "007_query_views"
down_revision = "006_create_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_calibration_record_calibrated_at", "calibration_record", ["calibrated_at"]
    )
    op.create_index("ix_calibration_record_verdict", "calibration_record", ["verdict"])
    create_query_views(op.get_bind())


def downgrade() -> None:
    drop_query_views(op.get_bind())
    op.drop_index("ix_calibration_record_verdict", table_name="calibration_record")
    op.drop_index(
        "ix_calibration_record_calibrated_at", table_name="calibration_record"
    )
