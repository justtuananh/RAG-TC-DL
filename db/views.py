"""Khung nhìn thực thi P3: chỉ dữ liệu đã duyệt mới lộ ra bề mặt sử dụng.

Spec §5.7. Mọi truy vấn của tầng ``query/`` (Sprint 8-9) chỉ được đọc từ các view
này, tuyệt đối không đọc bảng gốc. File này là nguồn sự thật duy nhất cho định
nghĩa view:

- migration ``004_create_extraction`` gọi ``create_approved_views`` khi upgrade;
- test dựng view trên SQLite sạch qua cùng hàm đó;
- ``scan_query_source`` là bộ guard quét mã ``query/`` để chặn truy cập bảng gốc.

View lọc ở tầng cơ sở dữ liệu chứ không phải tầng ứng dụng: dù tầng ứng dụng có
quên lọc ``status`` thì dữ liệu chưa duyệt vẫn không thể lọt ra.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import text

# Tên view đã duyệt tri thức — bề mặt tra cứu chỉ được phép chạm tới những tên này.
APPROVED_VIEWS: tuple[str, ...] = (
    "v_procedure_fact",
    "v_procedure_standard",
    "v_term",
)

# Sprint 7: view đã duyệt cho dữ liệu đo. Tách khỏi ``APPROVED_VIEWS`` vì
# migration 004 (tri thức) tạo view trước khi bảng hồ sơ tồn tại — gộp chung sẽ
# làm hỏng `alembic upgrade` trên cơ sở dữ liệu sạch.
RECORD_VIEWS: tuple[str, ...] = (
    "v_calibration_record",
    "v_measurement_point",
)

# Sprint 8: view phục vụ bề mặt tra cứu dữ liệu (bảng lọc, lịch sử thiết bị,
# xuất xứ từng ô số). Tách nhóm riêng vì migration 007 tạo chúng SAU khi bảng hồ
# sơ (006) và view tri thức (004) đã tồn tại — chúng tham chiếu cả hai.
#
# - ``v_extraction``: extraction đã duyệt kèm ``file_stem`` để dựng xuất xứ P1.
# - ``v_record_detail``: một dòng/hồ sơ đã duyệt đã nối sẵn thiết bị, loại, đại
#   lượng, QTKĐ và phạm vi/cấp chính xác đã duyệt của QTKĐ đó. Nhờ gộp sẵn, tầng
#   ``query/`` chỉ quét một view thay vì tự nối nhiều bảng — vừa nhanh vừa giữ P3.
QUERY_VIEWS: tuple[str, ...] = (
    "v_unit",
    "v_extraction",
    "v_record_detail",
    "v_measurement_detail",
)

# Sprint 9: view tham chiếu cho chat số liệu — đại lượng, loại thiết bị, QTKĐ.
# Đây là dữ liệu nền (không gắn trạng thái duyệt, giống ``v_unit``) nhưng vẫn đi
# qua view để tầng ``query/`` không bao giờ chạm bảng gốc. Chat số liệu cần chúng
# để phân giải tham số "số QTKĐ"/"loại thiết bị"/"đại lượng" thành id trước khi
# gọi truy vấn tham số hóa trên các view dữ liệu đã duyệt.
REFERENCE_VIEWS: tuple[str, ...] = (
    "v_quantity",
    "v_device_type",
    "v_procedure",
)

# Pha D1: view đã duyệt cho bốn danh mục hồ sơ NAS. Mỗi view chỉ lộ dòng có
# extraction ``approved`` (P3) và kèm tên tài liệu để dựng xuất xứ P1.
CATALOG_VIEWS: tuple[str, ...] = (
    "v_lab_standard",
    "v_inspector",
    "v_procedure_catalog",
    "v_capability",
)

# Pha R: trường đầu mục của biên bản (phạm vi đo, A0, uCmax...). Tách nhóm vì
# migration 012 tạo view này SAU khi bảng ``record_field`` tồn tại.
FIELD_VIEWS: tuple[str, ...] = ("v_record_field",)

# Slug nhãn của trường phạm vi đo / cấp chính xác ghi trên CHÍNH biên bản. Đây là
# đặc tính của thiết bị; dữ kiện ``working_range`` của QTKĐ chỉ là phạm vi áp dụng
# của quy trình và chỉ dùng khi biên bản không ghi (``range_source = 'procedure'``).
RANGE_FIELD_KEYS: tuple[str, ...] = ("pham_vi_do", "pham_vi_lam_viec", "gioi_han_do")
ACCURACY_FIELD_KEYS: tuple[str, ...] = ("cap_chinh_xac",)

# Bảng gốc giữ cả dữ liệu chưa duyệt — cấm truy cập trực tiếp từ tầng ``query/``.
RAW_TABLES: tuple[str, ...] = (
    "extraction",
    "procedure_fact",
    "procedure_standard",
    "term",
    "device",
    "calibration_record",
    "measurement_point",
    "record_field",
    "lab_standard",
    "inspector",
    "procedure_catalog",
    "capability",
)

_VIEW_SQL: dict[str, str] = {
    "v_procedure_fact": (
        "CREATE VIEW v_procedure_fact AS "
        "SELECT f.* FROM procedure_fact f "
        "JOIN extraction e ON e.id = f.extraction_id "
        "WHERE e.status = 'approved'"
    ),
    "v_procedure_standard": (
        "CREATE VIEW v_procedure_standard AS "
        "SELECT s.* FROM procedure_standard s "
        "JOIN extraction e ON e.id = s.extraction_id "
        "WHERE e.status = 'approved'"
    ),
    "v_term": (
        "CREATE VIEW v_term AS "
        "SELECT t.* FROM term t "
        "JOIN extraction e ON e.id = t.extraction_id "
        "WHERE e.status = 'approved'"
    ),
}

# View dữ liệu đo: hồ sơ và số liệu đo chỉ lộ khi extraction tương ứng đã duyệt.
# `v_measurement_point` nối qua hồ sơ nên một số liệu đo không thể lọt ra nếu hồ
# sơ chứa nó còn `pending`.
_RECORD_VIEW_SQL: dict[str, str] = {
    "v_calibration_record": (
        "CREATE VIEW v_calibration_record AS "
        "SELECT r.* FROM calibration_record r "
        "JOIN extraction e ON e.id = r.extraction_id "
        "WHERE e.status = 'approved'"
    ),
    "v_measurement_point": (
        "CREATE VIEW v_measurement_point AS "
        "SELECT m.* FROM measurement_point m "
        "JOIN calibration_record r ON r.id = m.record_id "
        "JOIN extraction e ON e.id = r.extraction_id "
        "WHERE e.status = 'approved'"
    ),
}

# Định nghĩa ``v_measurement_detail`` TRƯỚC Sprint M (một đơn vị dùng chung cho cả
# giá trị đo lẫn sai số). Migration 007 tạo view này khi cột ``error_unit_id`` chưa
# tồn tại, nên định nghĩa cũ vẫn được giữ nguyên ở đây cho lịch sử migration.
_MEASUREMENT_DETAIL_SQL_BASE: str = (
    "CREATE VIEW v_measurement_detail AS "
    "SELECT "
    "m.id AS id, m.record_id AS record_id, m.ord AS ord, "
    "m.step_code AS step_code, m.label AS label, "
    "m.nominal_value AS nominal_value, m.measured_value AS measured_value, "
    "m.error_value AS error_value, m.unit_id AS unit_id, "
    "m.limit_value AS limit_value, m.within_limit AS within_limit, "
    "m.note AS note, m.quote AS quote, m.nominal_text AS nominal_text, "
    "m.measured_text AS measured_text, m.error_text AS error_text, "
    "m.limit_text AS limit_text, u.code AS unit_code, u.name_vi AS unit_name, "
    "r.device_id AS device_id, r.calibrated_at AS calibrated_at, "
    "r.extraction_id AS extraction_id, r.verdict AS verdict, "
    "r.procedure_id AS procedure_id, r.serial_no AS serial_no, "
    "r.procedure_number AS procedure_number, r.file_stem AS file_stem "
    "FROM measurement_point m "
    "JOIN v_record_detail r ON r.id = m.record_id "
    "LEFT JOIN unit u ON u.id = m.unit_id"
)

# Định nghĩa HIỆN HÀNH (Sprint M): thêm đơn vị riêng của sai số/giới hạn. Chỉ áp
# dụng SAU migration 010 (khi cột ``error_unit_id`` đã tồn tại) qua
# ``recreate_measurement_detail_view``; test SQLite dựng view trực tiếp cũng dùng nó.
_MEASUREMENT_DETAIL_SQL: str = (
    "CREATE VIEW v_measurement_detail AS "
    "SELECT "
    "m.id AS id, m.record_id AS record_id, m.ord AS ord, "
    "m.step_code AS step_code, m.label AS label, "
    "m.nominal_value AS nominal_value, m.measured_value AS measured_value, "
    "m.error_value AS error_value, m.unit_id AS unit_id, "
    "m.error_unit_id AS error_unit_id, "
    "m.limit_value AS limit_value, m.within_limit AS within_limit, "
    "m.note AS note, m.quote AS quote, m.nominal_text AS nominal_text, "
    "m.measured_text AS measured_text, m.error_text AS error_text, "
    "m.limit_text AS limit_text, u.code AS unit_code, u.name_vi AS unit_name, "
    "eu.code AS error_unit_code, eu.name_vi AS error_unit_name, "
    "r.device_id AS device_id, r.calibrated_at AS calibrated_at, "
    "r.extraction_id AS extraction_id, r.verdict AS verdict, "
    "r.procedure_id AS procedure_id, r.serial_no AS serial_no, "
    "r.procedure_number AS procedure_number, r.file_stem AS file_stem "
    "FROM measurement_point m "
    "JOIN v_record_detail r ON r.id = m.record_id "
    "LEFT JOIN unit u ON u.id = m.unit_id "
    "LEFT JOIN unit eu ON eu.id = m.error_unit_id"
)

# Định nghĩa HIỆN HÀNH (Pha R): thêm ``cells`` (nguyên văn mọi ô của dòng kèm tên
# cột). Chỉ áp dụng SAU migration 012 khi cột ``measurement_point.cells`` tồn tại.
_MEASUREMENT_DETAIL_SQL_CELLS: str = _MEASUREMENT_DETAIL_SQL.replace(
    "m.limit_text AS limit_text, ", "m.limit_text AS limit_text, m.cells AS cells, "
)


def _sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


# ``v_record_detail`` HIỆN HÀNH (Pha R). Khác định nghĩa Sprint 8 ở hai điểm:
# - phạm vi đo / cấp chính xác lấy từ trường ghi trên CHÍNH biên bản
#   (``record_field``); chỉ khi biên bản không ghi mới rơi về dữ kiện QTKĐ;
# - khi rơi về QTKĐ, chọn MỘT dữ kiện ``working_range`` (khoảng rộng nhất) thay vì
#   ``MAX()`` từng cột — trước đây cận dưới và cận trên có thể đến từ hai dữ kiện
#   khác nhau, sinh ra một khoảng không tài liệu nào ghi (vi phạm P1/P2).
_RECORD_DETAIL_SQL: str = (
    "CREATE VIEW v_record_detail AS "
    "SELECT "
    "r.id AS id, r.document_id AS document_id, r.extraction_id AS extraction_id, "
    "r.device_id AS device_id, r.procedure_id AS procedure_id, r.mode AS mode, "
    "r.calibrated_at AS calibrated_at, r.expires_at AS expires_at, "
    "r.expires_from_fact_id AS expires_from_fact_id, r.verdict AS verdict, "
    "r.cert_no AS cert_no, r.inspector_name AS inspector_name, "
    "r.reviewer_name AS reviewer_name, r.lab_name AS lab_name, "
    "r.env_temp_c AS env_temp_c, r.env_humidity_pct AS env_humidity_pct, "
    "r.created_at AS created_at, "
    "d.device_type_id AS device_type_id, d.serial_no AS serial_no, "
    "d.model_code AS model_code, d.manufacturer AS manufacturer, "
    "d.owner_org AS owner_org, d.needs_identification AS needs_identification, "
    "dt.name_vi AS device_type_name, dt.quantity_id AS quantity_id, "
    "q.name_vi AS quantity_name, "
    "p.number AS procedure_number, p.title AS procedure_title, p.year AS procedure_year, "
    "e.section_path AS extraction_section_path, e.chunk_id AS extraction_chunk_id, "
    "e.quote AS extraction_quote, e.file_stem AS file_stem, "
    "e.extractor AS extractor, e.confidence AS confidence, "
    "CASE WHEN rf.id IS NOT NULL THEN rf.value_min ELSE pf.value_min END AS range_min, "
    "CASE WHEN rf.id IS NOT NULL THEN rf.value_max ELSE pf.value_max END AS range_max, "
    "CASE WHEN rf.id IS NOT NULL THEN rf.unit_id ELSE pf.unit_id END AS range_unit_id, "
    "ru.code AS range_unit_code, "
    "CASE WHEN rf.id IS NULL THEN pf.id END AS range_fact_id, "
    "rf.id AS range_field_id, "
    "CASE WHEN rf.id IS NOT NULL THEN 'record' "
    "WHEN pf.id IS NOT NULL THEN 'procedure' END AS range_source, "
    "CASE WHEN rf.id IS NOT NULL THEN rf.value_text ELSE pf.value_text END AS range_text, "
    "CASE WHEN af.id IS NOT NULL THEN af.value_text ELSE apf.value_text END "
    "AS accuracy_text, "
    "CASE WHEN af.id IS NULL THEN apf.id END AS accuracy_fact_id, "
    "af.id AS accuracy_field_id "
    "FROM calibration_record r "
    "JOIN v_extraction e ON e.id = r.extraction_id "
    "LEFT JOIN device d ON d.id = r.device_id "
    "LEFT JOIN device_type dt ON dt.id = d.device_type_id "
    "LEFT JOIN quantity q ON q.id = dt.quantity_id "
    "LEFT JOIN procedure p ON p.id = r.procedure_id "
    "LEFT JOIN record_field rf ON rf.id = ("
    "SELECT MIN(f.id) FROM record_field f WHERE f.record_id = r.id "
    f"AND f.field_key IN ({_sql_list(RANGE_FIELD_KEYS)}) "
    "AND (f.value_min IS NOT NULL OR f.value_max IS NOT NULL)) "
    "LEFT JOIN record_field af ON af.id = ("
    "SELECT MIN(f.id) FROM record_field f WHERE f.record_id = r.id "
    f"AND f.field_key IN ({_sql_list(ACCURACY_FIELD_KEYS)}) "
    "AND f.value_text IS NOT NULL AND f.value_text <> '') "
    "LEFT JOIN v_procedure_fact pf ON pf.id = ("
    "SELECT f.id FROM v_procedure_fact f WHERE f.procedure_id = r.procedure_id "
    "AND f.fact_kind = 'working_range' "
    "ORDER BY COALESCE(f.value_max, 0) - COALESCE(f.value_min, 0) DESC, f.id DESC LIMIT 1) "
    "LEFT JOIN v_procedure_fact apf ON apf.id = ("
    "SELECT f.id FROM v_procedure_fact f WHERE f.procedure_id = r.procedure_id "
    "AND f.fact_kind = 'accuracy_class' ORDER BY f.id DESC LIMIT 1) "
    "LEFT JOIN unit ru ON ru.id = "
    "(CASE WHEN rf.id IS NOT NULL THEN rf.unit_id ELSE pf.unit_id END)"
)

# Trường đầu mục đã duyệt: lộ khi hồ sơ chứa nó có extraction ``approved`` (P3).
_FIELD_VIEW_SQL: dict[str, str] = {
    "v_record_field": (
        "CREATE VIEW v_record_field AS "
        "SELECT f.id AS id, f.record_id AS record_id, f.ord AS ord, "
        "f.field_key AS field_key, f.label AS label, f.value_text AS value_text, "
        "f.quote AS quote, f.source AS source, f.rel_op AS rel_op, "
        "f.value_min AS value_min, f.value_max AS value_max, "
        "f.unit_id AS unit_id, f.unit_text AS unit_text, u.code AS unit_code, "
        "r.extraction_id AS extraction_id, r.device_id AS device_id, "
        "r.procedure_id AS procedure_id, r.calibrated_at AS calibrated_at "
        "FROM record_field f "
        "JOIN calibration_record r ON r.id = f.record_id "
        "JOIN extraction e ON e.id = r.extraction_id "
        "LEFT JOIN unit u ON u.id = f.unit_id "
        "WHERE e.status = 'approved'"
    ),
}

# View Sprint 8: xuất xứ P1 cho extraction đã duyệt và một dòng tra cứu "dày" đã
# nối sẵn. `v_record_detail` tham chiếu `v_procedure_fact`/`v_extraction` nên phải
# được tạo SAU chúng — thứ tự trong `QUERY_VIEWS` và lời gọi create phản ánh điều đó.
_QUERY_VIEW_SQL: dict[str, str] = {
    # Bảng đơn vị là dữ liệu tham chiếu (không gắn trạng thái duyệt) nhưng vẫn đi
    # qua view để tầng ``query/`` không bao giờ chạm bảng gốc.
    "v_unit": ("CREATE VIEW v_unit AS SELECT * FROM unit"),
    "v_extraction": (
        "CREATE VIEW v_extraction AS "
        "SELECT e.*, doc.file_stem AS file_stem, doc.display_name AS display_name "
        "FROM extraction e "
        "LEFT JOIN document doc ON doc.id = e.document_id "
        "WHERE e.status = 'approved'"
    ),
    "v_record_detail": (
        "CREATE VIEW v_record_detail AS "
        "SELECT "
        "r.id AS id, r.document_id AS document_id, r.extraction_id AS extraction_id, "
        "r.device_id AS device_id, r.procedure_id AS procedure_id, r.mode AS mode, "
        "r.calibrated_at AS calibrated_at, r.expires_at AS expires_at, "
        "r.expires_from_fact_id AS expires_from_fact_id, r.verdict AS verdict, "
        "r.cert_no AS cert_no, r.inspector_name AS inspector_name, "
        "r.reviewer_name AS reviewer_name, r.lab_name AS lab_name, "
        "r.env_temp_c AS env_temp_c, r.env_humidity_pct AS env_humidity_pct, "
        "r.created_at AS created_at, "
        "d.device_type_id AS device_type_id, d.serial_no AS serial_no, "
        "d.model_code AS model_code, d.manufacturer AS manufacturer, "
        "d.owner_org AS owner_org, d.needs_identification AS needs_identification, "
        "dt.name_vi AS device_type_name, dt.quantity_id AS quantity_id, "
        "q.name_vi AS quantity_name, "
        "p.number AS procedure_number, p.title AS procedure_title, p.year AS procedure_year, "
        "e.section_path AS extraction_section_path, e.chunk_id AS extraction_chunk_id, "
        "e.quote AS extraction_quote, e.file_stem AS file_stem, "
        "e.extractor AS extractor, e.confidence AS confidence, "
        "pf.range_min AS range_min, pf.range_max AS range_max, "
        "pf.range_unit_id AS range_unit_id, ru.code AS range_unit_code, "
        "pf.range_fact_id AS range_fact_id, "
        "pf.accuracy_text AS accuracy_text, pf.accuracy_fact_id AS accuracy_fact_id "
        "FROM calibration_record r "
        "JOIN v_extraction e ON e.id = r.extraction_id "
        "LEFT JOIN device d ON d.id = r.device_id "
        "LEFT JOIN device_type dt ON dt.id = d.device_type_id "
        "LEFT JOIN quantity q ON q.id = dt.quantity_id "
        "LEFT JOIN procedure p ON p.id = r.procedure_id "
        "LEFT JOIN ("
        "SELECT procedure_id, "
        "MAX(CASE WHEN fact_kind = 'working_range' THEN value_min END) AS range_min, "
        "MAX(CASE WHEN fact_kind = 'working_range' THEN value_max END) AS range_max, "
        "MAX(CASE WHEN fact_kind = 'working_range' THEN unit_id END) AS range_unit_id, "
        "MAX(CASE WHEN fact_kind = 'working_range' THEN id END) AS range_fact_id, "
        "MAX(CASE WHEN fact_kind = 'accuracy_class' THEN value_text END) AS accuracy_text, "
        "MAX(CASE WHEN fact_kind = 'accuracy_class' THEN id END) AS accuracy_fact_id "
        "FROM v_procedure_fact GROUP BY procedure_id"
        ") pf ON pf.procedure_id = r.procedure_id "
        "LEFT JOIN unit ru ON ru.id = pf.range_unit_id"
    ),
    # Một dòng số liệu đo đã duyệt, kèm đơn vị và ngữ cảnh hồ sơ để bề mặt tra cứu
    # chỉ quét DUY NHẤT một view (không đọc bảng đơn vị trực tiếp).
    "v_measurement_detail": _MEASUREMENT_DETAIL_SQL_BASE,
}

# View tham chiếu Sprint 9: dữ liệu nền để phân giải tham số chat số liệu. Không
# tham chiếu view khác nên thứ tự tạo không quan trọng.
_REFERENCE_VIEW_SQL: dict[str, str] = {
    "v_quantity": (
        "CREATE VIEW v_quantity AS "
        "SELECT id AS id, code AS code, name_vi AS name_vi, si_unit_code AS si_unit_code "
        "FROM quantity"
    ),
    "v_device_type": (
        "CREATE VIEW v_device_type AS "
        "SELECT dt.id AS id, dt.name_vi AS name_vi, dt.aliases AS aliases, "
        "dt.quantity_id AS quantity_id, q.name_vi AS quantity_name, q.code AS quantity_code "
        "FROM device_type dt LEFT JOIN quantity q ON q.id = dt.quantity_id"
    ),
    "v_procedure": (
        "CREATE VIEW v_procedure AS "
        "SELECT p.id AS id, p.number AS number, p.year AS year, p.title AS title, "
        "p.edition AS edition, p.document_id AS document_id, "
        "p.device_type_id AS device_type_id, dt.name_vi AS device_type_name, "
        "dt.quantity_id AS quantity_id, q.name_vi AS quantity_name, q.code AS quantity_code "
        "FROM procedure p "
        "LEFT JOIN device_type dt ON dt.id = p.device_type_id "
        "LEFT JOIN quantity q ON q.id = dt.quantity_id"
    ),
}

CREATE_VIEW_STATEMENTS: tuple[str, ...] = tuple(_VIEW_SQL[name] for name in APPROVED_VIEWS)
DROP_VIEW_STATEMENTS: tuple[str, ...] = tuple(
    f"DROP VIEW IF EXISTS {name}" for name in APPROVED_VIEWS
)
CREATE_RECORD_VIEW_STATEMENTS: tuple[str, ...] = tuple(
    _RECORD_VIEW_SQL[name] for name in RECORD_VIEWS
)
DROP_RECORD_VIEW_STATEMENTS: tuple[str, ...] = tuple(
    f"DROP VIEW IF EXISTS {name}" for name in RECORD_VIEWS
)
CREATE_QUERY_VIEW_STATEMENTS: tuple[str, ...] = tuple(_QUERY_VIEW_SQL[name] for name in QUERY_VIEWS)
DROP_QUERY_VIEW_STATEMENTS: tuple[str, ...] = tuple(
    f"DROP VIEW IF EXISTS {name}" for name in QUERY_VIEWS
)
CREATE_REFERENCE_VIEW_STATEMENTS: tuple[str, ...] = tuple(
    _REFERENCE_VIEW_SQL[name] for name in REFERENCE_VIEWS
)
DROP_REFERENCE_VIEW_STATEMENTS: tuple[str, ...] = tuple(
    f"DROP VIEW IF EXISTS {name}" for name in REFERENCE_VIEWS
)

# View danh mục NAS: ``c.*`` cộng tên tài liệu; chỉ dòng đã duyệt mới lộ (P3).
_CATALOG_VIEW_SQL: dict[str, str] = {
    name: (
        f"CREATE VIEW {name} AS "
        f"SELECT c.*, d.file_stem AS file_stem, d.display_name AS display_name "
        f"FROM {name[2:]} c "
        "JOIN extraction e ON e.id = c.extraction_id "
        "LEFT JOIN document d ON d.id = c.document_id "
        "WHERE e.status = 'approved'"
    )
    for name in CATALOG_VIEWS
}

CREATE_CATALOG_VIEW_STATEMENTS: tuple[str, ...] = tuple(
    _CATALOG_VIEW_SQL[name] for name in CATALOG_VIEWS
)
DROP_CATALOG_VIEW_STATEMENTS: tuple[str, ...] = tuple(
    f"DROP VIEW IF EXISTS {name}" for name in CATALOG_VIEWS
)


def create_approved_views(connection) -> None:
    """Tạo ba view đã duyệt tri thức trên một connection đang mở (Alembic hoặc test)."""
    for sql in CREATE_VIEW_STATEMENTS:
        connection.execute(text(sql))


def drop_approved_views(connection) -> None:
    """Gỡ ba view đã duyệt tri thức; an toàn khi chúng chưa tồn tại."""
    for sql in DROP_VIEW_STATEMENTS:
        connection.execute(text(sql))


def create_record_views(connection) -> None:
    """Tạo view đã duyệt cho hồ sơ + số liệu đo (gọi ở migration 006/test)."""
    for sql in CREATE_RECORD_VIEW_STATEMENTS:
        connection.execute(text(sql))


def drop_record_views(connection) -> None:
    """Gỡ view đã duyệt cho hồ sơ + số liệu đo; an toàn khi chưa tồn tại."""
    for sql in DROP_RECORD_VIEW_STATEMENTS:
        connection.execute(text(sql))


def create_query_views(connection) -> None:
    """Tạo view bề mặt tra cứu (xuất xứ + dòng dày) — migration 007/test.

    Phải chạy SAU ``create_approved_views``/``create_record_views`` vì
    ``v_record_detail`` tham chiếu ``v_extraction`` và ``v_procedure_fact``.
    """
    for sql in CREATE_QUERY_VIEW_STATEMENTS:
        connection.execute(text(sql))


def drop_query_views(connection) -> None:
    """Gỡ view bề mặt tra cứu; an toàn khi chưa tồn tại."""
    for sql in DROP_QUERY_VIEW_STATEMENTS:
        connection.execute(text(sql))


def recreate_measurement_detail_view(connection, *, with_error_unit: bool = True) -> None:
    """Tạo lại ``v_measurement_detail`` (migration 010 và test SQLite).

    ``with_error_unit=True`` dùng định nghĩa hiện hành có cột ``error_unit_id``/
    ``error_unit_code``; ``False`` là định nghĩa cũ để khôi phục khi downgrade.
    Phải chạy SAU ``create_query_views`` vì view tham chiếu ``v_record_detail``.
    """
    connection.execute(text("DROP VIEW IF EXISTS v_measurement_detail"))
    sql = _MEASUREMENT_DETAIL_SQL if with_error_unit else _MEASUREMENT_DETAIL_SQL_BASE
    connection.execute(text(sql))


def create_reference_views(connection) -> None:
    """Tạo view tham chiếu cho chat số liệu (Sprint 9) — migration 008/test."""
    for sql in CREATE_REFERENCE_VIEW_STATEMENTS:
        connection.execute(text(sql))


def drop_reference_views(connection) -> None:
    """Gỡ view tham chiếu; an toàn khi chưa tồn tại."""
    for sql in DROP_REFERENCE_VIEW_STATEMENTS:
        connection.execute(text(sql))


def create_catalog_views(connection) -> None:
    """Tạo view đã duyệt cho bốn danh mục NAS (Pha D1) — migration 011/test."""
    for sql in CREATE_CATALOG_VIEW_STATEMENTS:
        connection.execute(text(sql))


def drop_catalog_views(connection) -> None:
    """Gỡ view danh mục NAS; an toàn khi chưa tồn tại."""
    for sql in DROP_CATALOG_VIEW_STATEMENTS:
        connection.execute(text(sql))


def create_field_views(connection) -> None:
    """Tạo view trường đầu mục biên bản (Pha R) — migration 012/test."""
    for name in FIELD_VIEWS:
        connection.execute(text(_FIELD_VIEW_SQL[name]))


def drop_field_views(connection) -> None:
    """Gỡ view trường đầu mục biên bản; an toàn khi chưa tồn tại."""
    for name in FIELD_VIEWS:
        connection.execute(text(f"DROP VIEW IF EXISTS {name}"))


def recreate_record_detail_views(connection, *, with_record_fields: bool = True) -> None:
    """Tạo lại ``v_record_detail`` + ``v_measurement_detail`` (migration 012/test).

    ``with_record_fields=True`` dùng định nghĩa hiện hành (phạm vi đo của thiết bị,
    cột ``cells``); ``False`` khôi phục định nghĩa Sprint M khi downgrade.
    ``v_measurement_detail`` tham chiếu ``v_record_detail`` nên gỡ nó trước.
    """
    connection.execute(text("DROP VIEW IF EXISTS v_measurement_detail"))
    connection.execute(text("DROP VIEW IF EXISTS v_record_detail"))
    if with_record_fields:
        connection.execute(text(_RECORD_DETAIL_SQL))
        connection.execute(text(_MEASUREMENT_DETAIL_SQL_CELLS))
    else:
        connection.execute(text(_QUERY_VIEW_SQL["v_record_detail"]))
        connection.execute(text(_MEASUREMENT_DETAIL_SQL))


def create_all_approved_views(connection) -> None:
    """Tạo toàn bộ view đã duyệt (tri thức + dữ liệu đo + tra cứu + tham chiếu)."""
    create_approved_views(connection)
    create_record_views(connection)
    create_reference_views(connection)
    create_query_views(connection)
    create_catalog_views(connection)
    # Sprint M: view hiện hành có thêm đơn vị sai số; tạo lại sau nhóm query.
    recreate_measurement_detail_view(connection)
    # Pha R: trường đầu mục + phạm vi đo của thiết bị + nguyên văn từng ô.
    create_field_views(connection)
    recreate_record_detail_views(connection)


# `FROM`/`JOIN`/`INSERT INTO`/`UPDATE`/`DELETE FROM` theo sau là tên bảng gốc.
_RAW_ACCESS_RE = re.compile(
    r"\b(?:from|join|into|update|table)\s+([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)


def scan_query_source(path: str | Path) -> list[str]:
    """Quét mã nguồn tầng ``query/`` tìm truy cập bảng gốc chưa lọc duyệt.

    Trả danh sách vi phạm dạng ``"file.py:12: procedure_fact"``. Rỗng nghĩa là
    sạch. Chỉ quét file ``.py``; nếu thư mục chưa tồn tại (Sprint 4 chưa mở
    ``query/``) thì trả rỗng.
    """
    root = Path(path)
    if not root.exists():
        return []
    violations: list[str] = []
    files = [root] if root.is_file() else sorted(root.rglob("*.py"))
    for file_path in files:
        if file_path.suffix != ".py":
            continue
        for lineno, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), 1):
            for match in _RAW_ACCESS_RE.finditer(line):
                if match.group(1).lower() in RAW_TABLES:
                    violations.append(f"{file_path}:{lineno}: {match.group(1)}")
    return violations
