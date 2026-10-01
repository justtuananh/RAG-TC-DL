"""Đọc view biên bản đã duyệt + dựng ô bảng kèm xuất xứ (dùng chung cho Pha R).

Dùng bởi ``query.record_query`` (``record_lookup``) và ``query.record_summary``
(``records_summary``). Mọi câu SQL do người viết, tham số luôn được bind, chỉ đọc view
đã duyệt (``v_record_detail``, ``v_record_field``, ``v_measurement_detail``) — P3.
Mỗi ô mang tham chiếu xuất xứ (P1); giá trị hiển thị NGUYÊN VĂN (P2).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from query.record_fields import VERDICT_KEY
from query.record_intents import RecordLookupParams
from query.records import VERDICT_LABELS
from query.table_model import Cell, Column, _date_text

# So số thực đã phân tích (điểm danh nghĩa được hỏi, đồng hạng cực trị): tương đối 1e-9.
VALUE_TOLERANCE = 1e-9

IDENTITY_COLUMNS: tuple[Column, ...] = (
    Column("cert_no", "Số biên bản"),
    Column("calibrated_at", "Ngày kiểm định"),
    Column("serial_no", "Số hiệu"),
    Column("model_code", "Ký hiệu"),
)


# ── Đọc view ──────────────────────────────────────────────────────────────────


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min)
    return start, start + timedelta(days=1)


def select_records(session: Session, conditions: list[str], params: dict[str, Any]) -> list[dict]:
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    statement = text(f"SELECT * FROM v_record_detail r{where} ORDER BY r.calibrated_at, r.id")
    # Tham số danh sách (``IN :ids``) phải bind dạng expanding trên cả SQLite lẫn PostgreSQL.
    expanding = [
        bindparam(key, expanding=True) for key, value in params.items() if isinstance(value, list)
    ]
    if expanding:
        statement = statement.bindparams(*expanding)
    return [dict(row) for row in session.execute(statement, params).mappings()]


def find_records(session: Session, params: RecordLookupParams) -> list[dict]:
    """Biên bản đã duyệt khớp MỌI bộ lọc đã cho (số hiệu, số biên bản, ký hiệu, ngày)."""
    conditions: list[str] = []
    values: dict[str, Any] = {}
    if params.serial:
        conditions.append("LOWER(COALESCE(r.serial_no, '')) = :serial")
        values["serial"] = params.serial.strip().casefold()
    if params.cert_no:
        conditions.append("COALESCE(r.cert_no, '') = :cert_no")
        values["cert_no"] = params.cert_no.strip()
    if params.model_code:
        conditions.append("LOWER(COALESCE(r.model_code, '')) = :model_code")
        values["model_code"] = params.model_code.strip().casefold()
    if params.calibrated_on:
        start, end = day_bounds(params.calibrated_on)
        conditions.append("r.calibrated_at >= :day_start AND r.calibrated_at < :day_end")
        values.update(day_start=start, day_end=end)
    return select_records(session, conditions, values)


def fields_by_record(session: Session, record_ids: list[int]) -> dict[int, dict[str, dict]]:
    if not record_ids:
        return {}
    statement = text(
        "SELECT * FROM v_record_field WHERE record_id IN :ids ORDER BY record_id, ord"
    ).bindparams(bindparam("ids", expanding=True))
    result: dict[int, dict[str, dict]] = {}
    for row in session.execute(statement, {"ids": record_ids}).mappings():
        result.setdefault(int(row["record_id"]), {}).setdefault(row["field_key"], dict(row))
    return result


def load_points(
    session: Session, record_ids: list[int], steps: list[str] | None = None
) -> list[dict]:
    if not record_ids:
        return []
    sql = "SELECT * FROM v_measurement_detail WHERE record_id IN :ids"
    params: dict[str, Any] = {"ids": record_ids}
    binds = [bindparam("ids", expanding=True)]
    if steps:
        sql += " AND step_code IN :steps"
        params["steps"] = steps
        binds.append(bindparam("steps", expanding=True))
    sql += " ORDER BY record_id, step_code, ord, id"
    return [dict(row) for row in session.execute(text(sql).bindparams(*binds), params).mappings()]


# ── Ô bảng ────────────────────────────────────────────────────────────────────


def record_cell(record: dict, value: Any, field: str, *, numeric: bool = False) -> Cell:
    empty = value in (None, "")
    return Cell(
        text="—" if empty else str(value),
        numeric=numeric and not empty,
        provenance=None if empty else {"kind": "record", "id": record["id"], "field": field},
        device_id=record.get("device_id"),
        record_id=record.get("id"),
    )


def field_cell(record: dict, row: dict | None) -> Cell:
    if row is None:
        return Cell(text="—", record_id=record.get("id"), device_id=record.get("device_id"))
    has_number = row.get("value_min") is not None or row.get("value_max") is not None
    return record_cell(record, row.get("value_text"), row["field_key"], numeric=has_number)


def identity_cells(record: dict) -> dict[str, Cell]:
    return {
        "cert_no": record_cell(record, record.get("cert_no"), "so"),
        "calibrated_at": record_cell(
            record, _date_text(record.get("calibrated_at")), "ngay_kiem_dinh"
        ),
        "serial_no": record_cell(record, record.get("serial_no"), "so_hieu"),
        "model_code": record_cell(record, record.get("model_code"), "ky_hieu"),
    }


def verdict_cell(record: dict, fields: dict[str, dict]) -> Cell:
    """Kết luận nguyên văn biên bản; thiếu thì nhãn chuẩn hóa từ sổ cái."""
    row = fields.get(VERDICT_KEY)
    if row is not None:
        return field_cell(record, row)
    label = VERDICT_LABELS.get(record.get("verdict"), record.get("verdict"))
    return record_cell(record, label, "verdict")


def point_cell(point: dict, value: str | None) -> Cell:
    empty = value in (None, "")
    return Cell(
        text="—" if empty else str(value),
        numeric=not empty and any(char.isdigit() for char in str(value)),
        provenance=None if empty else {"kind": "measurement", "id": point["id"], "field": "row"},
        device_id=point.get("device_id"),
        record_id=point.get("record_id"),
    )
