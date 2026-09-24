"""Sprint 9: view tham chiếu cho chat số liệu (đại lượng, loại thiết bị, QTKĐ).

Chat lai văn bản + số liệu cần phân giải tham số người dùng ("số QTKĐ", "loại
thiết bị", "đại lượng") thành id trước khi gọi truy vấn tham số hóa trên các view
dữ liệu đã duyệt. Migration này tạo ba view tham chiếu (P3: tầng ``query/`` không
bao giờ chạm bảng gốc):

- ``v_quantity`` — đại lượng đo.
- ``v_device_type`` — loại phương tiện đo kèm đại lượng.
- ``v_procedure`` — QTKĐ kèm loại thiết bị/đại lượng.

Đây là dữ liệu nền giống ``v_unit`` (Sprint 8), không gắn trạng thái duyệt.

Revision ID: 008_reference_views
Revises: 007_query_views
"""

from alembic import op

from db.views import create_reference_views, drop_reference_views

revision = "008_reference_views"
down_revision = "007_query_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    create_reference_views(op.get_bind())


def downgrade() -> None:
    drop_reference_views(op.get_bind())
