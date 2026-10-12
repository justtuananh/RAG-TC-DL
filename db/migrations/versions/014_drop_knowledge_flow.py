"""Gỡ luồng trích xuất tri thức và nhánh số liệu.

``upgrade`` drop mọi view của luồng tri thức/số liệu, rồi drop các bảng không còn
dùng theo thứ tự phụ thuộc: ``record_field``, ``measurement_point``,
``calibration_record``, ``device``, ``capability``, ``procedure_catalog``,
``inspector``, ``lab_standard``, ``term``, ``procedure_standard``,
``procedure_fact``, ``extraction``; cuối cùng drop enum ``extraction_status``.
Không đụng ``document``, ``app_user``, ``audit_log``, ``quantity``, ``unit``,
``device_type``, ``procedure``.

``downgrade`` dựng lại đúng lược đồ (rỗng) của revision 013 cho các đối tượng đã
drop, tái dùng định nghĩa view đóng băng ở ``db.migrations.legacy_views``.

Revision ID: 014_drop_knowledge_flow
Revises: 013_procedure_document
"""

from alembic import op
import sqlalchemy as sa

from db.migrations.legacy_views import create_all_approved_views

revision = "014_drop_knowledge_flow"
down_revision = "013_procedure_document"
branch_labels = None
depends_on = None


# View của luồng tri thức/số liệu, theo thứ tự AN TOÀN phụ thuộc: view phụ thuộc
# được drop trước view nó tham chiếu (PostgreSQL chặn drop view còn bị tham chiếu).
_VIEWS_DROP_ORDER = (
    "v_measurement_detail",
    "v_measurement_point",
    "v_record_field",
    "v_record_detail",
    "v_lab_standard",
    "v_inspector",
    "v_procedure_catalog",
    "v_capability",
    "v_extraction",
    "v_calibration_record",
    "v_procedure_fact",
    "v_procedure_standard",
    "v_term",
    "v_unit",
    "v_procedure",
    "v_device_type",
    "v_quantity",
)


def _drop_views() -> None:
    """Drop mọi view của luồng tri thức/số liệu (an toàn khi chưa tồn tại)."""
    bind = op.get_bind()
    for name in _VIEWS_DROP_ORDER:
        bind.exec_driver_sql(f"DROP VIEW IF EXISTS {name}")


def upgrade() -> None:
    _drop_views()

    op.drop_index("ix_record_field_field_key", table_name="record_field")
    op.drop_index("ix_record_field_record_id", table_name="record_field")
    op.drop_table("record_field")

    op.drop_index("ix_measurement_point_step_code", table_name="measurement_point")
    op.drop_index("ix_measurement_point_record_id", table_name="measurement_point")
    op.drop_table("measurement_point")

    op.drop_index("ix_calibration_record_verdict", table_name="calibration_record")
    op.drop_index("ix_calibration_record_calibrated_at", table_name="calibration_record")
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

    # Danh mục hồ sơ NAS (Biểu 1, 3, 4, 7).
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

    # Dữ kiện / chuẩn / thuật ngữ (khoá ngoại tới ``extraction``).
    op.drop_index("ix_term_procedure_id", table_name="term")
    op.drop_index("ix_term_extraction_id", table_name="term")
    op.drop_table("term")

    op.drop_index("ix_procedure_standard_procedure_id", table_name="procedure_standard")
    op.drop_index("ix_procedure_standard_extraction_id", table_name="procedure_standard")
    op.drop_table("procedure_standard")

    op.drop_index("ix_procedure_fact_fact_kind", table_name="procedure_fact")
    op.drop_index("ix_procedure_fact_procedure_id", table_name="procedure_fact")
    op.drop_index("ix_procedure_fact_extraction_id", table_name="procedure_fact")
    op.drop_table("procedure_fact")

    op.drop_index("ix_extraction_confidence", table_name="extraction")
    op.drop_index("ix_extraction_extractor", table_name="extraction")
    op.drop_index("ix_extraction_status", table_name="extraction")
    op.drop_index("ix_extraction_document_id", table_name="extraction")
    op.drop_table("extraction")

    # Enum Postgres chỉ ``extraction`` dùng.
    sa.Enum(name="extraction_status").drop(op.get_bind(), checkfirst=True)


# ── downgrade: dựng lại lược đồ rỗng đúng như revision 013 ─────────────────────

_STATUS_ENUM_VALUES = ("pending", "approved", "rejected", "superseded")


def _create_extraction() -> None:
    status = sa.Enum(*_STATUS_ENUM_VALUES, name="extraction_status")
    op.create_table(
        "extraction",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.String(128), sa.ForeignKey("document.id"), nullable=False),
        sa.Column("section_path", sa.String(512), nullable=True),
        sa.Column("chunk_id", sa.String(128), nullable=True),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("char_start", sa.Integer, nullable=True),
        sa.Column("char_end", sa.Integer, nullable=True),
        sa.Column("extractor", sa.String(128), nullable=False),
        sa.Column("extractor_version", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("status", status, nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.Integer, sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime, nullable=True),
        sa.Column("review_note", sa.Text, nullable=True),
        sa.Column("supersedes_id", sa.Integer, sa.ForeignKey("extraction.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_extraction_document_id", "extraction", ["document_id"])
    op.create_index("ix_extraction_status", "extraction", ["status"])
    op.create_index("ix_extraction_extractor", "extraction", ["extractor"])
    op.create_index("ix_extraction_confidence", "extraction", ["confidence"])


def _create_device() -> None:
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


def _create_fact_tables() -> None:
    op.create_table(
        "procedure_fact",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "extraction_id", sa.Integer, sa.ForeignKey("extraction.id"), nullable=False
        ),
        sa.Column("procedure_id", sa.Integer, sa.ForeignKey("procedure.id"), nullable=True),
        sa.Column("fact_kind", sa.String(32), nullable=False),
        sa.Column("label", sa.Text, nullable=True),
        sa.Column("rel_op", sa.String(16), nullable=True),
        sa.Column("value_min", sa.Float, nullable=True),
        sa.Column("value_max", sa.Float, nullable=True),
        sa.Column("unit_id", sa.Integer, sa.ForeignKey("unit.id"), nullable=True),
        sa.Column("value_text", sa.Text, nullable=True),
        sa.Column("condition_text", sa.Text, nullable=True),
    )
    op.create_index("ix_procedure_fact_extraction_id", "procedure_fact", ["extraction_id"])
    op.create_index("ix_procedure_fact_procedure_id", "procedure_fact", ["procedure_id"])
    op.create_index("ix_procedure_fact_fact_kind", "procedure_fact", ["fact_kind"])

    op.create_table(
        "procedure_standard",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "extraction_id", sa.Integer, sa.ForeignKey("extraction.id"), nullable=False
        ),
        sa.Column("procedure_id", sa.Integer, sa.ForeignKey("procedure.id"), nullable=True),
        sa.Column("ord", sa.Integer, nullable=True),
        sa.Column("name_vi", sa.Text, nullable=False),
        sa.Column("range_text", sa.Text, nullable=True),
        sa.Column("accuracy_text", sa.Text, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_procedure_standard_extraction_id", "procedure_standard", ["extraction_id"]
    )
    op.create_index(
        "ix_procedure_standard_procedure_id", "procedure_standard", ["procedure_id"]
    )

    op.create_table(
        "term",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "extraction_id", sa.Integer, sa.ForeignKey("extraction.id"), nullable=False
        ),
        sa.Column("procedure_id", sa.Integer, sa.ForeignKey("procedure.id"), nullable=True),
        sa.Column("term_vi", sa.Text, nullable=False),
        sa.Column("term_en", sa.Text, nullable=True),
        sa.Column("definition", sa.Text, nullable=True),
    )
    op.create_index("ix_term_extraction_id", "term", ["extraction_id"])
    op.create_index("ix_term_procedure_id", "term", ["procedure_id"])


def _add_error_unit_column() -> None:
    """Thêm ``measurement_point.error_unit_id`` y như migration 010.

    SQLite không hỗ trợ ADD CONSTRAINT nên dùng ``ADD COLUMN ... REFERENCES``;
    PostgreSQL dùng ``op.add_column`` để có đúng tên khoá ngoại như 010.
    """
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
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


def _create_records() -> None:
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
    op.create_index(
        "ix_calibration_record_calibrated_at", "calibration_record", ["calibrated_at"]
    )
    op.create_index("ix_calibration_record_verdict", "calibration_record", ["verdict"])

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

    # Hai cột dưới được ALTER thêm ở 010/012; thêm lại đúng cách để lược đồ khớp
    # revision 013 (và để chuỗi downgrade trên SQLite chạy được).
    _add_error_unit_column()
    op.add_column("measurement_point", sa.Column("cells", sa.JSON, nullable=True))

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


def _catalog_columns() -> list[sa.Column]:
    """Cột chung của mọi bảng danh mục NAS: xuất xứ + thứ tự + nguyên văn + tìm kiếm."""
    return [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.String(128), sa.ForeignKey("document.id"), nullable=False),
        sa.Column("extraction_id", sa.Integer, sa.ForeignKey("extraction.id"), nullable=False),
        sa.Column("ord", sa.Integer, nullable=True),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("search_text", sa.Text, nullable=True),
    ]


def _create_catalogs() -> None:
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
    op.create_index(
        "ix_procedure_catalog_procedure_number", "procedure_catalog", ["procedure_number"]
    )

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


# Ở revision 013, ``v_measurement_point`` được 006 tạo bằng ``m.*`` TRƯỚC khi 010
# và 012 thêm cột; PostgreSQL đóng băng danh sách cột lúc tạo nên view KHÔNG có
# ``error_unit_id``/``cells``. Dựng lại đúng danh sách cột đó để lược đồ khớp 013.
_MEASUREMENT_POINT_VIEW_013 = (
    "CREATE VIEW v_measurement_point AS "
    "SELECT m.id AS id, m.record_id AS record_id, m.ord AS ord, "
    "m.step_code AS step_code, m.label AS label, "
    "m.nominal_value AS nominal_value, m.measured_value AS measured_value, "
    "m.error_value AS error_value, m.unit_id AS unit_id, "
    "m.limit_value AS limit_value, m.within_limit AS within_limit, "
    "m.note AS note, m.quote AS quote, m.nominal_text AS nominal_text, "
    "m.measured_text AS measured_text, m.error_text AS error_text, "
    "m.limit_text AS limit_text "
    "FROM measurement_point m "
    "JOIN calibration_record r ON r.id = m.record_id "
    "JOIN extraction e ON e.id = r.extraction_id "
    "WHERE e.status = 'approved'"
)


def _restore_measurement_point_view_013() -> None:
    """Ghi đè ``v_measurement_point`` về đúng định nghĩa thời 006 (không cột mới)."""
    bind = op.get_bind()
    bind.exec_driver_sql("DROP VIEW IF EXISTS v_measurement_point")
    bind.exec_driver_sql(_MEASUREMENT_POINT_VIEW_013)


def downgrade() -> None:
    _create_extraction()
    _create_device()
    _create_fact_tables()
    _create_records()
    _create_catalogs()
    create_all_approved_views(op.get_bind())
    _restore_measurement_point_view_013()
