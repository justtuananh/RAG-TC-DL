"""Sprint 7: device, calibration_record, measurement_point + view đã duyệt.

Hồ sơ kiểm định và phiếu đo vào sổ cái qua `extraction` (``pending``) nên P3 chỉ
lộ dữ liệu đã duyệt qua ``v_calibration_record``/``v_measurement_point``. Khóa
nhận dạng thiết bị là ``(device_type_id, serial_norm)``; thiếu serial → thiết bị
tạm gắn ``needs_identification``.

Revision ID: 006_create_records
Revises: 005_review_indexes
"""

import sqlalchemy as sa
from alembic import op

from db.views import create_record_views, drop_record_views

revision = "006_create_records"
down_revision = "005_review_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("device_type_id", sa.Integer, sa.ForeignKey("device_type.id"), nullable=True),
        sa.Column("serial_no", sa.String(128), nullable=True),
        sa.Column("serial_norm", sa.String(128), nullable=True),
        sa.Column("model_code", sa.String(255), nullable=True),
        sa.Column("manufacturer", sa.String(255), nullable=True),
        sa.Column("owner_org", sa.String(255), nullable=True),
        sa.Column("attrs", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("needs_identification", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "device_type_id", "serial_norm", name="uq_device_type_serial_norm"
        ),
    )
    op.create_index("ix_device_device_type_id", "device", ["device_type_id"])
    op.create_index("ix_device_serial_no", "device", ["serial_no"])
    op.create_index("ix_device_serial_norm", "device", ["serial_norm"])
    op.create_index("ix_device_needs_identification", "device", ["needs_identification"])

    op.create_table(
        "calibration_record",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.String(128), sa.ForeignKey("document.id"), nullable=True),
        sa.Column(
            "extraction_id", sa.Integer, sa.ForeignKey("extraction.id"), nullable=False
        ),
        sa.Column("device_id", sa.Integer, sa.ForeignKey("device.id"), nullable=True),
        sa.Column("procedure_id", sa.Integer, sa.ForeignKey("procedure.id"), nullable=True),
        sa.Column("mode", sa.String(32), nullable=True),
        sa.Column("calibrated_at", sa.DateTime, nullable=True),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column(
            "expires_from_fact_id",
            sa.Integer,
            sa.ForeignKey("procedure_fact.id"),
            nullable=True,
        ),
        sa.Column("verdict", sa.String(16), nullable=True),
        sa.Column("cert_no", sa.String(128), nullable=True),
        sa.Column("inspector_name", sa.String(255), nullable=True),
        sa.Column("reviewer_name", sa.String(255), nullable=True),
        sa.Column("lab_name", sa.String(255), nullable=True),
        sa.Column("env_temp_c", sa.Float, nullable=True),
        sa.Column("env_humidity_pct", sa.Float, nullable=True),
        sa.Column("source_text", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_calibration_record_document_id", "calibration_record", ["document_id"])
    op.create_index(
        "ix_calibration_record_extraction_id", "calibration_record", ["extraction_id"]
    )
    op.create_index("ix_calibration_record_device_id", "calibration_record", ["device_id"])
    op.create_index(
        "ix_calibration_record_procedure_id", "calibration_record", ["procedure_id"]
    )

    op.create_table(
        "measurement_point",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "record_id", sa.Integer, sa.ForeignKey("calibration_record.id"), nullable=False
        ),
        sa.Column("ord", sa.Integer, nullable=True),
        sa.Column("step_code", sa.String(32), nullable=True),
        sa.Column("label", sa.Text, nullable=True),
        sa.Column("nominal_value", sa.Float, nullable=True),
        sa.Column("measured_value", sa.Float, nullable=True),
        sa.Column("error_value", sa.Float, nullable=True),
        sa.Column("unit_id", sa.Integer, sa.ForeignKey("unit.id"), nullable=True),
        sa.Column("limit_value", sa.Float, nullable=True),
        sa.Column("within_limit", sa.Integer, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("quote", sa.Text, nullable=True),
        sa.Column("nominal_text", sa.Text, nullable=True),
        sa.Column("measured_text", sa.Text, nullable=True),
        sa.Column("error_text", sa.Text, nullable=True),
        sa.Column("limit_text", sa.Text, nullable=True),
    )
    op.create_index("ix_measurement_point_record_id", "measurement_point", ["record_id"])
    op.create_index("ix_measurement_point_step_code", "measurement_point", ["step_code"])

    # P3 cho dữ liệu đo — nguồn sự thật chung ở db/views.py.
    create_record_views(op.get_bind())


def downgrade() -> None:
    drop_record_views(op.get_bind())

    op.drop_index("ix_measurement_point_step_code", table_name="measurement_point")
    op.drop_index("ix_measurement_point_record_id", table_name="measurement_point")
    op.drop_table("measurement_point")

    op.drop_index("ix_calibration_record_procedure_id", table_name="calibration_record")
    op.drop_index("ix_calibration_record_device_id", table_name="calibration_record")
    op.drop_index("ix_calibration_record_extraction_id", table_name="calibration_record")
    op.drop_index("ix_calibration_record_document_id", table_name="calibration_record")
    op.drop_table("calibration_record")

    op.drop_index("ix_device_needs_identification", table_name="device")
    op.drop_index("ix_device_serial_norm", table_name="device")
    op.drop_index("ix_device_serial_no", table_name="device")
    op.drop_index("ix_device_device_type_id", table_name="device")
    op.drop_table("device")
