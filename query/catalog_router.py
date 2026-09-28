"""Bộ dựng bảng cho bốn intent danh mục NAS (Pha D2) — chỉ view đã duyệt (P3).

Mỗi resolver đọc danh mục qua ``query/catalogs.py`` rồi lọc không dấu trong Python
(số dòng nhỏ: 8-84). Mỗi ô mang tham chiếu xuất xứ P1 (``extraction_id`` + nguyên
văn dòng nguồn) để cổng "0 ô số không truy được nguồn" luôn đạt; kết quả rỗng trả
payload rỗng kèm ghi chú rõ thay vì ném lỗi.

P2: không tính lại số liệu nguồn, chỉ đọc và định dạng. Hạn kế tiếp của chuẩn mẫu
là giá trị dẫn xuất do tầng ghi tính sẵn (``next_due_*``), ở đây chỉ hiển thị.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from catalogs.text import fold
from query import catalog_intents, catalogs as catalogs_query
from query.table_model import (
    CITATION_CAP,
    Cell,
    Column,
    DataPayload,
    DataTable,
    empty_payload,
    make_payload,
)

CATALOG_NOTE = (
    "Đọc từ danh mục NAS đã duyệt (Biểu 1, 3, 4, 7) — chỉ bản đã duyệt (P3), "
    "mỗi ô bấm để mở dòng nguyên văn."
)
_ROW_LIMIT = 200
_TOKEN_RE = re.compile(r"[\w\-]+", re.UNICODE)

# Cột JSON cần chuẩn hoá: SQLite trả chuỗi, Postgres trả list/dict.
_JSON_COLUMNS: dict[str, tuple[str, ...]] = {
    "lab_standard": ("usage_refs", "inherited"),
    "inspector": ("fields",),
    "procedure_catalog": ("codes", "inherited"),
    "capability": ("parameters", "procedure_codes"),
}

RECOGNITION_LABELS: dict[str, str] = {
    "bo_sung_moi": "Bổ sung mới",
    "mo_rong": "Mở rộng",
    "duy_tri": "Duy trì",
}


def _as_list(value: Any) -> list[Any]:
    """Cột JSON/list: chấp nhận list sẵn có hoặc chuỗi JSON (SQLite)."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _catalog_items(session: Session, kind: str) -> list[dict[str, Any]]:
    """Đọc một danh mục đã duyệt và chuẩn hoá các cột JSON."""
    items, _ = catalogs_query.list_catalog(session, kind, limit=_ROW_LIMIT)
    columns = _JSON_COLUMNS.get(kind, ())
    for item in items:
        for column in columns:
            item[column] = _as_list(item.get(column))
    return items


# ── Tiện ích lọc/tìm không dấu ────────────────────────────────────────────────


def _norm_code(value: str | None) -> str:
    """Mã quy trình so khớp: bỏ dấu, bỏ mọi khoảng trắng (``QTKĐ 1.019 : 2014``)."""
    return re.sub(r"\s+", "", fold(value))


def _query_tokens(value: str | None) -> list[str]:
    return [token for token in _TOKEN_RE.findall(fold(value)) if len(token) >= 2]


def _ref_key(pair: Any) -> str:
    """Khoá so khớp một cặp (sheet, mục) của `usage_refs` — chỉ lấy phần mục."""
    if isinstance(pair, (list, tuple)) and len(pair) >= 2:
        return _norm_code(str(pair[1]))
    return _norm_code(str(pair))


def _standard_score(item: dict[str, Any], tokens: list[str], needle_compact: str = "") -> int:
    name = fold(item.get("name"))
    model = fold(item.get("model"))
    serial = fold(item.get("serial"))
    chars = fold(item.get("characteristics"))
    score = 0
    # Ký hiệu/model nhiều từ: khớp cụm đã gộp khoảng trắng ("Fluke 5624-20-B").
    for value in (model, serial):
        compact = re.sub(r"\s+", "", value)
        if needle_compact and compact and needle_compact == compact:
            score += 5
    for token in tokens:
        if token == model or token == serial:
            score += 3
        elif token in name:
            score += 2
        elif token in chars or token in model or token in serial:
            score += 1
    return score


def _filter_standards(
    items: list[dict[str, Any]], query: str | None, usage_ref: str | None
) -> list[dict[str, Any]]:
    if usage_ref:
        needle = _norm_code(usage_ref)
        items = [
            item
            for item in items
            if any(_ref_key(pair) == needle for pair in (item.get("usage_refs") or []))
        ]
    if query:
        tokens = _query_tokens(query)
        needle_compact = re.sub(r"\s+", "", fold(query))
        scored = [
            (score, item)
            for item in items
            if (score := _standard_score(item, tokens, needle_compact)) > 0
        ]
        if scored:
            best = max(score for score, _ in scored)
            items = [item for score, item in scored if score == best]
        else:
            items = []
    return items


def _match_code(item: dict[str, Any], code: str) -> bool:
    needle = _norm_code(code)
    if not needle or len(needle) < 3:
        return False
    candidates = [_norm_code(item.get("code_text"))]
    candidates += [
        _norm_code(entry.get("normalized")) for entry in (item.get("codes") or [])
    ]
    if item.get("procedure_number"):
        candidates.append(_norm_code(str(item["procedure_number"])))
    return any(candidate and (needle == candidate or needle in candidate or candidate in needle)
               for candidate in candidates)


def _procedure_haystack(item: dict[str, Any]) -> str:
    codes = " ".join(entry.get("normalized") or "" for entry in (item.get("codes") or []))
    return fold(
        " ".join(
            part or ""
            for part in (
                item.get("code_text"),
                item.get("title"),
                item.get("group_title"),
                item.get("group_code"),
                item.get("issuer"),
                codes,
            )
        )
    )


def _capability_haystack(item: dict[str, Any]) -> str:
    codes = " ".join(entry.get("normalized") or "" for entry in (item.get("procedure_codes") or []))
    return fold(
        " ".join(
            part or ""
            for part in (
                item.get("name"),
                item.get("group_title"),
                item.get("group_code"),
                codes,
                " ".join(item.get("parameters") or []),
            )
        )
    )


# ── Ô + trích dẫn ─────────────────────────────────────────────────────────────


def _cell(item: dict[str, Any], field_name: str, value: Any, *, numeric: bool = False) -> Cell:
    """Ô danh mục: mọi ô đều mang tham chiếu ``extraction`` + nguyên văn dòng nguồn."""
    ref = item.get("provenance") or {}
    extraction_id = ref.get("extraction_id")
    provenance = None
    if extraction_id is not None:
        provenance = {
            "kind": "extraction",
            "id": extraction_id,
            "field": field_name,
            "quote": item.get("quote"),
        }
    return Cell(text="—" if value in (None, "") else str(value), numeric=numeric, provenance=provenance)


def _catalog_citations(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Trích dẫn theo TỪNG dòng nguồn (một extraction giữ nhiều dòng danh mục)."""
    citations: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for item in items:
        ref = item.get("provenance") or {}
        key = (ref.get("extraction_id"), item.get("quote"))
        if ref.get("extraction_id") is None or key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "kind": "extraction",
                "file_stem": ref.get("file_stem"),
                "document_id": ref.get("document_id"),
                "display_name": ref.get("display_name"),
                "section_path": None,
                "chunk_id": None,
                "quote": item.get("quote"),
                "value_text": item.get("quote"),
            }
        )
        if len(citations) >= CITATION_CAP:
            break
    return citations


def _build(
    *,
    intent: str,
    title: str,
    table_title: str,
    columns: list[Column],
    rows: list[dict[str, Cell]],
    items: list[dict[str, Any]],
    empty_note: str,
) -> DataPayload:
    if not rows:
        return empty_payload(intent, title, empty_note)
    table = DataTable(title=table_title, columns=columns, rows=rows, total=len(rows))
    return make_payload(
        intent=intent,
        title=title,
        note=CATALOG_NOTE,
        tables=[table],
        citations=_catalog_citations(items),
        total=len(rows),
    )


# ── Bốn resolver ──────────────────────────────────────────────────────────────


def resolve_lab_standard_lookup(
    session: Session, params: catalog_intents.LabStandardLookupParams
) -> DataPayload:
    items = _catalog_items(session, "lab_standard")
    items = _filter_standards(items, params.query, params.usage_ref)
    columns = [
        Column("ord", "TT"),
        Column("name", "Tên chuẩn mẫu"),
        Column("model", "Ký hiệu"),
        Column("serial", "Số hiệu"),
        Column("characteristics", "Đặc tính đo lường"),
        Column("interval_text", "Chu kỳ KĐ/HC"),
        Column("last_cal_text", "Lần KĐ/HC gần nhất"),
        Column("next_due_text", "Hạn kế tiếp (ước tính)"),
        Column("usage_text", "Lĩnh vực sử dụng"),
    ]
    rows = [
        {
            "ord": _cell(item, "ord", item.get("ord"), numeric=True),
            "name": _cell(item, "name", item.get("name")),
            "model": _cell(item, "model", item.get("model")),
            "serial": _cell(item, "serial", item.get("serial")),
            "characteristics": _cell(item, "characteristics", item.get("characteristics")),
            "interval_text": _cell(item, "interval_text", item.get("interval_text")),
            "last_cal_text": _cell(item, "last_cal_text", item.get("last_cal_text")),
            "next_due_text": _cell(item, "next_due_text", _next_due_text(item)),
            "usage_text": _cell(item, "usage_text", item.get("usage_text")),
        }
        for item in items
    ]
    return _build(
        intent="lab_standard_lookup",
        title="Danh mục chuẩn mẫu",
        table_title="Chuẩn mẫu / PTĐ / PTTN đã duyệt",
        columns=columns,
        rows=rows,
        items=items,
        empty_note="Không tìm thấy chuẩn mẫu đã duyệt khớp yêu cầu.",
    )


def _next_due_text(item: dict[str, Any]) -> str | None:
    if not item.get("next_due_derived"):
        return None
    year, month = item.get("next_due_year"), item.get("next_due_month")
    if not year or not month:
        return None
    return f"{int(month):02d}/{int(year)} (ước tính)"


def resolve_inspector_lookup(
    session: Session, params: catalog_intents.InspectorLookupParams
) -> DataPayload:
    items = _catalog_items(session, "inspector")
    if params.name:
        needle = fold(params.name)
        items = [item for item in items if needle and needle in fold(item.get("name"))]
    if params.field:
        needle = fold(params.field)
        items = [
            item
            for item in items
            if needle and any(needle in fold(field) for field in (item.get("fields") or []))
        ]
    columns = [
        Column("ord", "TT"),
        Column("name", "Họ và tên"),
        Column("birth_year", "Năm sinh"),
        Column("rank", "Cấp bậc"),
        Column("position", "Chức vụ"),
        Column("education", "Trình độ"),
        Column("specialization", "Chuyên ngành"),
        Column("fields", "Lĩnh vực chứng nhận"),
        Column("card_no", "Số thẻ"),
        Column("card_date", "Ngày cấp"),
    ]
    rows = [
        {
            "ord": _cell(item, "ord", item.get("ord"), numeric=True),
            "name": _cell(item, "name", item.get("name")),
            "birth_year": _cell(item, "birth_year", item.get("birth_year"), numeric=True),
            "rank": _cell(item, "rank", item.get("rank")),
            "position": _cell(item, "position", item.get("position")),
            "education": _cell(item, "education", item.get("education")),
            "specialization": _cell(item, "specialization", item.get("specialization")),
            "fields": _cell(item, "fields", "; ".join(item.get("fields") or [])),
            "card_no": _cell(item, "card_no", item.get("card_no")),
            "card_date": _cell(item, "card_date", _date_text(item.get("card_date"))),
        }
        for item in items
    ]
    return _build(
        intent="inspector_lookup",
        title="Danh sách kiểm định viên",
        table_title="Kiểm định viên đã duyệt",
        columns=columns,
        rows=rows,
        items=items,
        empty_note="Không tìm thấy kiểm định viên đã duyệt khớp yêu cầu.",
    )


def _date_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    if "T" in text:
        text = text.split("T", 1)[0]
    parts = text.split("-")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return text


def resolve_procedure_catalog_lookup(
    session: Session, params: catalog_intents.ProcedureCatalogLookupParams
) -> DataPayload:
    items = _catalog_items(session, "procedure_catalog")
    if params.code:
        items = [item for item in items if _match_code(item, params.code)]
    if params.keyword:
        needle = fold(params.keyword)
        items = [item for item in items if needle and needle in _procedure_haystack(item)]
    if params.group:
        needle = fold(params.group)
        items = [
            item for item in items if needle and needle in fold(item.get("group_title") or "")
        ]
    columns = [
        Column("ord", "TT"),
        Column("group_title", "Nhóm lĩnh vực"),
        Column("code_text", "Số hiệu"),
        Column("title", "Tên tiêu chuẩn / quy trình"),
        Column("issuer", "Cấp ban hành"),
        Column("year_issued", "Năm"),
    ]
    rows = [
        {
            "ord": _cell(item, "ord", item.get("ord"), numeric=True),
            "group_title": _cell(item, "group_title", item.get("group_title")),
            "code_text": _cell(item, "code_text", item.get("code_text")),
            "title": _cell(item, "title", item.get("title")),
            "issuer": _cell(item, "issuer", item.get("issuer")),
            "year_issued": _cell(item, "year_issued", item.get("year_issued"), numeric=True),
        }
        for item in items
    ]
    return _build(
        intent="procedure_catalog_lookup",
        title="Danh mục tiêu chuẩn, quy trình",
        table_title="Tiêu chuẩn / quy trình đã duyệt",
        columns=columns,
        rows=rows,
        items=items,
        empty_note="Không tìm thấy tiêu chuẩn/quy trình đã duyệt khớp yêu cầu.",
    )


def resolve_capability_lookup(
    session: Session, params: catalog_intents.CapabilityLookupParams
) -> DataPayload:
    items = _catalog_items(session, "capability")
    needle = fold(params.keyword)
    items = [item for item in items if needle and needle in _capability_haystack(item)]
    columns = [
        Column("ord", "TT"),
        Column("group_title", "Nhóm lĩnh vực"),
        Column("name", "Đại lượng / trang bị"),
        Column("parameters", "Tham số đo lường"),
        Column("procedure_codes", "Quy trình áp dụng"),
        Column("inspector_count", "Số KĐV"),
        Column("recognition", "Hình thức công nhận"),
    ]
    rows = [
        {
            "ord": _cell(item, "ord", item.get("ord"), numeric=True),
            "group_title": _cell(item, "group_title", item.get("group_title")),
            "name": _cell(item, "name", item.get("name")),
            "parameters": _cell(item, "parameters", "; ".join(item.get("parameters") or [])),
            "procedure_codes": _cell(
                item,
                "procedure_codes",
                ", ".join(
                    entry.get("normalized") or entry.get("raw") or ""
                    for entry in (item.get("procedure_codes") or [])
                ),
            ),
            "inspector_count": _cell(
                item, "inspector_count", item.get("inspector_count"), numeric=True
            ),
            "recognition": _cell(
                item,
                "recognition",
                RECOGNITION_LABELS.get(item.get("recognition") or "", item.get("recognition")),
            ),
        }
        for item in items
    ]
    return _build(
        intent="capability_lookup",
        title="Lĩnh vực kiểm định, hiệu chuẩn được công nhận",
        table_title="Lĩnh vực công nhận đã duyệt",
        columns=columns,
        rows=rows,
        items=items,
        empty_note="Không tìm thấy lĩnh vực công nhận đã duyệt khớp yêu cầu.",
    )


CATALOG_RESOLVERS: dict[str, Any] = {
    "lab_standard_lookup": resolve_lab_standard_lookup,
    "inspector_lookup": resolve_inspector_lookup,
    "procedure_catalog_lookup": resolve_procedure_catalog_lookup,
    "capability_lookup": resolve_capability_lookup,
}
