"""Sprint M: đơn vị riêng của sai số + view điểm đo có đơn vị sai số.

Biên bản áp kế pittông (QTKĐ 1.159) có bảng A.4: khối lượng quả cân đo theo ``g``
nhưng sai số TƯƠNG ĐỐI ghi theo ``%``. Trước đây ``measurement_point`` chỉ có một
``unit_id`` nên panel hiển thị sai số kèm sai đơn vị. Migration này:

- thêm cột nullable ``measurement_point.error_unit_id`` (FK ``unit.id``);
- bảo đảm có đơn vị ``%`` (idempotent, an toàn cho cả DB cũ lẫn DB mới);
- tạo lại ``v_measurement_detail`` để lộ ``error_unit_id``/``error_unit_code``.

Không tính lại số nào (P2). ``downgrade`` khôi phục view cũ rồi bỏ cột.

Revision ID: 010_measurement_error_unit
Revises: 009_fix_id_sequences
"""

import sqlalchemy as sa
from alembic import op

from db.views import recreate_measurement_detail_view
from knowledge import seed_data

revision = "010_measurement_error_unit"
down_revision = "009_fix_id_sequences"
branch_labels = None
depends_on = None

_PERCENT_QUANTITY = next(row for row in seed_data.QUANTITIES if row["code"] == "ratio")
_PERCENT_UNIT = next(row for row in seed_data.UNITS if row["code"] == "%")


def _ensure_percent_unit(bind) -> None:
    """Thêm đại lượng tỉ lệ và đơn vị ``%`` nếu còn thiếu (idempotent).

    Migration 003 seed theo ``knowledge.seed_data`` tại thời điểm chạy; DB đã lên
    009 trước Sprint M chưa có ``%`` nên phải chèn bù ở đây. Dùng bảng core để
    kiểu JSON của ``aliases`` được bind đúng trên cả SQLite lẫn PostgreSQL.
    """
    quantity_table = sa.table(
        "quantity",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("name_vi", sa.String),
        sa.column("si_unit_code", sa.String),
    )
    unit_table = sa.table(
        "unit",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("name_vi", sa.String),
        sa.column("quantity_id", sa.Integer),
        sa.column("factor_to_si", sa.Float),
        sa.column("offset_to_si", sa.Float),
        sa.column("aliases", sa.JSON),
    )

    quantity_id = bind.execute(
        sa.select(quantity_table.c.id).where(quantity_table.c.code == _PERCENT_QUANTITY["code"])
    ).scalar()
    if quantity_id is None:
        bind.execute(
            quantity_table.insert().values(
                code=_PERCENT_QUANTITY["code"],
                name_vi=_PERCENT_QUANTITY["name_vi"],
                si_unit_code=_PERCENT_QUANTITY["si_unit_code"],
            )
        )
        quantity_id = bind.execute(
            sa.select(quantity_table.c.id).where(
                quantity_table.c.code == _PERCENT_QUANTITY["code"]
            )
        ).scalar()

    exists = bind.execute(
        sa.select(unit_table.c.id).where(unit_table.c.code == _PERCENT_UNIT["code"])
    ).scalar()
    if exists is None:
        bind.execute(
            unit_table.insert().values(
                code=_PERCENT_UNIT["code"],
                name_vi=_PERCENT_UNIT["name_vi"],
                quantity_id=quantity_id,
                factor_to_si=_PERCENT_UNIT["factor_to_si"],
                offset_to_si=_PERCENT_UNIT["offset_to_si"],
                aliases=list(_PERCENT_UNIT["aliases"]),
            )
        )


def _add_error_unit_column() -> None:
    """Thêm cột ``error_unit_id`` (FK ``unit.id``)."""
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite: Alembic tách FK thành ADD CONSTRAINT (không hỗ trợ), nhưng
        # ``ADD COLUMN ... REFERENCES`` thì hợp lệ.
        bind.exec_driver_sql(
            "ALTER TABLE measurement_point ADD COLUMN error_unit_id INTEGER REFERENCES unit(id)"
        )
        return
    op.add_column(
        "measurement_point",
        sa.Column(
            "error_unit_id",
            sa.Integer,
            sa.ForeignKey("unit.id", name="fk_measurement_point_error_unit_id"),
            nullable=True,
        ),
    )


def _drop_error_unit_column() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.exec_driver_sql("ALTER TABLE measurement_point DROP COLUMN error_unit_id")
        return
    op.drop_column("measurement_point", "error_unit_id")


def upgrade() -> None:
    _add_error_unit_column()
    _ensure_percent_unit(op.get_bind())
    recreate_measurement_detail_view(op.get_bind(), with_error_unit=True)


def downgrade() -> None:
    # Khôi phục view cũ TRƯỚC khi bỏ cột mà nó không còn tham chiếu.
    recreate_measurement_detail_view(op.get_bind(), with_error_unit=False)
    _drop_error_unit_column()
