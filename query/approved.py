"""Tầng ``query/`` — bề mặt tra cứu chỉ đọc dữ liệu ĐÃ DUYỆT (P3, spec §5.7).

Mọi truy vấn trong thư mục này CHỈ được SELECT từ các view ``v_*`` do
``db/views.py`` định nghĩa. Không nơi nào ở đây được chạm bảng gốc — bộ guard
``db.views.scan_query_source`` quét chính thư mục này và fail nếu thấy tên bảng
gốc, nên vi phạm P3 là lỗi chặn merge chứ không phải lỗi lúc chạy.

Sprint 6 chỉ cần một accessor tối thiểu để (a) có bề mặt tra cứu thật cho guard
bảo vệ và (b) chứng minh dữ liệu ``pending``/``rejected`` không lọt ra. Bề mặt
tra cứu đầy đủ (bảng lọc, phân trang, lịch sử thiết bị) mở ở Sprint 8.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

# SQL chỉ tham chiếu view đã duyệt. Hằng số tách riêng để test khóa được rằng
# không có tên bảng gốc nào xuất hiện trong bề mặt tra cứu.
APPROVED_FACT_SQL = "SELECT * FROM v_procedure_fact"
APPROVED_STANDARD_SQL = "SELECT * FROM v_procedure_standard"
APPROVED_TERM_SQL = "SELECT * FROM v_term"
# Sprint 7: dữ liệu đo — cũng chỉ đọc view đã duyệt.
APPROVED_RECORD_SQL = "SELECT * FROM v_calibration_record"
APPROVED_MEASUREMENT_SQL = "SELECT * FROM v_measurement_point"

# Bảng gốc bị cấm — chỉ dùng để test tự kiểm, không đưa vào câu SQL nào.
FORBIDDEN_TABLE_NAMES: tuple[str, ...] = (
    "extraction",
    "procedure_fact",
    "procedure_standard",
    "term",
    "device",
    "calibration_record",
    "measurement_point",
)


def _where(conditions: list[str], params: dict[str, Any]) -> str:
    return f" WHERE {' AND '.join(conditions)}" if conditions else ""


def _rows(session: Session, base_sql: str, conditions: list[str], params: dict[str, Any]) -> list[dict]:
    sql = base_sql + _where(conditions, params)
    return [dict(row) for row in session.execute(text(sql), params).mappings().all()]


def list_approved_facts(
    session: Session,
    *,
    procedure_id: int | None = None,
    fact_kind: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """Dữ kiện đã duyệt, đọc từ ``v_procedure_fact``; rỗng khi chưa duyệt gì."""
    conditions: list[str] = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if procedure_id is not None:
        conditions.append("procedure_id = :procedure_id")
        params["procedure_id"] = procedure_id
    if fact_kind is not None:
        conditions.append("fact_kind = :fact_kind")
        params["fact_kind"] = fact_kind
    sql = APPROVED_FACT_SQL + _where(conditions, params) + " ORDER BY id LIMIT :limit OFFSET :offset"
    return [dict(row) for row in session.execute(text(sql), params).mappings().all()]


def list_approved_standards(
    session: Session,
    *,
    procedure_id: int | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """Bảng 2 Phương tiện kiểm định đã duyệt, đọc từ ``v_procedure_standard``."""
    conditions: list[str] = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if procedure_id is not None:
        conditions.append("procedure_id = :procedure_id")
        params["procedure_id"] = procedure_id
    sql = (
        APPROVED_STANDARD_SQL
        + _where(conditions, params)
        + " ORDER BY id LIMIT :limit OFFSET :offset"
    )
    return [dict(row) for row in session.execute(text(sql), params).mappings().all()]


def list_approved_terms(
    session: Session,
    *,
    procedure_id: int | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """Thuật ngữ đã duyệt, đọc từ ``v_term``."""
    conditions: list[str] = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if procedure_id is not None:
        conditions.append("procedure_id = :procedure_id")
        params["procedure_id"] = procedure_id
    sql = APPROVED_TERM_SQL + _where(conditions, params) + " ORDER BY id LIMIT :limit OFFSET :offset"
    return [dict(row) for row in session.execute(text(sql), params).mappings().all()]


def list_approved_records(
    session: Session,
    *,
    procedure_id: int | None = None,
    device_id: int | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """Hồ sơ kiểm định đã duyệt, đọc từ ``v_calibration_record`` (P3)."""
    conditions: list[str] = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if procedure_id is not None:
        conditions.append("procedure_id = :procedure_id")
        params["procedure_id"] = procedure_id
    if device_id is not None:
        conditions.append("device_id = :device_id")
        params["device_id"] = device_id
    sql = (
        APPROVED_RECORD_SQL
        + _where(conditions, params)
        + " ORDER BY id LIMIT :limit OFFSET :offset"
    )
    return [dict(row) for row in session.execute(text(sql), params).mappings().all()]


def list_approved_measurements(
    session: Session,
    *,
    record_id: int | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[dict]:
    """Số liệu đo đã duyệt, đọc từ ``v_measurement_point`` (P3)."""
    conditions: list[str] = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if record_id is not None:
        conditions.append("record_id = :record_id")
        params["record_id"] = record_id
    sql = (
        APPROVED_MEASUREMENT_SQL
        + _where(conditions, params)
        + " ORDER BY id LIMIT :limit OFFSET :offset"
    )
    return [dict(row) for row in session.execute(text(sql), params).mappings().all()]


def approved_counts(session: Session) -> dict[str, int]:
    """Số dòng tri thức đã duyệt — luôn đọc qua view, không bao giờ bảng gốc."""
    return {
        "facts": session.execute(
            text("SELECT COUNT(*) FROM v_procedure_fact")
        ).scalar_one(),
        "standards": session.execute(
            text("SELECT COUNT(*) FROM v_procedure_standard")
        ).scalar_one(),
        "terms": session.execute(text("SELECT COUNT(*) FROM v_term")).scalar_one(),
    }


def approved_record_counts(session: Session) -> dict[str, int]:
    """Số hồ sơ/số liệu đo đã duyệt — đọc ``v_calibration_record``/``v_measurement_point``."""
    return {
        "records": session.execute(
            text("SELECT COUNT(*) FROM v_calibration_record")
        ).scalar_one(),
        "measurements": session.execute(
            text("SELECT COUNT(*) FROM v_measurement_point")
        ).scalar_one(),
    }
