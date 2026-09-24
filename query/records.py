"""Bề mặt tra cứu dữ liệu có cấu trúc — chỉ đọc view ĐÃ DUYỆT (P3, spec §9 S8).

Cung cấp bảng lọc/phân trang/sắp xếp cho tab "Dữ liệu", lịch sử thiết bị theo số
hiệu (dòng thời gian + diễn biến sai số), và tham chiếu xuất xứ cho từng ô số (P1).

Ràng buộc P3 được cài ở tầng cơ sở dữ liệu: mọi câu SQL ở đây chỉ chạm các view
``v_record_detail``/``v_measurement_detail``/``v_extraction``/``v_procedure_fact``/
``v_unit``. Bộ guard ``db.views.scan_query_source`` quét chính thư mục này và fail
nếu bắt gặp tên bảng gốc, nên vi phạm P3 là lỗi chặn merge.

P2: không có phép tính nào trên số liệu nguồn ở đây — chỉ đọc và trình bày. Giá
trị ``range_*`` là dữ kiện QTKĐ đã chuẩn hóa sẵn ở tầng trích xuất.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

# Cột được phép sắp xếp — whitelist để không bao giờ nối tham số vào SQL.
RECORD_SORTS: dict[str, str] = {
    "calibrated_at": "r.calibrated_at",
    "expires_at": "r.expires_at",
    "serial_no": "r.serial_no",
    "procedure_number": "r.procedure_number",
    "verdict": "r.verdict",
    "device_type_name": "r.device_type_name",
    "id": "r.id",
}
DEFAULT_SORT = "calibrated_at"
DEFAULT_ORDER = "desc"
LIST_LIMIT_MAX = 200
EXPORT_LIMIT_MAX = 20000

VERDICT_LABELS: dict[str, str] = {"dat": "Đạt", "khong_dat": "Không đạt"}
MODE_LABELS: dict[str, str] = {
    "ban_dau": "Ban đầu",
    "dinh_ky": "Định kỳ",
    "sau_sua_chua": "Sau sửa chữa",
}

# Định danh thiết bị dùng chung cho nhóm + lịch sử.
_DEVICE_GROUP_COLS = (
    "r.device_id",
    "r.serial_no",
    "r.model_code",
    "r.manufacturer",
    "r.owner_org",
    "r.device_type_id",
    "r.device_type_name",
    "r.quantity_id",
    "r.quantity_name",
)


class QueryError(ValueError):
    """Tham số tra cứu không hợp lệ."""


class NotFoundError(QueryError):
    """Không tìm thấy bản ghi đã duyệt."""


def _iso(value: Any) -> str | None:
    """Chuẩn hóa ngày giờ về ISO cho JSON (SQLite trả chuỗi, Postgres trả datetime)."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).isoformat()
        except ValueError:
            return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _parse_dt(value: Any, *, end_of_day: bool = False) -> datetime | None:
    """Nhận ISO date/datetime; ngày trần của ``date_to`` mở rộng tới cuối ngày."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.max if end_of_day else time.min)
    text_value = str(value).strip()
    if not text_value:
        return None
    try:
        parsed = datetime.fromisoformat(text_value)
    except ValueError as exc:  # pragma: no cover - bảo vệ tham số bẩn
        raise QueryError(f"Ngày không hợp lệ: {value!r}") from exc
    if end_of_day and len(text_value) <= 10:
        parsed = datetime.combine(parsed.date(), time.max)
    return parsed


def _unit_factor(session: Session, code: str | None) -> tuple[float, float]:
    """Hệ số quy đổi của một đơn vị (đọc ``v_unit``); mặc định SI = 1/0."""
    if not code:
        return 1.0, 0.0
    row = (
        session.execute(
            text("SELECT factor_to_si, offset_to_si FROM v_unit WHERE code = :code"),
            {"code": code},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise QueryError(f"Không nhận diện được đơn vị: {code!r}")
    return float(row["factor_to_si"]), float(row["offset_to_si"])


def _record_conditions(
    session: Session,
    *,
    device_type_id: int | None = None,
    quantity_id: int | None = None,
    procedure_id: int | None = None,
    verdict: str | None = None,
    date_from: Any = None,
    date_to: Any = None,
    range_min: float | None = None,
    range_max: float | None = None,
    range_unit: str | None = None,
    accuracy: str | None = None,
    serial: str | None = None,
    search: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Dựng mệnh đề WHERE cho bảng hồ sơ; tham số luôn được bind, không nối chuỗi."""
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if device_type_id is not None:
        conditions.append("r.device_type_id = :device_type_id")
        params["device_type_id"] = device_type_id
    if quantity_id is not None:
        conditions.append("r.quantity_id = :quantity_id")
        params["quantity_id"] = quantity_id
    if procedure_id is not None:
        conditions.append("r.procedure_id = :procedure_id")
        params["procedure_id"] = procedure_id
    if verdict:
        conditions.append("r.verdict = :verdict")
        params["verdict"] = verdict

    parsed_from = _parse_dt(date_from)
    if parsed_from is not None:
        conditions.append("r.calibrated_at >= :date_from")
        params["date_from"] = parsed_from
    parsed_to = _parse_dt(date_to, end_of_day=True)
    if parsed_to is not None:
        conditions.append("r.calibrated_at <= :date_to")
        params["date_to"] = parsed_to

    if range_min is not None or range_max is not None:
        factor, offset = _unit_factor(session, range_unit)
        if range_min is not None:
            conditions.append("r.range_min IS NOT NULL AND r.range_min <= :range_min_si")
            params["range_min_si"] = factor * range_min + offset
        if range_max is not None:
            conditions.append("r.range_max IS NOT NULL AND r.range_max >= :range_max_si")
            params["range_max_si"] = factor * range_max + offset

    if accuracy:
        conditions.append("r.accuracy_text LIKE :accuracy")
        params["accuracy"] = f"%{accuracy.strip()}%"
    if serial:
        conditions.append("LOWER(COALESCE(r.serial_no, '')) = :serial")
        params["serial"] = serial.strip().lower()
    if search:
        conditions.append(
            "(LOWER(COALESCE(r.serial_no, '')) LIKE :search "
            "OR LOWER(COALESCE(r.model_code, '')) LIKE :search "
            "OR LOWER(COALESCE(r.procedure_number, '')) LIKE :search "
            "OR LOWER(COALESCE(r.cert_no, '')) LIKE :search "
            "OR LOWER(COALESCE(r.lab_name, '')) LIKE :search)"
        )
        params["search"] = f"%{search.strip().lower()}%"

    return conditions, params


def _where(conditions: list[str]) -> str:
    return f" WHERE {' AND '.join(conditions)}" if conditions else ""


def _record_cells(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Tham chiếu xuất xứ cho từng ô số của một hồ sơ (P1).

    Mỗi ô số trả ``{field, kind, id}``; client bấm vào ô sẽ gọi
    ``GET /api/data/provenance`` với tham chiếu tương ứng để mở đúng đoạn nguồn.
    """
    cells: list[dict[str, Any]] = []
    record_id = record.get("id")
    if record.get("calibrated_at") is not None:
        cells.append({"field": "calibrated_at", "kind": "record", "id": record_id})
    if record.get("expires_at") is not None:
        cell: dict[str, Any] = {
            "field": "expires_at",
            "kind": "record",
            "id": record_id,
        }
        if record.get("expires_from_fact_id") is not None:
            cell["fact_id"] = record["expires_from_fact_id"]
        cells.append(cell)
    for field in ("env_temp_c", "env_humidity_pct"):
        if record.get(field) is not None:
            cells.append({"field": field, "kind": "record", "id": record_id})
    if record.get("range_fact_id") is not None:
        for field in ("range_min", "range_max"):
            if record.get(field) is not None:
                cells.append({"field": field, "kind": "fact", "id": record["range_fact_id"]})
    if record.get("accuracy_fact_id") is not None and record.get("accuracy_text"):
        cells.append(
            {
                "field": "accuracy_text",
                "kind": "fact",
                "id": record["accuracy_fact_id"],
            }
        )
    if record.get("measurement_count"):
        cells.append({"field": "measurement_count", "kind": "record", "id": record_id})
    return cells


def serialize_record(row: Any) -> dict[str, Any]:
    """Chuẩn hóa một dòng ``v_record_detail`` cho JSON, kèm tham chiếu xuất xứ."""
    record = _row_to_dict(row)
    for key in ("calibrated_at", "expires_at", "created_at"):
        record[key] = _iso(record.get(key))
    record["verdict_label"] = VERDICT_LABELS.get(record.get("verdict"), record.get("verdict"))
    record["mode_label"] = MODE_LABELS.get(record.get("mode"), record.get("mode"))
    record["within_limit"] = None  # cấp hồ sơ không có cờ này
    record["provenance"] = _record_cells(record)
    return record


def _measurement_cells(point: dict[str, Any]) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for field, column in (
        ("nominal", "nominal_value"),
        ("measured", "measured_value"),
        ("error", "error_value"),
        ("limit", "limit_value"),
    ):
        if point.get(column) is not None or point.get(f"{field}_text"):
            cells.append({"field": field, "kind": "measurement", "id": point.get("id")})
    return cells


def serialize_measurement(row: Any) -> dict[str, Any]:
    point = _row_to_dict(row)
    point["calibrated_at"] = _iso(point.get("calibrated_at"))
    point["within_limit"] = (
        None if point.get("within_limit") is None else bool(point["within_limit"])
    )
    point["provenance"] = _measurement_cells(point)
    return point


def _query_records(
    session: Session,
    *,
    cap: int,
    device_type_id: int | None = None,
    quantity_id: int | None = None,
    procedure_id: int | None = None,
    verdict: str | None = None,
    date_from: Any = None,
    date_to: Any = None,
    range_min: float | None = None,
    range_max: float | None = None,
    range_unit: str | None = None,
    accuracy: str | None = None,
    serial: str | None = None,
    search: str | None = None,
    sort: str = DEFAULT_SORT,
    order: str = DEFAULT_ORDER,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Lõi truy vấn hồ sơ dùng chung cho bảng lọc và xuất Excel."""
    conditions, params = _record_conditions(
        session,
        device_type_id=device_type_id,
        quantity_id=quantity_id,
        procedure_id=procedure_id,
        verdict=verdict,
        date_from=date_from,
        date_to=date_to,
        range_min=range_min,
        range_max=range_max,
        range_unit=range_unit,
        accuracy=accuracy,
        serial=serial,
        search=search,
    )
    where = _where(conditions)

    total = session.execute(
        text("SELECT COUNT(*) FROM v_record_detail r" + where), params
    ).scalar_one()

    column = RECORD_SORTS.get(sort, RECORD_SORTS[DEFAULT_SORT])
    direction = "ASC" if str(order).lower() == "asc" else "DESC"
    safe_limit = max(1, min(int(limit), cap))
    safe_offset = max(0, int(offset))

    sql = (
        "SELECT r.*, mc.measurement_count AS measurement_count "
        "FROM v_record_detail r "
        "LEFT JOIN ("
        "SELECT record_id, COUNT(*) AS measurement_count "
        "FROM v_measurement_detail GROUP BY record_id"
        ") mc ON mc.record_id = r.id"
        + where
        + f" ORDER BY {column} {direction}, r.id {direction} LIMIT :limit OFFSET :offset"
    )
    rows = (
        session.execute(text(sql), {**params, "limit": safe_limit, "offset": safe_offset})
        .mappings()
        .all()
    )
    return [serialize_record(row) for row in rows], int(total)


def list_records(
    session: Session,
    *,
    device_type_id: int | None = None,
    quantity_id: int | None = None,
    procedure_id: int | None = None,
    verdict: str | None = None,
    date_from: Any = None,
    date_to: Any = None,
    range_min: float | None = None,
    range_max: float | None = None,
    range_unit: str | None = None,
    accuracy: str | None = None,
    serial: str | None = None,
    search: str | None = None,
    sort: str = DEFAULT_SORT,
    order: str = DEFAULT_ORDER,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Trang hồ sơ đã duyệt + tổng số dòng khớp bộ lọc (P3)."""
    return _query_records(
        session,
        cap=LIST_LIMIT_MAX,
        device_type_id=device_type_id,
        quantity_id=quantity_id,
        procedure_id=procedure_id,
        verdict=verdict,
        date_from=date_from,
        date_to=date_to,
        range_min=range_min,
        range_max=range_max,
        range_unit=range_unit,
        accuracy=accuracy,
        serial=serial,
        search=search,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )


def all_records(
    session: Session,
    *,
    limit: int = EXPORT_LIMIT_MAX,
    **filters: Any,
) -> list[dict[str, Any]]:
    """Toàn bộ hồ sơ khớp bộ lọc cho xuất Excel (cùng ngữ nghĩa với bảng lọc)."""
    rows, _ = _query_records(session, cap=EXPORT_LIMIT_MAX, limit=limit, offset=0, **filters)
    return rows


def get_record(session: Session, record_id: int) -> dict[str, Any]:
    """Một hồ sơ đã duyệt kèm toàn bộ điểm đo và tham chiếu xuất xứ từng ô."""
    row = (
        session.execute(text("SELECT * FROM v_record_detail WHERE id = :id"), {"id": record_id})
        .mappings()
        .first()
    )
    if row is None:
        raise NotFoundError(f"Không tìm thấy hồ sơ đã duyệt {record_id}.")
    record = serialize_record(row)
    points = (
        session.execute(
            text(
                "SELECT * FROM v_measurement_detail WHERE record_id = :id "
                "ORDER BY COALESCE(ord, 999999), id"
            ),
            {"id": record_id},
        )
        .mappings()
        .all()
    )
    record["measurements"] = [serialize_measurement(point) for point in points]
    record["measurement_count"] = len(record["measurements"])
    return record


def list_devices(
    session: Session,
    *,
    q: str | None = None,
    device_type_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Thiết bị có ít nhất một hồ sơ đã duyệt, kèm số lần kiểm định (P3)."""
    conditions: list[str] = []
    params: dict[str, Any] = {}
    if q:
        conditions.append(
            "(LOWER(COALESCE(r.serial_no, '')) LIKE :q "
            "OR LOWER(COALESCE(r.model_code, '')) LIKE :q "
            "OR LOWER(COALESCE(r.manufacturer, '')) LIKE :q)"
        )
        params["q"] = f"%{q.strip().lower()}%"
    if device_type_id is not None:
        conditions.append("r.device_type_id = :device_type_id")
        params["device_type_id"] = device_type_id
    where = _where(conditions)

    total = session.execute(
        text("SELECT COUNT(DISTINCT r.device_id) FROM v_record_detail r" + where),
        params,
    ).scalar_one()

    sql = (
        "SELECT r.device_id AS id, r.serial_no AS serial_no, r.model_code AS model_code, "
        "r.manufacturer AS manufacturer, r.owner_org AS owner_org, "
        "r.device_type_id AS device_type_id, r.device_type_name AS device_type_name, "
        "r.quantity_id AS quantity_id, r.quantity_name AS quantity_name, "
        "COUNT(*) AS record_count, MAX(r.calibrated_at) AS last_calibrated_at, "
        "SUM(CASE WHEN r.verdict = 'dat' THEN 1 ELSE 0 END) AS dat_count "
        "FROM v_record_detail r"
        + where
        + " GROUP BY "
        + ", ".join(_DEVICE_GROUP_COLS)
        + " ORDER BY r.serial_no IS NULL, r.serial_no, r.device_id LIMIT :limit OFFSET :offset"
    )
    safe_limit = max(1, min(int(limit), LIST_LIMIT_MAX))
    rows = (
        session.execute(text(sql), {**params, "limit": safe_limit, "offset": max(0, int(offset))})
        .mappings()
        .all()
    )
    devices = []
    for row in rows:
        device = _row_to_dict(row)
        device["last_calibrated_at"] = _iso(device.get("last_calibrated_at"))
        devices.append(device)
    return devices, int(total)


def _build_trend(points: list[Any]) -> list[dict[str, Any]]:
    """Gom điểm đo theo mốc (``step_code``/nhãn) để vẽ diễn biến sai số."""
    buckets: dict[str, dict[str, Any]] = {}
    for row in points:
        key = row["step_code"] or row["label"] or "(không có mốc)"
        bucket = buckets.setdefault(
            key,
            {
                "key": key,
                "step_code": row["step_code"],
                "label": row["label"],
                "unit_code": row["unit_code"],
                "unit_name": row["unit_name"],
                "points": [],
            },
        )
        if bucket["unit_code"] is None:
            bucket["unit_code"] = row["unit_code"]
            bucket["unit_name"] = row["unit_name"]
        point = serialize_measurement(row)
        point["provenance"] = [
            {"field": cell["field"], "kind": "measurement", "id": row["id"]}
            for cell in point["provenance"]
        ]
        bucket["points"].append(
            {
                "record_id": row["record_id"],
                "point_id": row["id"],
                "calibrated_at": _iso(row["calibrated_at"]),
                "verdict": row["verdict"],
                "verdict_label": VERDICT_LABELS.get(row["verdict"], row["verdict"]),
                "error_value": row["error_value"],
                "error_text": row["error_text"],
                "limit_value": row["limit_value"],
                "limit_text": row["limit_text"],
                "within_limit": (
                    None if row["within_limit"] is None else bool(row["within_limit"])
                ),
                "unit_code": row["unit_code"],
                "provenance": [
                    {"field": "error", "kind": "measurement", "id": row["id"]},
                    {"field": "limit", "kind": "measurement", "id": row["id"]},
                ],
            }
        )
    return sorted(buckets.values(), key=lambda item: item["key"] or "")


def device_history(
    session: Session,
    *,
    device_id: int | None = None,
    serial: str | None = None,
) -> dict[str, Any]:
    """Trang thiết bị: định danh, dòng thời gian kiểm định, diễn biến sai số (P3)."""
    if device_id is None:
        if not serial or not serial.strip():
            raise QueryError("Cần device_id hoặc số hiệu thiết bị.")
        found = session.execute(
            text(
                "SELECT device_id FROM v_record_detail "
                "WHERE LOWER(COALESCE(serial_no, '')) = :serial "
                "ORDER BY calibrated_at DESC LIMIT 1"
            ),
            {"serial": serial.strip().lower()},
        ).first()
        if found is None:
            raise NotFoundError(f"Không tìm thấy thiết bị có số hiệu {serial!r}.")
        device_id = found[0]

    rows = (
        session.execute(
            text("SELECT * FROM v_record_detail WHERE device_id = :id ORDER BY calibrated_at, id"),
            {"id": device_id},
        )
        .mappings()
        .all()
    )
    if not rows:
        raise NotFoundError(f"Không tìm thấy thiết bị đã duyệt {device_id}.")

    device = {
        "id": rows[0]["device_id"],
        "serial_no": rows[0]["serial_no"],
        "model_code": rows[0]["model_code"],
        "manufacturer": rows[0]["manufacturer"],
        "owner_org": rows[0]["owner_org"],
        "device_type_id": rows[0]["device_type_id"],
        "device_type_name": rows[0]["device_type_name"],
        "quantity_id": rows[0]["quantity_id"],
        "quantity_name": rows[0]["quantity_name"],
        "record_count": len(rows),
    }

    records = []
    for row in rows:
        record = serialize_record(row)
        records.append(
            {
                "id": record["id"],
                "calibrated_at": record["calibrated_at"],
                "expires_at": record["expires_at"],
                "verdict": record["verdict"],
                "verdict_label": record["verdict_label"],
                "mode": record["mode"],
                "mode_label": record["mode_label"],
                "procedure_number": record["procedure_number"],
                "procedure_title": record["procedure_title"],
                "cert_no": record["cert_no"],
                "document_id": record["document_id"],
                "file_stem": record["file_stem"],
                "extraction_id": record["extraction_id"],
                "measurement_count": record.get("measurement_count"),
                "provenance": record["provenance"],
            }
        )

    points = (
        session.execute(
            text(
                "SELECT * FROM v_measurement_detail WHERE device_id = :id "
                "ORDER BY calibrated_at, COALESCE(ord, 999999), id"
            ),
            {"id": device_id},
        )
        .mappings()
        .all()
    )
    return {
        "device": device,
        "records": records,
        "trend": _build_trend(points),
        "record_count": len(records),
    }


def _distinct_options(
    session: Session,
    value_expr: str,
    label_expr: str,
    *,
    extra: str | None = None,
) -> list[dict[str, Any]]:
    select_extra = f", {extra}" if extra else ""
    sql = (
        f"SELECT DISTINCT {value_expr} AS value, {label_expr} AS label{select_extra} "
        f"FROM v_record_detail r WHERE {value_expr} IS NOT NULL ORDER BY label"
    )
    return [_row_to_dict(row) for row in session.execute(text(sql)).mappings().all()]


def filter_options(session: Session) -> dict[str, Any]:
    """Giá trị bộ lọc suy từ dữ liệu ĐÃ DUYỆT (không lộ mục chưa duyệt)."""
    return {
        "device_types": _distinct_options(session, "r.device_type_id", "r.device_type_name"),
        "quantities": _distinct_options(session, "r.quantity_id", "r.quantity_name"),
        "procedures": _distinct_options(
            session, "r.procedure_id", "r.procedure_number", extra="r.procedure_title"
        ),
        "verdicts": [
            {"value": value, "label": VERDICT_LABELS.get(value, value)}
            for value in session.execute(
                text(
                    "SELECT DISTINCT r.verdict AS value FROM v_record_detail r "
                    "WHERE r.verdict IS NOT NULL ORDER BY r.verdict"
                )
            ).scalars()
        ],
        "sorts": list(RECORD_SORTS.keys()),
    }
