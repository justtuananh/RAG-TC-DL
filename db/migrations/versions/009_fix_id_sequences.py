"""Sprint 9 fix: đồng bộ sequence id sau khi migration 003 chèn id tường minh.

``003_create_measurement_framework`` seed ``quantity``/``unit``/``device_type``
bằng id tường minh (``knowledge.seed_data``). Trên PostgreSQL, ``INSERT`` có id
tường minh KHÔNG nâng sequence của cột, nên ``last_value`` đứng ở 1 trong khi
``MAX(id)`` lớn hơn: lần chèn tiếp theo (không id) sẽ trùng khóa chính.

Migration này ``setval`` cho từng bảng về ``MAX(id)``. Idempotent và chỉ chạy
trên PostgreSQL; SQLite (test, DB nhúng) không có sequence nên bỏ qua. Không
hoàn tác được thao tác đồng bộ này nên ``downgrade`` là no-op.

Revision ID: 009_fix_id_sequences
Revises: 008_reference_views
"""

from alembic import op

revision = "009_fix_id_sequences"
down_revision = "008_reference_views"
branch_labels = None
depends_on = None

# Các bảng bị migration 003 chèn id tường minh (đã rà 001-008: chỉ 003 seed).
_SEEDED_TABLES = ("quantity", "unit", "device_type")


def _sync_sequences(bind) -> None:
    """Đưa sequence id của các bảng seed về ``MAX(id)`` hiện có (chỉ Postgres)."""
    if bind.dialect.name != "postgresql":
        return
    for table in _SEEDED_TABLES:
        bind.exec_driver_sql(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
            f"COALESCE((SELECT MAX(id) FROM {table}), 1), "
            f"(SELECT MAX(id) FROM {table}) IS NOT NULL)"
        )


def upgrade() -> None:
    _sync_sequences(op.get_bind())


def downgrade() -> None:
    # Không hoàn tác việc đồng bộ sequence; đây là sửa chữa dữ liệu idempotent.
    pass
