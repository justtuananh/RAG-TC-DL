"""Mô hình bảng kết quả + định dạng + xuất xứ dùng chung cho chat số liệu (spec §8).

Tách khỏi ``query/router.py`` để nhiều bộ dựng bảng (hồ sơ/số liệu đo và danh mục
NAS) dùng chung đúng một mô hình. Thuần dữ liệu, dễ serialize; không truy vấn gì
ngoài các view đã duyệt khi dựng trích dẫn (P3).

Bất biến:
- P1: mỗi ô số kèm tham chiếu ``{kind, id, field}``; ô số thiếu nguồn bị để trống.
- P2: không tính lại số liệu nguồn; chỉ đọc và định dạng.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from query import provenance as provenance_query
from query import units as units_query

CITATION_CAP = 12


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


def _range_text(minimum: Any, maximum: Any, unit: dict[str, Any] | None) -> str:
    """Khoảng giá trị: ``minimum``/``maximum`` theo SI, hiển thị theo ``unit`` của dữ kiện."""
    has_min = minimum is not None
    has_max = maximum is not None
    if not has_min and not has_max:
        return "—"
    low, high = units_query.from_si(minimum, unit), units_query.from_si(maximum, unit)
    suffix = f" {unit['code']}" if unit else ""
    if has_min and has_max:
        return f"{_num_text(low, digits=9)} – {_num_text(high, digits=9)}{suffix}"
    return f"{_num_text(low if has_min else high, digits=9)}{suffix}"


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


def _num_cell(
    record: dict[str, Any],
    field_name: str,
    value: Any,
    *,
    digits: int = 3,
    unit: str | None = None,
) -> Cell:
    """Ô số: CHỈ hiện con số khi có tham chiếu xuất xứ; thiếu nguồn → để trống.

    Đây là hàng rào P1 ở tầng trình bày: không bao giờ đưa ra một con số không
    truy được về nguyên văn (spec §8 cổng: không có số không truy được nguồn).
    ``unit`` là hậu tố đơn vị (ví dụ "%") gắn liền con số cùng dòng.
    """
    ref = _prov_of(record, field_name)
    if ref is None:
        return Cell(text="—", numeric=False)
    text = _num_text(value, digits)
    if unit and text != "—":
        text = f"{text} {unit}"
    return Cell(
        text=text,
        numeric=True,
        provenance=ref,
        device_id=record.get("device_id"),
        record_id=record.get("id"),
    )


def _date_cell(record: dict[str, Any], field_name: str) -> Cell:
    return _text_cell(record, _date_text(record.get(field_name)), field_name=field_name)


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


# ── Dựng payload ──────────────────────────────────────────────────────────────

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

LEDGER_NOTE = "Đọc từ sổ cái hồ sơ đã duyệt — không phải trích từ tài liệu QTKĐ."


def make_payload(
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


def empty_payload(intent: str, title: str, note: str) -> DataPayload:
    return DataPayload(
        intent=intent, branch="data", title=title, note=note, tables=[], citations=[], empty=True
    )


# Giữ tên cũ trong ``query.router`` cho tương thích nội bộ.
_payload = make_payload
_empty_payload = empty_payload


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
