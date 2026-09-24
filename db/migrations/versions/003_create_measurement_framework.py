"""Sprint 3: measurement concept framework (quantity/unit/device_type/procedure).

Revision ID: 003_create_measurement_framework
Revises: 002_create_document
"""
from alembic import op
import sqlalchemy as sa

from knowledge.seed_data import DEVICE_TYPES, QUANTITIES, UNITS

revision = "003_create_measurement_framework"
down_revision = "002_create_document"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quantity",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name_vi", sa.String(255), nullable=False),
        sa.Column("si_unit_code", sa.String(32), nullable=False),
    )
    op.create_index("ix_quantity_code", "quantity", ["code"], unique=True)

    op.create_table(
        "unit",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name_vi", sa.String(255), nullable=False),
        sa.Column("quantity_id", sa.Integer, sa.ForeignKey("quantity.id"), nullable=False),
        sa.Column("factor_to_si", sa.Float, nullable=False),
        sa.Column("offset_to_si", sa.Float, nullable=False, server_default="0"),
        sa.Column("aliases", sa.JSON, nullable=False),
    )
    op.create_index("ix_unit_code", "unit", ["code"], unique=True)
    op.create_index("ix_unit_quantity_id", "unit", ["quantity_id"])

    op.create_table(
        "device_type",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name_vi", sa.String(255), nullable=False),
        sa.Column("aliases", sa.JSON, nullable=False),
        sa.Column("quantity_id", sa.Integer, sa.ForeignKey("quantity.id"), nullable=True),
    )
    op.create_index("ix_device_type_name_vi", "device_type", ["name_vi"], unique=True)
    op.create_index("ix_device_type_quantity_id", "device_type", ["quantity_id"])

    op.create_table(
        "procedure",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.String(128), sa.ForeignKey("document.id"), nullable=True),
        sa.Column("number", sa.String(32), nullable=False),
        sa.Column("year", sa.Integer, nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("device_type_id", sa.Integer, sa.ForeignKey("device_type.id"), nullable=True),
        sa.Column("edition", sa.String(64), nullable=True),
    )
    op.create_index("ix_procedure_number", "procedure", ["number"], unique=True)
    op.create_index("ix_procedure_document_id", "procedure", ["document_id"])
    op.create_index("ix_procedure_device_type_id", "procedure", ["device_type_id"])

    _seed_reference_data()


def _seed_reference_data() -> None:
    """Seed khung khái niệm từ knowledge.seed_data (id tường minh)."""
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
    device_type_table = sa.table(
        "device_type",
        sa.column("id", sa.Integer),
        sa.column("name_vi", sa.String),
        sa.column("aliases", sa.JSON),
        sa.column("quantity_id", sa.Integer),
    )

    bind = op.get_bind()
    bind.execute(quantity_table.insert(), QUANTITIES)
    bind.execute(unit_table.insert(), UNITS)
    bind.execute(device_type_table.insert(), DEVICE_TYPES)


def downgrade() -> None:
    op.drop_index("ix_procedure_device_type_id", table_name="procedure")
    op.drop_index("ix_procedure_document_id", table_name="procedure")
    op.drop_index("ix_procedure_number", table_name="procedure")
    op.drop_table("procedure")

    op.drop_index("ix_device_type_quantity_id", table_name="device_type")
    op.drop_index("ix_device_type_name_vi", table_name="device_type")
    op.drop_table("device_type")

    op.drop_index("ix_unit_quantity_id", table_name="unit")
    op.drop_index("ix_unit_code", table_name="unit")
    op.drop_table("unit")

    op.drop_index("ix_quantity_code", table_name="quantity")
    op.drop_table("quantity")
