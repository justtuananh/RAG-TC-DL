"""Câu trả lời một dòng cho câu hỏi cực trị trên sổ cái ("Biên bản nào ... thấp nhất").

Người hỏi cần biết biên bản nào và giá trị bao nhiêu, không phải cả sổ cái:

    Biên bản 020/2026 của áp kế píttông tiêu chuẩn CPB5800 số hiệu 1A0043219, ngày
    19/05/2026: trung bình 154,6 s (cùng chiều kim đồng hồ 157,3 s; ngược chiều kim
    đồng hồ 151,9 s), thấp hơn mức cho phép ≥ 180 s nên không đạt.

Câu được dựng tất định (không qua LLM) từ NGUYÊN VĂN các ô của dòng thắng; bảng một
dòng đi kèm vẫn giữ xuất xứ từng ô (P1). Không tính ra số mới (P2): chỉ so giá trị
với mức cho phép để chọn chữ (hoặc dùng ``within_limit`` của bộ đọc khi mức áp cho sai
số), và chỉ nói "không đạt" khi kết luận biên bản cũng là không đạt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from query.record_fields import load_cells
from query.table_model import DataTable, _date_text
from records.columns import role_for_column, unit_from_header

# "Kết quả, s Cùng chiều kim đồng hồ": nhóm cột "Kết quả" (đơn vị s), cột con "Cùng chiều…".
_READING_RE = re.compile(r"^(?P<group>[^,]+),\s*(?P<unit>\S+)\s+(?P<sub>.+)$")
# Nhãn cột chung chung: dùng nhãn dòng thay vì "giá trị xác định 2,3".
_GENERIC_LABELS = frozenset({"", "xác định", "đo", "đo được"})
# Dấu so sánh đầu mức cho phép; "&gt;=" viết ASCII là "≥", không phải "&gt;" (cùng quy ước
# ``records.columns._LEADING_COMPARATOR_RE``).
_BOUND_RE = re.compile(r"^\s*(<=|>=|=<|=>|[<>≤≥])")
_BOUND_ALIASES = {"<=": "≤", "=<": "≤", ">=": "≥", "=>": "≥"}
_LOWER_BOUND = ("≥", ">")
_UPPER_BOUND = ("≤", "<")


@dataclass
class RankGroup:
    """Kết quả cực trị của MỘT QTKĐ: bảng các dòng thắng và câu trả lời cho từng dòng."""

    table: DataTable
    procedure: str | None
    label: str
    order: str
    sentences: list[str] = field(default_factory=list)


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def _strip_unit(column: str, unit: str | None) -> str:
    text = " ".join(column.split())
    if unit:
        for suffix in (f", {unit}", f",{unit}", f"({unit})"):
            if text.endswith(suffix):
                return text[: -len(suffix)].strip(" ,")
    return text


def _with_unit(value: str, unit: str | None) -> str:
    value = value.strip()
    if not unit or value.endswith(unit):
        return value
    return f"{value} {unit}"


def _device(record: dict) -> str:
    """ "của áp kế píttông tiêu chuẩn CPB5800 số hiệu 1A0043219" (bỏ phần sổ cái thiếu)."""
    parts = [
        _lower_first(record.get("device_type_name") or "") or "thiết bị",
        record.get("model_code") or "",
        f"số hiệu {record['serial_no']}" if record.get("serial_no") else "",
    ]
    return " của " + " ".join(part for part in parts if part)


def _head(record: dict) -> str:
    cert = record.get("cert_no") or str(record["id"])
    return f"Biên bản {cert}{_device(record)}, ngày {_date_text(record.get('calibrated_at'))}"


def _filled(point: dict) -> list[tuple[str, str]]:
    return [
        (str(cell.get("column") or ""), str(cell.get("text") or "").strip())
        for cell in load_cells(point.get("cells"))
        if str(cell.get("text") or "").strip()
    ]


def _first(cells: list[tuple[str, str]], role: str) -> tuple[str, str] | None:
    return next((cell for cell in cells if role_for_column(cell[0]) == role), None)


def _measured_label(column: str, unit: str | None, point: dict, fallback: str) -> str:
    """ "Giá trị trung bình, s" → "trung bình"; "Giá trị xác định" → nhãn dòng."""
    label = _strip_unit(column, unit).casefold()
    if label.startswith("giá trị"):
        label = label[len("giá trị") :].strip()
    if label not in _GENERIC_LABELS:
        return label
    return _lower_first(point.get("label") or fallback)


def _readings(cells: list[tuple[str, str]], unit: str | None) -> list[str]:
    """Các lần đọc cùng đơn vị đã ra giá trị chính ("cùng chiều kim đồng hồ 157,3 s")."""
    readings = []
    for column, value in cells:
        match = _READING_RE.match(" ".join(column.split()))
        if role_for_column(column) is None and match and match["unit"] == unit:
            readings.append(f"{_lower_first(match['sub'])} {_with_unit(value, unit)}")
    return readings


def _bound(limit_text: str | None) -> str | None:
    match = _BOUND_RE.match(limit_text or "")
    return _BOUND_ALIASES.get(match[1], match[1]) if match else None


def _measured_within(point: dict, same_unit: bool) -> bool | None:
    """So giá trị đo với mức cho phép (chỉ khi cùng đơn vị và mức có dấu so sánh)."""
    measured, limit = point.get("measured_value"), point.get("limit_value")
    bound = _bound(point.get("limit_text"))
    if not same_unit or measured is None or limit is None:
        return None
    if bound in _LOWER_BOUND:
        return measured >= limit if bound == "≥" else measured > limit
    if bound in _UPPER_BOUND:
        return measured <= limit if bound == "≤" else measured < limit
    return None


def _limit_phrase(point: dict, record: dict, limit: str, within: bool | None) -> str:
    if within:
        return f", trong mức cho phép {limit}"
    if within is False and record.get("verdict") == "khong_dat":
        bound = _bound(point.get("limit_text"))
        if bound in _LOWER_BOUND:
            return f", thấp hơn mức cho phép {limit} nên không đạt"
        if bound in _UPPER_BOUND:
            return f", vượt mức cho phép {limit} nên không đạt"
        return f", ngoài mức cho phép {limit} nên không đạt"
    return f", mức cho phép {limit}"


def point_sentence(record: dict, point: dict, table_label: str) -> str:
    """Câu trả lời cho một dòng số liệu đo thắng cực trị."""
    cells = _filled(point)
    measured = _first(cells, "measured")
    if measured is None:
        value = point.get("measured_text") or "—"
        return f"{_head(record)}: {_lower_first(table_label)} {value}."
    unit = unit_from_header(measured[0])
    label = _measured_label(measured[0], unit, point, table_label)
    sentence = f"{_head(record)}: {label} {_with_unit(measured[1], unit)}"
    readings = _readings(cells, unit)
    if readings:
        sentence += f" ({'; '.join(readings)})"
    limit = _first(cells, "limit")
    if limit is None:
        return sentence + "."
    limit_unit = unit_from_header(limit[0])
    error = _first(cells, "error")
    if error is not None:
        # Mức cho phép áp cho SAI SỐ (bộ đọc ghi ``within_limit`` = |sai số| ≤ |mức|),
        # không áp cho giá trị đo: nêu sai số rồi mới so.
        error_unit = unit_from_header(error[0]) or limit_unit
        sentence += f", sai số {_with_unit(error[1], error_unit)}"
        within = None if point.get("within_limit") is None else bool(point["within_limit"])
        limit_text = _with_unit(limit[1], limit_unit or error_unit)
    else:
        within = _measured_within(point, limit_unit in (unit, None))
        limit_text = _with_unit(limit[1], limit_unit or unit)
    return sentence + _limit_phrase(point, record, limit_text, within) + "."


def field_sentence(record: dict, row: dict, label: str, related: list[tuple[str, Any]]) -> str:
    """Câu trả lời cho một trường đầu mục thắng cực trị (kèm trường đi kèm, vd. U(p))."""
    value = str(row.get("value_text") or "—").strip().rstrip(";")
    sentence = f"{_head(record)}: {_lower_first(label)} {value}"
    extras = [
        f"{related_label} {str(related_row['value_text']).strip().rstrip(';')}"
        for related_label, related_row in related
        if related_row is not None and related_row.get("value_text")
    ]
    if extras:
        sentence += f" ({'; '.join(extras)})"
    return sentence + "."


def extreme_answer(groups: list[RankGroup]) -> str:
    """Ghép câu trả lời: một dòng thắng → một câu; đồng hạng / nhiều QTKĐ → danh sách."""
    if len(groups) == 1 and len(groups[0].sentences) == 1:
        return groups[0].sentences[0]
    if len(groups) == 1:
        group = groups[0]
        lines = [f"- {sentence}" for sentence in group.sentences]
        lead = f"Có {len(lines)} biên bản cùng {_lower_first(group.label)} {group.order}:"
        return "\n".join([lead, "", *lines])
    lines = [
        f"- **QTKĐ {group.procedure}**{' (đồng hạng)' if len(group.sentences) > 1 else ''}: "
        f"{sentence}"
        for group in groups
        for sentence in group.sentences
    ]
    return "\n".join(["Mỗi QTKĐ so riêng, không so chéo quy trình:", "", *lines])
