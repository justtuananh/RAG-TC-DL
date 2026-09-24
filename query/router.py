"""Tầng định tuyến chat lai văn bản + số liệu (spec §8).

Ba nhánh:

- ``text`` — pipeline RAG văn bản hiện tại, không đổi.
- ``data`` — chạy một intent đã kiểm tham số rồi trả bảng kèm tham chiếu xuất xứ.
- ``mixed`` — chạy cả hai và ghép: phần quy định lấy từ QTKĐ, phần số liệu lấy
  từ sổ cái, mỗi phần giữ trích dẫn riêng.

Không chắc chắn → ``text`` (trả lời thiếu số liệu nhưng đúng nguồn tốt hơn trả lời
số liệu sai nhánh).

Bất biến:
- P1: mỗi ô số trong bảng kèm tham chiếu ``{kind, id, field}``; bảng cũng mang
  danh sách trích dẫn sổ cái để tách bạch với trích dẫn QTKĐ.
- P2: không tính lại số liệu nguồn; chỉ đọc và định dạng.
- P3: mọi truy vấn đi qua ``query.records``/``query.approved``/``v_*`` tham chiếu,
  tuyệt đối không chạm bảng gốc.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from query import approved as approved_query
from query import intents
from query import provenance as provenance_query
from query import records as records_query

logger = logging.getLogger(__name__)

CITATION_CAP = 12
TREND_POINT_CAP = 200


# ── Mô hình bảng kết quả (thuần dữ liệu, dễ serialize) ────────────────────────


@dataclass(frozen=True)
class Column:
    key: str
    label: str


@dataclass
class Cell:
    """Một ô trong bảng; ``provenance`` bắt buộc với ô số (P1)."""

    text: str
    numeric: bool = False
    provenance: dict[str, Any] | None = None
    device_id: int | None = None
    record_id: int | None = None


@dataclass
class DataTable:
    title: str
    columns: list[Column]
    rows: list[dict[str, Cell]] = field(default_factory=list)
    note: str | None = None
    total: int | None = None


@dataclass
class DataPayload:
    intent: str
    branch: str
    title: str
    note: str
    tables: list[DataTable] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    empty: bool = False


# ── Định dạng hiển thị ────────────────────────────────────────────────────────


def _date_text(value: Any) -> str:
    if value is None or value == "":
        return "—"
    parsed: datetime | date | None = None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return value
    if parsed is None:
        return str(value)
    return parsed.strftime("%d/%m/%Y")


def _num_text(value: Any, digits: int = 3) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number != number or number in (float("inf"), float("-inf")):
        return "—"
    fixed = f"{number:.{digits}f}"
    fixed = fixed.rstrip("0").rstrip(".")
    return fixed or "0"


def _range_text(minimum: Any, maximum: Any, unit: str | None) -> str:
    has_min = minimum is not None
    has_max = maximum is not None
    if not has_min and not has_max:
        return "—"
    suffix = f" {unit}" if unit else ""
    if has_min and has_max:
        return f"{_num_text(minimum)} – {_num_text(maximum)}{suffix}"
    return f"{_num_text(minimum if has_min else maximum)}{suffix}"


# ── Tham chiếu xuất xứ của hồ sơ/số liệu đo ──────────────────────────────────


def _prov_of(record: dict[str, Any], field_name: str) -> dict[str, Any] | None:
    for cell in record.get("provenance") or []:
        if cell.get("field") == field_name:
            return dict(cell)
    return None


def _text_cell(record: dict[str, Any], value: Any, *, field_name: str | None = None) -> Cell:
    ref = _prov_of(record, field_name) if field_name else None
    return Cell(
        text="—" if value in (None, "") else str(value),
        numeric=False,
        provenance=ref,
        device_id=record.get("device_id"),
        record_id=record.get("id"),
    )


def _num_cell(record: dict[str, Any], field_name: str, value: Any, *, digits: int = 3) -> Cell:
    """Ô số: CHỈ hiện con số khi có tham chiếu xuất xứ; thiếu nguồn → để trống.

    Đây là hàng rào P1 ở tầng trình bày: không bao giờ đưa ra một con số không
    truy được về nguyên văn (spec §8 cổng: không có số không truy được nguồn).
    """
    ref = _prov_of(record, field_name)
    if ref is None:
        return Cell(text="—", numeric=False)
    return Cell(
        text=_num_text(value, digits),
        numeric=True,
        provenance=ref,
        device_id=record.get("device_id"),
        record_id=record.get("id"),
    )


def _date_cell(record: dict[str, Any], field_name: str) -> Cell:
    return _text_cell(record, _date_text(record.get(field_name)), field_name=field_name)


# ── Tra cứu tham chiếu (chỉ đọc view, P3) ─────────────────────────────────────


def _number_candidates(value: str) -> list[str]:
    text_value = (value or "").strip()
    matches = re.findall(r"\d+(?:\.\d+){1,2}", text_value)
    ordered: list[str] = []
    for match in matches:
        if match not in ordered:
            ordered.append(match)
    if text_value and text_value not in ordered:
        ordered.append(text_value)
    return ordered


def _find_procedure(
    session: Session, *, number: str | None = None, device_type: str | None = None
) -> dict[str, Any] | None:
    """Phân giải số QTKĐ / loại thiết bị → một dòng ``v_procedure`` (P3)."""
    if number:
        for candidate in _number_candidates(number):
            row = (
                session.execute(
                    text("SELECT * FROM v_procedure WHERE number = :number"),
                    {"number": candidate},
                )
                .mappings()
                .first()
            )
            if row is not None:
                return dict(row)
        row = (
            session.execute(
                text("SELECT * FROM v_procedure WHERE number LIKE :needle ORDER BY year DESC"),
                {"needle": f"%{number.strip()}%"},
            )
            .mappings()
            .first()
        )
        if row is not None:
            return dict(row)
    if device_type:
        needle = device_type.strip().lower()
        if needle:
            rows = session.execute(text("SELECT * FROM v_procedure")).mappings().all()
            for row in rows:
                haystack = (row["device_type_name"] or "").lower()
                if needle in haystack or haystack in needle:
                    return dict(row)
    return None


def _find_quantity(session: Session, name: str) -> dict[str, Any] | None:
    """Phân giải tên đại lượng → một dòng ``v_quantity`` (P3)."""
    needle = (name or "").strip().lower()
    if not needle:
        return None
    rows = session.execute(text("SELECT * FROM v_quantity")).mappings().all()
    for row in rows:
        code = (row["code"] or "").lower()
        label = (row["name_vi"] or "").lower()
        if needle == code or needle in label or label in needle:
            return dict(row)
    return None


def _unit_codes(session: Session) -> dict[int, str]:
    rows = session.execute(text("SELECT id, code FROM v_unit")).mappings().all()
    return {int(row["id"]): row["code"] for row in rows}


# ── Trích dẫn sổ cái (tách bạch với trích dẫn QTKĐ) ───────────────────────────


def _provenance_params(ref: dict[str, Any]) -> dict[str, Any]:
    kind = ref.get("kind")
    ref_id = ref.get("id")
    if kind == "measurement":
        return {"measurement_id": ref_id, "field": ref.get("field")}
    if kind == "fact":
        return {"fact_id": ref_id}
    if kind == "extraction":
        return {"extraction_id": ref_id}
    return {"record_id": ref_id}


def _iter_cells(tables: list[DataTable]):
    for table in tables:
        for row in table.rows:
            for cell in row.values():
                yield table, cell


def _citations_for_tables(
    session: Session, tables: list[DataTable], *, cap: int = CITATION_CAP
) -> list[dict[str, Any]]:
    """Dựng trích dẫn sổ cái cho các ô số, khử trùng lặp, giới hạn số lượng."""
    seen: set[tuple[Any, Any, Any]] = set()
    citations: list[dict[str, Any]] = []
    for _table, cell in _iter_cells(tables):
        ref = cell.provenance
        if not ref:
            continue
        key = (ref.get("kind"), ref.get("id"), ref.get("field"))
        if key in seen:
            continue
        seen.add(key)
        try:
            source = provenance_query.resolve(session, **_provenance_params(ref))
        except provenance_query.ProvenanceError:
            continue
        citations.append(
            {
                "kind": source.get("kind"),
                "file_stem": source.get("file_stem"),
                "document_id": source.get("document_id"),
                "display_name": source.get("display_name"),
                "section_path": source.get("section_path"),
                "chunk_id": source.get("chunk_id"),
                "quote": source.get("quote"),
                "value_text": source.get("value_text"),
                "record_id": source.get("record_id"),
                "measurement_id": source.get("measurement_id"),
                "fact_id": source.get("fact_id"),
            }
        )
        if len(citations) >= cap:
            break
    return citations


# ── Bộ dựng bảng cho từng intent ──────────────────────────────────────────────

FACT_KIND_LABELS: dict[str, str] = {
    "working_range": "Phạm vi đo",
    "accuracy_class": "Cấp chính xác",
    "max_permissible_error": "Sai số cho phép lớn nhất",
    "calibration_interval": "Chu kỳ kiểm định",
    "env_condition": "Điều kiện môi trường",
    "inspection_step": "Bước kiểm định",
    "formula": "Công thức",
    "appendix_field": "Trường mẫu hồ sơ",
}


def _payload(
    *,
    intent: str,
    title: str,
    note: str,
    tables: list[DataTable],
    citations: list[dict[str, Any]],
    total: int | None = None,
) -> DataPayload:
    rows = sum(len(table.rows) for table in tables)
    empty = rows == 0
    if total is not None:
        empty = total == 0
    return DataPayload(
        intent=intent,
        branch="data",
        title=title,
        note=note,
        tables=tables,
        citations=citations,
        empty=empty,
    )


def _empty_payload(intent: str, title: str, note: str) -> DataPayload:
    return DataPayload(
        intent=intent, branch="data", title=title, note=note, tables=[], citations=[], empty=True
    )


def _timeline_table(history: dict[str, Any]) -> DataTable:
    columns = [
        Column("calibrated_at", "Ngày kiểm định"),
        Column("procedure_number", "QTKĐ"),
        Column("verdict", "Kết luận"),
        Column("expires_at", "Hạn hiệu lực"),
        Column("measurement_count", "Số điểm đo"),
        Column("cert_no", "Số GCN"),
        Column("file_stem", "Hồ sơ gốc"),
    ]
    rows: list[dict[str, Cell]] = []
    for record in history.get("records", []):
        rows.append(
            {
                "calibrated_at": _date_cell(record, "calibrated_at"),
                "procedure_number": _text_cell(record, record.get("procedure_number")),
                "verdict": _text_cell(record, record.get("verdict_label") or record.get("verdict")),
                "expires_at": _date_cell(record, "expires_at"),
                "measurement_count": _num_cell(
                    record, "measurement_count", record.get("measurement_count"), digits=0
                ),
                "cert_no": _text_cell(record, record.get("cert_no")),
                "file_stem": _text_cell(record, record.get("file_stem")),
            }
        )
    return DataTable(
        title="Dòng thời gian kiểm định",
        columns=columns,
        rows=rows,
        total=history.get("record_count"),
        note="Mỗi lần kiểm định đã duyệt; số điểm đo bấm để mở nguồn.",
    )


def _trend_tables(history: dict[str, Any], *, step_code: str | None = None) -> list[DataTable]:
    tables: list[DataTable] = []
    needle = (step_code or "").strip().lower()
    count = 0
    rows: list[dict[str, Cell]] = []
    for series in history.get("trend", []):
        key = str(series.get("key") or "")
        if (
            needle
            and needle not in key.lower()
            and needle not in str(series.get("step_code") or "").lower()
        ):
            continue
        for point in series.get("points", []):
            if count >= TREND_POINT_CAP:
                break
            count += 1
            rows.append(
                {
                    "step": Cell(text=key or "—"),
                    "calibrated_at": Cell(text=_date_text(point.get("calibrated_at"))),
                    "error": _num_cell(point, "error", point.get("error_value")),
                    "limit": _num_cell(point, "limit", point.get("limit_value")),
                    "within": Cell(
                        text=(
                            "Trong giới hạn"
                            if point.get("within_limit") is True
                            else "Vượt giới hạn"
                            if point.get("within_limit") is False
                            else "—"
                        )
                    ),
                    "record_id": Cell(
                        text=str(point.get("record_id") or "—"),
                        record_id=point.get("record_id"),
                        device_id=history.get("device", {}).get("id"),
                    ),
                }
            )
    if rows:
        tables.append(
            DataTable(
                title="Diễn biến sai số theo mốc đo",
                columns=[
                    Column("step", "Mốc đo"),
                    Column("calibrated_at", "Ngày"),
                    Column("error", "Sai số"),
                    Column("limit", "Giới hạn"),
                    Column("within", "Đối chiếu"),
                    Column("record_id", "Hồ sơ"),
                ],
                rows=rows,
                note="Sai số đọc nguyên trạng từ biên bản (P2).",
            )
        )
    return tables


def _device_title(device: dict[str, Any]) -> str:
    serial = device.get("serial_no") or "(không số hiệu)"
    return f"Thiết bị {serial}"


LEDGER_NOTE = "Đọc từ sổ cái hồ sơ đã duyệt — không phải trích từ tài liệu QTKĐ."


def resolve_device_history(session: Session, params: intents.DeviceHistoryParams) -> DataPayload:
    history = records_query.device_history(session, serial=params.serial)
    tables = [_timeline_table(history), *_trend_tables(history)]
    return _payload(
        intent="device_history",
        title=f"Lịch sử kiểm định — {_device_title(history['device'])}",
        note=LEDGER_NOTE,
        tables=tables,
        citations=_citations_for_tables(session, tables),
        total=history.get("record_count"),
    )


def resolve_latest_record(session: Session, params: intents.LatestRecordParams) -> DataPayload:
    history = records_query.device_history(session, serial=params.serial)
    records = history.get("records", [])
    if not records:
        return _empty_payload(
            "latest_record",
            f"Lần kiểm định gần nhất — {_device_title(history['device'])}",
            LEDGER_NOTE,
        )
    record = records[-1]
    table = DataTable(
        title="Lần kiểm định gần nhất",
        columns=[
            Column("calibrated_at", "Ngày kiểm định"),
            Column("procedure_number", "QTKĐ"),
            Column("verdict", "Kết luận"),
            Column("mode", "Chế độ"),
            Column("expires_at", "Hạn hiệu lực"),
            Column("measurement_count", "Số điểm đo"),
            Column("cert_no", "Số GCN"),
            Column("file_stem", "Hồ sơ gốc"),
        ],
        rows=[
            {
                "calibrated_at": _date_cell(record, "calibrated_at"),
                "procedure_number": _text_cell(record, record.get("procedure_number")),
                "verdict": _text_cell(record, record.get("verdict_label") or record.get("verdict")),
                "mode": _text_cell(record, record.get("mode_label") or record.get("mode")),
                "expires_at": _date_cell(record, "expires_at"),
                "measurement_count": _num_cell(
                    record, "measurement_count", record.get("measurement_count"), digits=0
                ),
                "cert_no": _text_cell(record, record.get("cert_no")),
                "file_stem": _text_cell(record, record.get("file_stem")),
            }
        ],
    )
    return _payload(
        intent="latest_record",
        title=f"Lần kiểm định gần nhất — {_device_title(history['device'])}",
        note=LEDGER_NOTE,
        tables=[table],
        citations=_citations_for_tables(session, [table]),
        total=1,
    )


def resolve_records_by_period(
    session: Session, params: intents.RecordsByPeriodParams
) -> DataPayload:
    records, total = records_query.list_records(
        session,
        date_from=params.date_from,
        date_to=params.date_to,
        verdict=params.verdict,
        limit=50,
    )
    columns = [
        Column("calibrated_at", "Ngày kiểm định"),
        Column("serial_no", "Số hiệu"),
        Column("device_type_name", "Loại thiết bị"),
        Column("procedure_number", "QTKĐ"),
        Column("verdict", "Kết luận"),
        Column("expires_at", "Hạn hiệu lực"),
        Column("measurement_count", "Số điểm đo"),
    ]
    rows: list[dict[str, Cell]] = []
    for record in records:
        rows.append(
            {
                "calibrated_at": _date_cell(record, "calibrated_at"),
                "serial_no": _text_cell(record, record.get("serial_no")),
                "device_type_name": _text_cell(record, record.get("device_type_name")),
                "procedure_number": _text_cell(record, record.get("procedure_number")),
                "verdict": _text_cell(record, record.get("verdict_label") or record.get("verdict")),
                "expires_at": _date_cell(record, "expires_at"),
                "measurement_count": _num_cell(
                    record, "measurement_count", record.get("measurement_count"), digits=0
                ),
            }
        )
    table = DataTable(
        title="Hồ sơ trong khoảng thời gian",
        columns=columns,
        rows=rows,
        total=total,
        note="Tối đa 50 dòng gần nhất; bấm số điểm đo hoặc ngày để mở nguồn.",
    )
    return _payload(
        intent="records_by_period",
        title="Hồ sơ kiểm định theo khoảng thời gian",
        note=LEDGER_NOTE,
        tables=[table],
        citations=_citations_for_tables(session, [table]),
        total=total,
    )


def resolve_procedure_params(
    session: Session, params: intents.ProcedureParamsParams
) -> DataPayload:
    procedure = _find_procedure(
        session, number=params.procedure_number, device_type=params.device_type
    )
    if procedure is None:
        return _empty_payload(
            "procedure_params",
            "Thông số tham chiếu QTKĐ",
            "Không tìm thấy QTKĐ đã có dữ kiện được duyệt khớp yêu cầu.",
        )
    facts = approved_query.list_approved_facts(session, procedure_id=procedure["id"], limit=200)
    units = _unit_codes(session)
    columns = [
        Column("fact_kind", "Loại dữ kiện"),
        Column("label", "Nhãn"),
        Column("value_text", "Giá trị nguyên văn"),
        Column("value_range", "Khoảng giá trị"),
        Column("condition_text", "Điều kiện"),
    ]
    rows: list[dict[str, Cell]] = []
    for fact in facts:
        ref = {"kind": "fact", "id": fact.get("id"), "field": fact.get("fact_kind")}
        range_text = _range_text(
            fact.get("value_min"),
            fact.get("value_max"),
            units.get(fact.get("unit_id")) if fact.get("unit_id") else None,
        )
        has_range = fact.get("value_min") is not None or fact.get("value_max") is not None
        rows.append(
            {
                "fact_kind": Cell(
                    text=FACT_KIND_LABELS.get(fact.get("fact_kind"), fact.get("fact_kind") or "—")
                ),
                "label": Cell(text=fact.get("label") or "—"),
                "value_text": Cell(text=fact.get("value_text") or "—", provenance=dict(ref)),
                "value_range": Cell(
                    text=range_text if has_range else "—",
                    numeric=has_range,
                    provenance=dict(ref) if has_range else None,
                ),
                "condition_text": Cell(text=fact.get("condition_text") or "—"),
            }
        )
    table = DataTable(
        title=f"Thông số QTKĐ {procedure.get('number') or ''}".strip(),
        columns=columns,
        rows=rows,
        total=len(rows),
        note="Chỉ dữ kiện đã duyệt của QTKĐ này; giá trị nguyên văn kèm nguồn.",
    )
    return _payload(
        intent="procedure_params",
        title=f"Thông số tham chiếu — QTKĐ {procedure.get('number') or ''}".strip(),
        note=LEDGER_NOTE,
        tables=[table],
        citations=_citations_for_tables(session, [table]),
        total=len(rows),
    )


def resolve_standards_for(session: Session, params: intents.StandardsForParams) -> DataPayload:
    procedure = _find_procedure(session, number=params.procedure_number)
    if procedure is None:
        return _empty_payload(
            "standards_for",
            "Phương tiện kiểm định",
            "Không tìm thấy QTKĐ khớp số yêu cầu.",
        )
    standards = approved_query.list_approved_standards(
        session, procedure_id=procedure["id"], limit=200
    )
    columns = [
        Column("ord", "TT"),
        Column("name_vi", "Phương tiện kiểm định"),
        Column("range_text", "Phạm vi đo"),
        Column("accuracy_text", "Cấp chính xác"),
        Column("note", "Ghi chú"),
    ]
    rows: list[dict[str, Cell]] = []
    for standard in standards:
        ref = {"kind": "extraction", "id": standard.get("extraction_id"), "field": None}
        rows.append(
            {
                "ord": Cell(
                    text=str(standard.get("ord") or "—"), numeric=False, provenance=dict(ref)
                ),
                "name_vi": Cell(text=standard.get("name_vi") or "—", provenance=dict(ref)),
                "range_text": Cell(text=standard.get("range_text") or "—", provenance=dict(ref)),
                "accuracy_text": Cell(
                    text=standard.get("accuracy_text") or "—", provenance=dict(ref)
                ),
                "note": Cell(text=standard.get("note") or "—", provenance=dict(ref)),
            }
        )
    table = DataTable(
        title=f"Bảng 2 phương tiện kiểm định — QTKĐ {procedure.get('number') or ''}".strip(),
        columns=columns,
        rows=rows,
        total=len(rows),
        note="Mỗi dòng là một phương tiện chuẩn đã duyệt; bấm để mở nguồn.",
    )
    return _payload(
        intent="standards_for",
        title=f"Phương tiện kiểm định — QTKĐ {procedure.get('number') or ''}".strip(),
        note=LEDGER_NOTE,
        tables=[table],
        citations=_citations_for_tables(session, [table]),
        total=len(rows),
    )


def resolve_devices_by_range(session: Session, params: intents.DevicesByRangeParams) -> DataPayload:
    quantity = _find_quantity(session, params.quantity)
    if quantity is None:
        return _empty_payload(
            "devices_by_range",
            "Thiết bị theo phạm vi đo",
            f"Không nhận diện được đại lượng {params.quantity!r}.",
        )
    records, total = records_query.list_records(
        session,
        quantity_id=quantity["id"],
        range_min=params.min_value,
        range_max=params.max_value,
        range_unit=params.unit,
        limit=200,
    )
    seen: set[int] = set()
    columns = [
        Column("serial_no", "Số hiệu"),
        Column("device_type_name", "Loại thiết bị"),
        Column("quantity_name", "Đại lượng"),
        Column("range", "Phạm vi đo"),
        Column("calibrated_at", "Ngày kiểm định"),
        Column("verdict", "Kết luận"),
    ]
    rows: list[dict[str, Cell]] = []
    for record in records:
        device_id = record.get("device_id")
        if device_id is not None:
            if device_id in seen:
                continue
            seen.add(device_id)
        range_ref = _prov_of(record, "range_min")
        range_text = _range_text(
            record.get("range_min"), record.get("range_max"), record.get("range_unit_code")
        )
        rows.append(
            {
                "serial_no": _text_cell(record, record.get("serial_no")),
                "device_type_name": _text_cell(record, record.get("device_type_name")),
                "quantity_name": _text_cell(record, record.get("quantity_name")),
                "range": Cell(
                    text=range_text if range_ref else "—",
                    numeric=range_ref is not None,
                    provenance=dict(range_ref) if range_ref else None,
                    device_id=device_id,
                    record_id=record.get("id"),
                ),
                "calibrated_at": _date_cell(record, "calibrated_at"),
                "verdict": _text_cell(record, record.get("verdict_label") or record.get("verdict")),
            }
        )
    table = DataTable(
        title=f"Thiết bị có phạm vi đo trong khoảng ({quantity.get('name_vi')})",
        columns=columns,
        rows=rows,
        total=len(rows),
        note="Phạm vi đo đọc từ dữ kiện QTKĐ đã duyệt của hồ sơ (P2); bấm để mở nguồn.",
    )
    return _payload(
        intent="devices_by_range",
        title=f"Thiết bị theo phạm vi đo — {quantity.get('name_vi') or params.quantity}",
        note=LEDGER_NOTE,
        tables=[table],
        citations=_citations_for_tables(session, [table]),
        total=len(rows),
    )


def resolve_error_trend(session: Session, params: intents.ErrorTrendParams) -> DataPayload:
    history = records_query.device_history(session, serial=params.serial)
    tables = _trend_tables(history, step_code=params.step_code)
    return _payload(
        intent="error_trend",
        title=f"Diễn biến sai số — {_device_title(history['device'])}",
        note=LEDGER_NOTE,
        tables=tables,
        citations=_citations_for_tables(session, tables),
        total=sum(len(table.rows) for table in tables),
    )


_RESOLVERS: dict[str, Any] = {
    "device_history": resolve_device_history,
    "latest_record": resolve_latest_record,
    "records_by_period": resolve_records_by_period,
    "procedure_params": resolve_procedure_params,
    "standards_for": resolve_standards_for,
    "devices_by_range": resolve_devices_by_range,
    "error_trend": resolve_error_trend,
}


def build_data_payload(session: Session, request: Any) -> DataPayload:
    """Chạy intent đã kiểm tham số và trả bảng kèm xuất xứ (P1/P3)."""
    resolver = _RESOLVERS.get(request.intent)
    if resolver is None:  # pragma: no cover - discriminated union đã chặn
        raise ValueError(f"Intent không hỗ trợ: {request.intent}")
    return resolver(session, request.params)


# ── Định tuyến ────────────────────────────────────────────────────────────────


def plan_route(
    question: str,
    classifier: intents.IntentClassifier | None = None,
    *,
    min_confidence: float | None = None,
) -> intents.IntentDecision:
    """Chọn nhánh text/data/mixed; mọi bất định rơi về text."""
    if not intents.intents_enabled():
        return intents.text_decision("router_disabled")
    classifier = classifier or intents.default_classifier()
    try:
        raw = classifier.classify(question)
    except Exception as exc:  # noqa: BLE001 - thất bại an toàn có chủ đích
        logger.warning("Bộ phân loại intent lỗi: %s", exc)
        raw = None
    return intents.decide(raw, min_confidence=min_confidence or 0.0)


# ── Kiểm tra bất biến + serialize ─────────────────────────────────────────────


def untraceable_cells(payload: DataPayload) -> list[str]:
    """Danh sách ô số thiếu tham chiếu xuất xứ — cổng Sprint 9 phải rỗng."""
    problems: list[str] = []
    for table in payload.tables:
        for index, row in enumerate(table.rows):
            for column in table.columns:
                cell = row.get(column.key)
                if cell is None:
                    continue
                if cell.numeric and not cell.provenance:
                    problems.append(f"{table.title}#{index}:{column.key}")
    return problems


def cell_to_dict(cell: Cell) -> dict[str, Any]:
    return {
        "text": cell.text,
        "numeric": cell.numeric,
        "provenance": cell.provenance,
        "device_id": cell.device_id,
        "record_id": cell.record_id,
    }


def table_to_dict(table: DataTable) -> dict[str, Any]:
    return {
        "title": table.title,
        "note": table.note,
        "total": table.total,
        "columns": [{"key": column.key, "label": column.label} for column in table.columns],
        "rows": [{key: cell_to_dict(value) for key, value in row.items()} for row in table.rows],
    }


def payload_to_dict(payload: DataPayload) -> dict[str, Any]:
    return {
        "intent": payload.intent,
        "branch": payload.branch,
        "title": payload.title,
        "note": payload.note,
        "empty": payload.empty,
        "tables": [table_to_dict(table) for table in payload.tables],
        "citations": payload.citations,
    }
