"""Truy vấn biên bản có cấu trúc cho chat số liệu (Pha R, spec §8).

Hai resolver cho ``record_lookup`` và ``records_summary``. Mọi câu SQL do người
viết, tham số luôn được bind, chỉ đọc view đã duyệt (``v_record_detail``,
``v_record_field``, ``v_measurement_detail``, ``v_unit``) — P3.

Bất biến:
- P1: mỗi ô mang tham chiếu xuất xứ (``record`` + khóa trường, hoặc ``measurement``).
- P2: giá trị luôn hiển thị NGUYÊN VĂN biên bản. Cực trị chỉ SẮP XẾP theo số đã
  phân tích (quy đổi cùng SI khi đơn vị nhận diện được), không hiển thị số tính
  ra. Đếm là đếm hồ sơ/thiết bị, không phải phép tính trên số liệu đo.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from query.record_fields import (
    IDENTITY_KEYS,
    VERDICT_KEY,
    FieldCatalog,
    content_tokens,
    field_catalog,
    load_cells,
)
from query.record_intents import RecordLookupParams, RecordsSummaryParams
from query.records import VERDICT_LABELS
from query.table_model import (
    LEDGER_NOTE,
    Cell,
    Column,
    DataPayload,
    DataTable,
    _citations_for_tables,
    _date_text,
    empty_payload,
    make_payload,
)

MAX_CARDS = 3
MAX_LIST_ROWS = 50
RANK_ROWS = 5
_NOMINAL_TOLERANCE = 1e-9
_MIN_REASON_OVERLAP = 3

_IDENTITY_COLUMNS: tuple[Column, ...] = (
    Column("cert_no", "Số biên bản"),
    Column("calibrated_at", "Ngày kiểm định"),
    Column("serial_no", "Số hiệu"),
    Column("model_code", "Ký hiệu"),
)
_FALLBACK_POINT_COLUMNS = ("Thông số", "Danh nghĩa", "Giá trị xác định", "Giá trị cho phép")


# ── Đọc view ──────────────────────────────────────────────────────────────────


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min)
    return start, start + timedelta(days=1)


def _select_records(session: Session, conditions: list[str], params: dict[str, Any]) -> list[dict]:
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = session.execute(
        text(f"SELECT * FROM v_record_detail r{where} ORDER BY r.calibrated_at, r.id"), params
    ).mappings()
    return [dict(row) for row in rows]


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
        start, end = _day_bounds(params.calibrated_on)
        conditions.append("r.calibrated_at >= :day_start AND r.calibrated_at < :day_end")
        values.update(day_start=start, day_end=end)
    return _select_records(session, conditions, values)


def _fields_by_record(session: Session, record_ids: list[int]) -> dict[int, dict[str, dict]]:
    if not record_ids:
        return {}
    statement = text(
        "SELECT * FROM v_record_field WHERE record_id IN :ids ORDER BY record_id, ord"
    ).bindparams(bindparam("ids", expanding=True))
    result: dict[int, dict[str, dict]] = {}
    for row in session.execute(statement, {"ids": record_ids}).mappings():
        result.setdefault(int(row["record_id"]), {}).setdefault(row["field_key"], dict(row))
    return result


def _points(session: Session, record_ids: list[int], steps: list[str] | None = None) -> list[dict]:
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


def _record_cell(record: dict, value: Any, field: str, *, numeric: bool = False) -> Cell:
    empty = value in (None, "")
    return Cell(
        text="—" if empty else str(value),
        numeric=numeric and not empty,
        provenance=None if empty else {"kind": "record", "id": record["id"], "field": field},
        device_id=record.get("device_id"),
        record_id=record.get("id"),
    )


def _field_cell(record: dict, row: dict | None) -> Cell:
    if row is None:
        return Cell(text="—", record_id=record.get("id"), device_id=record.get("device_id"))
    has_number = row.get("value_min") is not None or row.get("value_max") is not None
    return _record_cell(record, row.get("value_text"), row["field_key"], numeric=has_number)


def _identity_cells(record: dict) -> dict[str, Cell]:
    return {
        "cert_no": _record_cell(record, record.get("cert_no"), "so"),
        "calibrated_at": _record_cell(
            record, _date_text(record.get("calibrated_at")), "ngay_kiem_dinh"
        ),
        "serial_no": _record_cell(record, record.get("serial_no"), "so_hieu"),
        "model_code": _record_cell(record, record.get("model_code"), "ky_hieu"),
    }


def _verdict_cell(record: dict, fields: dict[str, dict]) -> Cell:
    """Kết luận nguyên văn biên bản; thiếu thì nhãn chuẩn hóa từ sổ cái."""
    row = fields.get(VERDICT_KEY)
    if row is not None:
        return _field_cell(record, row)
    label = VERDICT_LABELS.get(record.get("verdict"), record.get("verdict"))
    return _record_cell(record, label, "verdict")


def _point_cell(point: dict, value: str | None) -> Cell:
    empty = value in (None, "")
    return Cell(
        text="—" if empty else str(value),
        numeric=not empty and any(char.isdigit() for char in str(value)),
        provenance=None if empty else {"kind": "measurement", "id": point["id"], "field": "row"},
        device_id=point.get("device_id"),
        record_id=point.get("record_id"),
    )


def _cert(record: dict) -> str:
    return str(record.get("cert_no") or record["id"])


# ── record_lookup ─────────────────────────────────────────────────────────────


def _fields_table(
    records: list[dict], fields: dict[int, dict[str, dict]], keys: list[str], catalog: FieldCatalog
) -> DataTable:
    columns = [*_IDENTITY_COLUMNS]
    columns += [Column(key, catalog.field_label(key)) for key in keys if key != VERDICT_KEY]
    if VERDICT_KEY in keys:
        columns.append(Column(VERDICT_KEY, "Kết luận"))
    rows = []
    for record in records:
        own = fields.get(record["id"], {})
        row = _identity_cells(record)
        for key in keys:
            if key == VERDICT_KEY:
                row[key] = _verdict_cell(record, own)
            else:
                row[key] = _field_cell(record, own.get(key))
        rows.append(row)
    return DataTable(
        title="Thông tin biên bản",
        columns=columns,
        rows=rows,
        total=len(rows),
        note="Giá trị nguyên văn biên bản đã duyệt; bấm vào ô để mở dòng nguồn.",
    )


def _record_cards(records: list[dict], fields: dict[int, dict[str, dict]]) -> list[DataTable]:
    tables = []
    for record in records[:MAX_CARDS]:
        rows = [
            {"label": Cell(text=row["label"]), "value": _field_cell(record, row)}
            for row in fields.get(record["id"], {}).values()
        ]
        tables.append(
            DataTable(
                title=f"Biên bản {_cert(record)} · số hiệu {record.get('serial_no') or '—'}",
                columns=[Column("label", "Trường"), Column("value", "Giá trị")],
                rows=rows,
                total=len(rows),
            )
        )
    return tables


def _cell_map(point: dict) -> dict[str, str]:
    return {
        (str(cell.get("column") or "").strip() or "—"): cell.get("text")
        for cell in load_cells(point.get("cells"))
    }


def _cell_columns(points: list[dict]) -> list[str]:
    names: list[str] = []
    for point in points:
        for name in _cell_map(point):
            if name not in names:
                names.append(name)
    return names


def _step_rows(points: list[dict], names: list[str]) -> list[dict[str, Cell]]:
    rows = []
    for point in points:
        cells = _cell_map(point)
        if cells:
            rows.append(
                {
                    f"c{index}": _point_cell(point, cells.get(name))
                    for index, name in enumerate(names)
                }
            )
            continue
        rows.append(
            {
                "c0": Cell(text=point.get("label") or "—"),
                "c1": _point_cell(point, point.get("nominal_text")),
                "c2": _point_cell(point, point.get("measured_text")),
                "c3": _point_cell(point, point.get("limit_text")),
            }
        )
    return rows


def _filter_nominal(points: list[dict], nominal: float | None) -> tuple[list[dict], bool]:
    """Chỉ dòng có giá trị danh nghĩa bằng giá trị được hỏi; không dòng nào thì giữ cả bảng."""
    if nominal is None:
        return points, False
    tolerance = _NOMINAL_TOLERANCE * max(1.0, abs(nominal))
    matched = [
        point
        for point in points
        if point.get("nominal_value") is not None
        and abs(float(point["nominal_value"]) - nominal) <= tolerance
    ]
    return (matched, True) if matched else (points, False)


def _step_tables(
    session: Session,
    records: list[dict],
    steps: list[str],
    catalog: FieldCatalog,
    nominal: float | None,
) -> list[DataTable]:
    points = _points(session, [record["id"] for record in records], steps)
    tables = []
    for record in records:
        for step in steps:
            own = [p for p in points if p["record_id"] == record["id"] and p["step_code"] == step]
            own, filtered = _filter_nominal(own, nominal)
            if not own:
                continue
            names = _cell_columns(own) or list(_FALLBACK_POINT_COLUMNS)
            note = "Nguyên văn từng ô của bảng trong biên bản."
            if filtered:
                note = "Chỉ dòng có giá trị danh nghĩa được hỏi. " + note
            tables.append(
                DataTable(
                    title=f"{catalog.table_title(step)} · biên bản {_cert(record)}",
                    columns=[Column(f"c{index}", name) for index, name in enumerate(names)],
                    rows=_step_rows(own, names),
                    total=len(own),
                    note=note,
                )
            )
    return tables


def _reason_points(points: list[dict], reason: str, catalog: FieldCatalog) -> list[dict]:
    """Dòng số liệu mà kết luận "không đạt" viện dẫn (so từ ngữ, không so số)."""
    words = content_tokens(reason)
    titles = {table.step_code: table.words for table in catalog.tables}
    chosen = []
    for point in points:
        title_words = titles.get(point.get("step_code") or "", frozenset())
        label_words = content_tokens(point.get("label"))
        if (title_words and title_words <= words) or len(
            label_words & words
        ) >= _MIN_REASON_OVERLAP:
            chosen.append(point)
    return chosen


def _failure_basis(
    session: Session, records: list[dict], fields: dict[int, dict[str, dict]], catalog: FieldCatalog
) -> list[DataTable]:
    failed = [record for record in records if record.get("verdict") == "khong_dat"]
    points = _points(session, [record["id"] for record in failed])
    tables = []
    for record in failed:
        reason = (fields.get(record["id"], {}).get(VERDICT_KEY) or {}).get("value_text") or ""
        own = [point for point in points if point["record_id"] == record["id"]]
        chosen = _reason_points(own, reason, catalog)
        if not chosen:
            continue
        rows = [
            {
                "table": Cell(text=catalog.table_title(point.get("step_code") or "")),
                "label": Cell(text=point.get("label") or "—"),
                "measured": _point_cell(point, point.get("measured_text")),
                "limit": _point_cell(point, point.get("limit_text")),
            }
            for point in chosen
        ]
        tables.append(
            DataTable(
                title=f"Căn cứ kết luận không đạt · biên bản {_cert(record)}",
                columns=[
                    Column("table", "Bảng"),
                    Column("label", "Thông số"),
                    Column("measured", "Giá trị xác định"),
                    Column("limit", "Giá trị cho phép"),
                ],
                rows=rows,
                total=len(rows),
                note="Dòng số liệu mà kết luận của biên bản nhắc tới; người đọc tự đối chiếu.",
            )
        )
    return tables


def _no_match(session: Session, params: RecordLookupParams) -> DataPayload:
    """Không có biên bản khớp: liệt kê biên bản hiện có của thiết bị (nếu biết số hiệu)."""
    title = "Tra cứu biên bản"
    if not params.serial:
        return empty_payload(
            "record_lookup", title, "Không tìm thấy biên bản đã duyệt khớp yêu cầu."
        )
    records = find_records(session, RecordLookupParams(serial=params.serial))
    if not records:
        return empty_payload(
            "record_lookup",
            title,
            f"Không có biên bản đã duyệt của thiết bị số hiệu {params.serial}.",
        )
    fields = _fields_by_record(session, [record["id"] for record in records])
    table = _fields_table(records, fields, [VERDICT_KEY], field_catalog(session))
    table.title = f"Biên bản đã duyệt của thiết bị số hiệu {params.serial}"
    table.note = "Không có biên bản khớp số biên bản/ngày được hỏi; đây là các biên bản hiện có."
    return make_payload(
        intent="record_lookup",
        title=title,
        note=LEDGER_NOTE,
        tables=[table],
        citations=_citations_for_tables(session, [table]),
    )


def resolve_record_lookup(session: Session, params: RecordLookupParams) -> DataPayload:
    """Biên bản cụ thể: trường được hỏi, bảng được hỏi, căn cứ kết luận không đạt."""
    records = find_records(session, params)
    if not records:
        return _no_match(session, params)
    catalog = field_catalog(session)
    fields = _fields_by_record(session, [record["id"] for record in records])
    keys = [key for key in dict.fromkeys(params.fields) if key not in IDENTITY_KEYS]
    tables: list[DataTable] = []
    if keys:
        tables.append(_fields_table(records, fields, keys, catalog))
    elif not params.steps:
        tables.extend(_record_cards(records, fields))
    if params.steps:
        tables.extend(_step_tables(session, records, list(params.steps), catalog, params.nominal))
    if VERDICT_KEY in keys:
        tables.extend(_failure_basis(session, records, fields, catalog))
    if not tables:
        tables.append(_fields_table(records, fields, [VERDICT_KEY], catalog))
    subject = params.cert_no or params.serial or params.model_code
    return make_payload(
        intent="record_lookup",
        title=f"Biên bản {subject}" if subject else "Tra cứu biên bản",
        note=LEDGER_NOTE,
        tables=tables,
        citations=_citations_for_tables(session, tables),
    )


# ── records_summary ───────────────────────────────────────────────────────────


def _aliases(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return []
    return [str(alias) for alias in value or []]


def unit_code(session: Session, unit_text: str) -> str:
    """Mã đơn vị chuẩn (``kG/cm2`` → ``kgf/cm2``) đọc từ ``v_unit``; lạ thì giữ nguyên."""
    needle = unit_text.strip().casefold()
    for row in session.execute(text("SELECT code, aliases FROM v_unit")).mappings():
        names = {str(row["code"]).casefold(), *(a.casefold() for a in _aliases(row["aliases"]))}
        if needle in names:
            return str(row["code"])
    return unit_text.strip()


def summary_records(session: Session, params: RecordsSummaryParams) -> list[dict]:
    """Biên bản đã duyệt khớp bộ lọc tổng hợp; không bộ lọc = toàn bộ sổ cái."""
    conditions: list[str] = []
    values: dict[str, Any] = {}
    exact = {
        "serial": ("serial_no", params.serial),
        "model_code": ("model_code", params.model_code),
        "inspector": ("inspector_name", params.inspector),
        "reviewer": ("reviewer_name", params.reviewer),
    }
    for name, (column, value) in exact.items():
        if value:
            conditions.append(f"LOWER(COALESCE(r.{column}, '')) = :{name}")
            values[name] = value.strip().casefold()
    if params.owner_org:
        conditions.append("LOWER(COALESCE(r.owner_org, '')) LIKE :owner_org")
        values["owner_org"] = f"%{params.owner_org.strip().casefold()}%"
    if params.verdict:
        conditions.append("r.verdict = :verdict")
        values["verdict"] = params.verdict
    if params.date_from:
        conditions.append("r.calibrated_at >= :date_from")
        values["date_from"] = _day_bounds(params.date_from)[0]
    if params.date_to:
        conditions.append("r.calibrated_at < :date_to")
        values["date_to"] = _day_bounds(params.date_to)[1]
    if params.range_unit:
        conditions.append("LOWER(COALESCE(r.range_unit_code, '')) = :range_unit")
        values["range_unit"] = unit_code(session, params.range_unit).casefold()
    return _select_records(session, conditions, values)


def _summary_table(records: list[dict]) -> DataTable:
    devices = {record.get("device_id") for record in records if record.get("device_id") is not None}
    failed = [record for record in records if record.get("verdict") == "khong_dat"]
    row = {
        "records": Cell(text=str(len(records))),
        "devices": Cell(text=str(len(devices))),
        "failed": Cell(text=str(len(failed))),
        "failed_list": Cell(text=", ".join(_cert(record) for record in failed) or "—"),
    }
    return DataTable(
        title="Tổng hợp",
        columns=[
            Column("records", "Số biên bản"),
            Column("devices", "Số thiết bị (theo số hiệu)"),
            Column("failed", "Số biên bản không đạt"),
            Column("failed_list", "Biên bản không đạt"),
        ],
        rows=[row],
        total=1,
        note="Đếm hồ sơ đã duyệt khớp bộ lọc; không tính lại số liệu đo.",
    )


def _list_table(records: list[dict], fields: dict[int, dict[str, dict]]) -> DataTable:
    rows = []
    for record in records[:MAX_LIST_ROWS]:
        row = _identity_cells(record)
        row["range_text"] = _record_cell(
            record, record.get("range_text"), "range_min", numeric=True
        )
        row["inspector"] = _record_cell(record, record.get("inspector_name"), "kiem_dinh_vien")
        row["owner"] = _record_cell(record, record.get("owner_org"), "don_vi_su_dung")
        row[VERDICT_KEY] = _verdict_cell(record, fields.get(record["id"], {}))
        rows.append(row)
    note = None
    if len(records) > MAX_LIST_ROWS:
        note = f"Hiện {MAX_LIST_ROWS}/{len(records)} biên bản."
    return DataTable(
        title="Danh sách biên bản",
        columns=[
            *_IDENTITY_COLUMNS,
            Column("range_text", "Phạm vi đo"),
            Column("inspector", "Kiểm định viên"),
            Column("owner", "Đơn vị sử dụng"),
            Column(VERDICT_KEY, "Kết luận"),
        ],
        rows=rows,
        total=len(records),
        note=note,
    )


def _device_table(records: list[dict]) -> DataTable:
    by_device: dict[Any, list[dict]] = {}
    for record in records:
        by_device.setdefault(record.get("device_id"), []).append(record)
    rows = []
    for group in by_device.values():
        latest = group[-1]
        rows.append(
            {
                "serial_no": _record_cell(latest, latest.get("serial_no"), "so_hieu"),
                "model_code": _record_cell(latest, latest.get("model_code"), "ky_hieu"),
                "range_text": _record_cell(
                    latest, latest.get("range_text"), "range_min", numeric=True
                ),
                "count": Cell(text=str(len(group))),
            }
        )
    return DataTable(
        title="Thiết bị",
        columns=[
            Column("serial_no", "Số hiệu"),
            Column("model_code", "Ký hiệu"),
            Column("range_text", "Phạm vi đo"),
            Column("count", "Số biên bản"),
        ],
        rows=rows,
        total=len(rows),
    )


def _is_step(field: str, catalog: FieldCatalog) -> bool:
    return any(table.step_code == field for table in catalog.tables)


def _rank_candidates(
    session: Session, records: list[dict], field: str, catalog: FieldCatalog
) -> list[tuple[float, dict, bool]]:
    """``(giá trị sắp xếp, dòng gốc, là điểm đo)`` cho mọi hồ sơ có giá trị của ``field``."""
    ids = [record["id"] for record in records]
    if _is_step(field, catalog):
        points = _points(session, ids, [field])
        return [
            (float(p["measured_value"]), p, True)
            for p in points
            if p.get("measured_value") is not None
        ]
    rows = [
        own[field]
        for own in _fields_by_record(session, ids).values()
        if field in own and own[field].get("value_min") is not None
    ]
    # Có đơn vị nhận diện được thì chỉ so các giá trị đã quy đổi SI (không trộn đơn vị gốc).
    if any(row.get("unit_id") is not None for row in rows):
        rows = [row for row in rows if row.get("unit_id") is not None]
    return [(float(row["value_min"]), row, False) for row in rows]


def _rank_row(
    rank: int, record: dict, row: dict, is_point: bool, related: list[dict | None]
) -> dict[str, Cell]:
    if is_point:
        value = _point_cell(row, row.get("measured_text"))
        line = " | ".join(cell.get("text") or "" for cell in load_cells(row.get("cells")))
        detail = _point_cell(row, line or row.get("quote"))
    else:
        value = _field_cell(record, row)
        detail = Cell(text=row.get("label") or "—")
    cells = {"rank": Cell(text=str(rank)), **_identity_cells(record), "value": value}
    cells["detail"] = detail
    for index, related_row in enumerate(related):
        cells[f"related{index}"] = _field_cell(record, related_row)
    return cells


def _rank_table(
    session: Session, records: list[dict], params: RecordsSummaryParams, catalog: FieldCatalog
) -> DataTable | None:
    field = params.field or ""
    candidates = _rank_candidates(session, records, field, catalog)
    if not candidates:
        return None
    by_id = {record["id"]: record for record in records}
    candidates.sort(key=lambda item: item[0], reverse=params.measure == "max")
    top = candidates[:RANK_ROWS]
    related_keys = [] if _is_step(field, catalog) else catalog.related(field)
    fields = _fields_by_record(session, [row["record_id"] for _, row, _ in top])
    rows = [
        _rank_row(
            rank,
            by_id[row["record_id"]],
            row,
            is_point,
            [fields.get(row["record_id"], {}).get(key) for key in related_keys],
        )
        for rank, (_, row, is_point) in enumerate(top, start=1)
    ]
    label = catalog.table_title(field) if _is_step(field, catalog) else catalog.field_label(field)
    order = "nhỏ nhất" if params.measure == "min" else "lớn nhất"
    return DataTable(
        title=f"{label}: {order} trước",
        columns=[
            Column("rank", "Hạng"),
            *_IDENTITY_COLUMNS,
            Column("value", "Giá trị ghi trong biên bản"),
            Column("detail", "Nguyên văn dòng / trường"),
            *(
                Column(f"related{index}", catalog.field_label(key))
                for index, key in enumerate(related_keys)
            ),
        ],
        rows=rows,
        total=len(candidates),
        note=(
            "Sắp theo giá trị ghi trong biên bản (quy đổi về cùng đơn vị SI khi khác đơn vị); "
            "hiển thị nguyên văn, không tính lại."
        ),
    )


def resolve_records_summary(session: Session, params: RecordsSummaryParams) -> DataPayload:
    """Đếm / liệt kê / cực trị trên sổ cái đã duyệt."""
    records = summary_records(session, params)
    if not records:
        return empty_payload(
            "records_summary", "Tổng hợp sổ cái", "Không có biên bản đã duyệt khớp bộ lọc."
        )
    catalog = field_catalog(session)
    fields = _fields_by_record(session, [record["id"] for record in records])
    tables: list[DataTable] = []
    if params.measure in ("min", "max"):
        ranked = _rank_table(session, records, params, catalog)
        if ranked is not None:
            tables.append(ranked)
    tables.append(_summary_table(records))
    if params.range_unit:
        tables.append(_device_table(records))
    tables.append(_list_table(records, fields))
    return make_payload(
        intent="records_summary",
        title="Tổng hợp sổ cái",
        note=LEDGER_NOTE,
        tables=tables,
        citations=_citations_for_tables(session, tables),
    )


RECORD_RESOLVERS: dict[str, Any] = {
    "record_lookup": resolve_record_lookup,
    "records_summary": resolve_records_summary,
}
