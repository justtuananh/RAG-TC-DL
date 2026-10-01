"""Tổng hợp sổ cái đã duyệt cho ``records_summary``: đếm / liệt kê / cực trị (Pha R).

Mỗi câu hỏi trả MỘT câu trả lời tất định (``query.record_answer_summary``,
``query.record_answer``) + đúng bảng của điều được hỏi: đếm → bảng tổng hợp (+ biên bản
không đạt); liệt kê → danh sách biên bản; thiết bị → bảng thiết bị; cực trị → chỉ dòng
thắng. Cực trị chỉ SẮP XẾP theo số đã phân tích (quy đổi cùng SI khi đơn vị nhận diện
được), không hiển thị số tính ra (P2) và không so chéo hai QTKĐ.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from query.answer_phrases import cert
from query.record_answer import RankGroup, extreme_answer, field_sentence, point_sentence
from query.record_answer_summary import is_overview, summary_answer
from query.record_cells import (
    IDENTITY_COLUMNS,
    VALUE_TOLERANCE,
    day_bounds,
    field_cell,
    fields_by_record,
    identity_cells,
    load_points,
    point_cell,
    record_cell,
    select_records,
    verdict_cell,
)
from query.record_fields import VERDICT_KEY, FieldCatalog, field_catalog, load_cells
from query.record_intents import RecordsSummaryParams
from query.table_model import (
    LEDGER_NOTE,
    Cell,
    Column,
    DataPayload,
    DataTable,
    _citations_for_tables,
    empty_payload,
    make_payload,
)

MAX_LIST_ROWS = 50
# Cột luôn có trong danh sách biên bản: trường hỏi kèm trùng nhãn thì không thêm cột.
_LISTED = frozenset({"Phạm vi đo", "Kiểm định viên", "Đơn vị sử dụng", "Kết luận"})


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
    # Kèm so nguyên văn: LOWER() của SQLite không hạ chữ hoa có dấu ("Đ"), còn bộ định
    # tuyến truyền đúng nguyên văn sổ cái.
    for name, (column, value) in exact.items():
        if value:
            conditions.append(
                f"(r.{column} = :{name}_raw OR LOWER(COALESCE(r.{column}, '')) = :{name})"
            )
            values[f"{name}_raw"] = value.strip()
            values[name] = value.strip().casefold()
    if params.owner_org:
        conditions.append(
            "(r.owner_org = :owner_org_raw OR LOWER(COALESCE(r.owner_org, '')) LIKE :owner_org)"
        )
        values["owner_org_raw"] = params.owner_org.strip()
        values["owner_org"] = f"%{params.owner_org.strip().casefold()}%"
    if params.verdict:
        conditions.append("r.verdict = :verdict")
        values["verdict"] = params.verdict
    if params.date_from:
        conditions.append("r.calibrated_at >= :date_from")
        values["date_from"] = day_bounds(params.date_from)[0]
    if params.date_to:
        conditions.append("r.calibrated_at < :date_to")
        values["date_to"] = day_bounds(params.date_to)[1]
    if params.procedure_ids:
        conditions.append("r.procedure_id IN :procedure_ids")
        values["procedure_ids"] = list(params.procedure_ids)
    if params.range_unit:
        conditions.append("LOWER(COALESCE(r.range_unit_code, '')) = :range_unit")
        values["range_unit"] = unit_code(session, params.range_unit).casefold()
    return select_records(session, conditions, values)


def _summary_table(records: list[dict]) -> DataTable:
    devices = {record.get("device_id") for record in records if record.get("device_id") is not None}
    failed = [record for record in records if record.get("verdict") == "khong_dat"]
    row = {
        "records": Cell(text=str(len(records))),
        "devices": Cell(text=str(len(devices))),
        "failed": Cell(text=str(len(failed))),
        "failed_list": Cell(text=", ".join(cert(record) for record in failed) or "—"),
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
        row = identity_cells(record)
        row["range_text"] = record_cell(record, record.get("range_text"), "range_min", numeric=True)
        row["inspector"] = record_cell(record, record.get("inspector_name"), "kiem_dinh_vien")
        row["owner"] = record_cell(record, record.get("owner_org"), "don_vi_su_dung")
        row[VERDICT_KEY] = verdict_cell(record, fields.get(record["id"], {}))
        rows.append(row)
    note = None
    if len(records) > MAX_LIST_ROWS:
        note = f"Hiện {MAX_LIST_ROWS}/{len(records)} biên bản."
    return DataTable(
        title="Danh sách biên bản",
        columns=[
            *IDENTITY_COLUMNS,
            Column("range_text", "Phạm vi đo"),
            Column("inspector", "Kiểm định viên"),
            Column("owner", "Đơn vị sử dụng"),
            Column(VERDICT_KEY, "Kết luận"),
        ],
        rows=rows,
        total=len(records),
        note=note,
    )


def _asked_columns(keys: list[str], catalog: FieldCatalog) -> list[Column]:
    return [Column(f"f_{key}", catalog.field_label(key)) for key in keys]


def _asked_cells(record: dict, own: dict[str, dict], keys: list[str]) -> dict[str, Cell]:
    return {f"f_{key}": field_cell(record, own.get(key)) for key in keys}


def _device_table(
    records: list[dict],
    fields: dict[int, dict[str, dict]] | None = None,
    keys: list[str] | None = None,
    catalog: FieldCatalog | None = None,
) -> DataTable:
    keys = keys or []
    by_device: dict[Any, list[dict]] = {}
    for record in records:
        by_device.setdefault(record.get("device_id"), []).append(record)
    rows = []
    for group in by_device.values():
        latest = group[-1]
        rows.append(
            {
                "serial_no": record_cell(latest, latest.get("serial_no"), "so_hieu"),
                "model_code": record_cell(latest, latest.get("model_code"), "ky_hieu"),
                "range_text": record_cell(
                    latest, latest.get("range_text"), "range_min", numeric=True
                ),
                **_asked_cells(latest, (fields or {}).get(latest["id"], {}), keys),
                "count": Cell(text=str(len(group))),
            }
        )
    return DataTable(
        title="Thiết bị",
        columns=[
            Column("serial_no", "Số hiệu"),
            Column("model_code", "Ký hiệu"),
            Column("range_text", "Phạm vi đo"),
            *(_asked_columns(keys, catalog) if catalog else []),
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
        points = load_points(session, ids, [field])
        return [
            (float(p["measured_value"]), p, True)
            for p in points
            if p.get("measured_value") is not None
        ]
    rows = [
        own[field]
        for own in fields_by_record(session, ids).values()
        if field in own and own[field].get("value_min") is not None
    ]
    # Có đơn vị nhận diện được thì chỉ so các giá trị đã quy đổi SI (không trộn đơn vị gốc).
    if any(row.get("unit_id") is not None for row in rows):
        rows = [row for row in rows if row.get("unit_id") is not None]
    return [(float(row["value_min"]), row, False) for row in rows]


def _rank_row(
    record: dict, row: dict, is_point: bool, related: list[dict | None]
) -> dict[str, Cell]:
    if is_point:
        value = point_cell(row, row.get("measured_text"))
        line = " | ".join(cell.get("text") or "" for cell in load_cells(row.get("cells")))
        detail = point_cell(row, line or row.get("quote"))
    else:
        value = field_cell(record, row)
        detail = Cell(text=row.get("label") or "—")
    cells = {**identity_cells(record), "value": value}
    cells["detail"] = detail
    for index, related_row in enumerate(related):
        cells[f"related{index}"] = field_cell(record, related_row)
    return cells


def _winners(
    candidates: list[tuple[float, dict, bool]], measure: str
) -> list[tuple[float, dict, bool]]:
    """Mọi dòng bằng giá trị cực trị (đồng hạng thì nêu đủ, không chọn bừa một dòng)."""
    ordered = sorted(candidates, key=lambda item: item[0], reverse=measure == "max")
    best = ordered[0][0]
    tolerance = VALUE_TOLERANCE * max(1.0, abs(best))
    return [item for item in ordered if abs(item[0] - best) <= tolerance]


def _rank_group(
    session: Session,
    by_id: dict[int, dict],
    candidates: list[tuple[float, dict, bool]],
    params: RecordsSummaryParams,
    catalog: FieldCatalog,
    procedure: str | None,
) -> RankGroup:
    """Dòng thắng cực trị của các biên bản MỘT QTKĐ (không so chéo quy trình)."""
    field = params.field or ""
    top = _winners(candidates, params.measure)
    procedure_id = top[0][1].get("procedure_id")
    is_step = _is_step(field, catalog)
    related_keys = [] if is_step else catalog.related(field)
    fields = fields_by_record(session, [row["record_id"] for _, row, _ in top])
    label = catalog.table_title(field, procedure_id) if is_step else catalog.field_label(field)
    order = "nhỏ nhất" if params.measure == "min" else "lớn nhất"
    rows, sentences = [], []
    for _, row, is_point in top:
        record = by_id[row["record_id"]]
        related = [fields.get(row["record_id"], {}).get(key) for key in related_keys]
        rows.append(_rank_row(record, row, is_point, related))
        if is_point:
            sentences.append(point_sentence(record, row, label))
        else:
            labels = [catalog.field_label(key) for key in related_keys]
            sentences.append(
                field_sentence(record, row, label, list(zip(labels, related, strict=True)))
            )
    scope = f" · QTKĐ {procedure}" if procedure else ""
    table = DataTable(
        title=f"{label}: {order}{scope}",
        columns=[
            *IDENTITY_COLUMNS,
            Column("value", "Giá trị ghi trong biên bản"),
            Column("detail", "Nguyên văn dòng / trường"),
            *(
                Column(f"related{index}", catalog.field_label(key))
                for index, key in enumerate(related_keys)
            ),
        ],
        rows=rows,
        total=len(rows),
        note=(
            f"Giá trị {order} trong {len(candidates)} giá trị ghi trong biên bản (quy đổi về "
            "cùng đơn vị SI khi khác đơn vị); hiển thị nguyên văn, không tính lại. "
            "Chỉ so biên bản cùng một QTKĐ."
        ),
    )
    return RankGroup(
        table=table, procedure=procedure, label=label, order=order, sentences=sentences
    )


def _rank_tables(
    session: Session, records: list[dict], params: RecordsSummaryParams, catalog: FieldCatalog
) -> list[RankGroup]:
    """Một nhóm cực trị cho mỗi QTKĐ: cùng mã bảng/nhãn ở hai QTKĐ không cùng đại lượng."""
    candidates = _rank_candidates(session, records, params.field or "", catalog)
    by_id = {record["id"]: record for record in records}
    groups: dict[Any, list[tuple[float, dict, bool]]] = {}
    for item in candidates:
        procedure_id = by_id[item[1]["record_id"]].get("procedure_id")
        groups.setdefault(procedure_id, []).append(item)
    result = []
    for group in groups.values():
        record = by_id[group[0][1]["record_id"]]
        procedure = record.get("procedure_number") if len(groups) > 1 else None
        result.append(_rank_group(session, by_id, group, params, catalog, procedure))
    return result


def _resolve_extreme(
    session: Session, records: list[dict], params: RecordsSummaryParams
) -> DataPayload:
    """ "Biên bản nào ... thấp nhất": câu trả lời + bảng dòng thắng, không kèm cả sổ cái."""
    groups = _rank_tables(session, records, params, field_catalog(session))
    if not groups:
        return empty_payload(
            "records_summary", "Tổng hợp sổ cái", "Không có biên bản đã duyệt có giá trị này."
        )
    tables = [group.table for group in groups]
    return make_payload(
        intent="records_summary",
        title="Tổng hợp sổ cái",
        note=LEDGER_NOTE,
        tables=tables,
        citations=_citations_for_tables(session, tables),
        answer=extreme_answer(groups),
    )


def _summary_tables(
    records: list[dict],
    fields: dict[int, dict[str, dict]],
    params: RecordsSummaryParams,
    catalog: FieldCatalog,
) -> list[DataTable]:
    """Đúng bảng của điều được hỏi: thiết bị / số lượng (+ biên bản không đạt) / danh sách."""
    keys = _summary_keys(params, catalog)
    if params.subject == "devices":
        return [_device_table(records, fields, keys, catalog)]
    if is_overview(params):
        failed = [record for record in records if record.get("verdict") == "khong_dat"]
        tables = [_summary_table(records)]
        if failed:
            failed_list = _list_table(failed, fields)
            failed_list.title = "Biên bản không đạt"
            tables.append(failed_list)
        return tables
    table = _list_table(records, fields)
    extra = [column for column in _asked_columns(keys, catalog) if column.label not in _LISTED]
    if extra:
        table.columns[-1:-1] = extra
        for record, row in zip(records, table.rows, strict=False):
            row.update(_asked_cells(record, fields.get(record["id"], {}), keys))
    return [table]


def _summary_keys(params: RecordsSummaryParams, catalog: FieldCatalog) -> list[str]:
    """Trường hỏi kèm có trong danh mục (khóa lạ từ LLM bị bỏ, không lọt vào bảng)."""
    known = {entry.key for entry in catalog.fields}
    return [key for key in dict.fromkeys(params.fields) if key in known and key != VERDICT_KEY]


def resolve_records_summary(session: Session, params: RecordsSummaryParams) -> DataPayload:
    """Đếm / liệt kê / cực trị trên sổ cái đã duyệt."""
    records = summary_records(session, params)
    if not records:
        return empty_payload(
            "records_summary", "Tổng hợp sổ cái", "Không có biên bản đã duyệt khớp bộ lọc."
        )
    if params.measure in ("min", "max"):
        return _resolve_extreme(session, records, params)
    fields = fields_by_record(session, [record["id"] for record in records])
    catalog = field_catalog(session)
    tables = _summary_tables(records, fields, params, catalog)
    keys = _summary_keys(params, catalog)
    labels = {key: catalog.field_label(key) for key in keys}
    return make_payload(
        intent="records_summary",
        title="Tổng hợp sổ cái",
        note=LEDGER_NOTE,
        tables=tables,
        citations=_citations_for_tables(session, tables),
        answer=summary_answer(records, fields, params, labels),
    )
