"""Cụm từ dùng chung cho câu trả lời tất định của nhánh số liệu sổ cái.

Mọi câu trả lời biên bản (tra một biên bản, tổng hợp, cực trị) được ghép từ NGUYÊN
VĂN ô sổ cái bằng các hàm ở đây, không qua LLM: cùng một cách gọi thiết bị, cùng một
cách nêu giá trị kèm đơn vị, cùng một cách đối chiếu mức cho phép. Không tính ra số
mới (P2): chỉ so giá trị với mức cho phép để chọn chữ, hoặc dùng ``within_limit`` của
bộ đọc khi mức áp cho sai số; chỉ nói "không đạt" khi kết luận biên bản cũng vậy.
"""

from __future__ import annotations

import re
from typing import Any

from query.record_fields import load_cells
from query.table_model import _date_text
from records.columns import role_for_column, unit_from_header

# "Kết quả, s Cùng chiều kim đồng hồ": nhóm cột "Kết quả" (đơn vị s), cột con "Cùng chiều…".
_READING_RE = re.compile(r"^(?P<group>[^,]+),\s*(?P<unit>\S+)\s+(?P<sub>.+)$")
# Nhãn cột chung chung: dùng nhãn dòng thay vì "giá trị xác định 2,3".
_GENERIC_LABELS = frozenset({"", "xác định", "đo", "đo được"})
# Dấu so sánh đầu mức cho phép; ">=" viết ASCII là "≥", không phải ">" (cùng quy ước
# ``records.columns._LEADING_COMPARATOR_RE``).
_BOUND_RE = re.compile(r"^\s*(<=|>=|=<|=>|[<>≤≥])")
_BOUND_ALIASES = {"<=": "≤", "=<": "≤", ">=": "≥", "=>": "≥"}
_LOWER_BOUND = ("≥", ">")
_UPPER_BOUND = ("≤", "<")
# Lý do trong kết luận: "Không đạt yêu cầu kỹ thuật đo lường (độ kín: ...)".
_REASON_RE = re.compile(r"\(([^()]+)\)\s*\.?\s*$")
VERDICT_SHORT = {"dat": "đạt", "khong_dat": "không đạt"}


def lower_first(text: str) -> str:
    """Hạ chữ đầu của nhãn thường ("Phạm vi đo" → "phạm vi đo"); giữ ký hiệu ("U(p)",
    "A0", "QTKĐ") vì chữ thứ hai không phải chữ thường."""
    if not text or (len(text) > 1 and not text[1].islower()):
        return text
    return text[:1].lower() + text[1:]


def upper_first(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def clean_value(value: Any) -> str:
    """Nguyên văn ô, bỏ dấu ";" cuối dòng của mẫu biên bản ("(1 đến 60) MPa;")."""
    return str(value if value not in (None, "") else "—").strip().rstrip(";").strip()


def strip_unit(column: str, unit: str | None) -> str:
    text = " ".join(column.split())
    if unit:
        for suffix in (f", ({unit})", f", {unit}", f",{unit}", f"({unit})"):
            if text.endswith(suffix):
                return text[: -len(suffix)].strip(" ,")
    return text


def with_unit(value: str, unit: str | None) -> str:
    value = value.strip()
    if not unit or value.endswith(unit):
        return value
    return f"{value} {unit}"


def date_text(value: Any) -> str:
    return _date_text(value)


def device_name(record: dict) -> str:
    """ "áp kế píttông tiêu chuẩn CPB5800 số hiệu 1A0043219" (bỏ phần sổ cái thiếu)."""
    parts = [
        lower_first(record.get("device_type_name") or "") or "thiết bị",
        record.get("model_code") or "",
        f"số hiệu {record['serial_no']}" if record.get("serial_no") else "",
    ]
    return " ".join(part for part in parts if part)


def cert(record: dict) -> str:
    return str(record.get("cert_no") or record["id"])


def record_head(record: dict) -> str:
    """ "Biên bản 020/2026 của áp kế ... số hiệu 1A0043219, ngày 19/05/2026"."""
    return (
        f"Biên bản {cert(record)} của {device_name(record)}, "
        f"ngày {date_text(record.get('calibrated_at'))}"
    )


def verdict_reason(verdict_text: str | None) -> str | None:
    match = _REASON_RE.search(verdict_text or "")
    return match[1].strip() if match else None


def verdict_short(record: dict, verdict_text: str | None = None) -> str:
    """ "đạt" / "không đạt (thời gian quay tự do dưới 180 s)" (lý do nguyên văn kết luận)."""
    label = VERDICT_SHORT.get(record.get("verdict") or "", "chưa rõ kết luận")
    reason = verdict_reason(verdict_text) if record.get("verdict") == "khong_dat" else None
    return f"{label} ({reason})" if reason else label


def join_vi(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} và {items[-1]}"


# ── Một dòng số liệu đo ──────────────────────────────────────────────────────


def filled_cells(point: dict) -> list[tuple[str, str]]:
    return [
        (str(cell.get("column") or ""), str(cell.get("text") or "").strip())
        for cell in load_cells(point.get("cells"))
        if str(cell.get("text") or "").strip()
    ]


def first_cell(cells: list[tuple[str, str]], role: str) -> tuple[str, str] | None:
    return next((cell for cell in cells if role_for_column(cell[0]) == role), None)


def cell_clause(column: str, value: str) -> str:
    """ "Áp suất khí quyển, hPa" + "1015,99" → "áp suất khí quyển 1015,99 hPa"."""
    unit = unit_from_header(column)
    return f"{lower_first(strip_unit(column, unit))} {with_unit(value, unit)}"


def _measured_label(
    column: str, unit: str | None, point: dict, fallback: str
) -> tuple[str, str, bool]:
    """(nhãn, đơn vị, nhãn từ cột?): "Giá trị trung bình, s" → "trung bình";
    "Giá trị xác định" → nhãn dòng.

    Nhãn dòng có thể mang đơn vị ("Độ giảm áp suất sau 5 min tại 600 kPa, kPa") khi cột
    giá trị không ghi đơn vị.
    """
    label = strip_unit(column, unit).casefold()
    if label.startswith("giá trị"):
        label = label[len("giá trị") :].strip()
    if label not in _GENERIC_LABELS:
        return label, unit or "", True
    row_label = str(point.get("label") or "").strip() or fallback
    row_unit = unit or unit_from_header(row_label) or ""
    return lower_first(strip_unit(row_label, row_unit or None)), row_unit, False


def _readings(cells: list[tuple[str, str]], unit: str | None) -> list[str]:
    """Các lần đọc cùng đơn vị đã ra giá trị chính ("cùng chiều kim đồng hồ 157,3 s")."""
    readings = []
    for column, value in cells:
        match = _READING_RE.match(" ".join(column.split()))
        if role_for_column(column) is None and match and match["unit"] == unit:
            readings.append(f"{lower_first(match['sub'])} {with_unit(value, unit)}")
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


def _limit_phrase(
    point: dict, record: dict, limit: str, within: bool | None, *, conclude: bool
) -> str:
    """Đối chiếu mức cho phép; ``conclude`` thêm "nên đạt / nên không đạt"."""
    if within:
        return f", trong mức cho phép {limit}" + (" nên đạt" if conclude else "")
    if within is False and record.get("verdict") == "khong_dat":
        bound = _bound(point.get("limit_text"))
        if bound in _LOWER_BOUND:
            phrase = f", thấp hơn mức cho phép {limit}"
        elif bound in _UPPER_BOUND:
            phrase = f", vượt mức cho phép {limit}"
        else:
            phrase = f", ngoài mức cho phép {limit}"
        return phrase + (" nên không đạt" if conclude else "")
    return f", mức cho phép {limit}"


def has_measured(point: dict) -> bool:
    return first_cell(filled_cells(point), "measured") is not None


def point_clause(
    record: dict,
    point: dict,
    table_label: str,
    *,
    conclude: bool = True,
    subject: str | None = None,
) -> str:
    """ "trung bình 154,6 s (cùng chiều … 157,3 s; …), thấp hơn mức cho phép ≥ 180 s nên …".

    ``subject`` ("thời gian quay tự do") đứng trước nhãn lấy từ tiêu đề cột ("trung
    bình") để câu đứng riêng vẫn rõ đại lượng; nhãn lấy từ chính dòng ("độ giảm áp suất
    sau 5 min…") đã đủ nghĩa nên không thêm.
    """
    cells = filled_cells(point)
    measured = first_cell(cells, "measured")
    if measured is None:
        return f"{lower_first(table_label)} {point.get('measured_text') or '—'}"
    unit = unit_from_header(measured[0])
    label, unit, from_column = _measured_label(measured[0], unit, point, table_label)
    if subject and from_column:
        label = f"{subject} {label}"
    clause = f"{label} {with_unit(measured[1], unit or None)}"
    readings = _readings(cells, unit or None)
    if readings:
        clause += f" ({'; '.join(readings)})"
    limit = first_cell(cells, "limit")
    if limit is None:
        return clause
    limit_unit = unit_from_header(limit[0])
    error = first_cell(cells, "error")
    if error is not None:
        # Mức cho phép áp cho SAI SỐ (bộ đọc ghi ``within_limit`` = |sai số| ≤ |mức|),
        # không áp cho giá trị đo: nêu sai số rồi mới so.
        error_unit = unit_from_header(error[0]) or limit_unit
        clause += f", sai số {with_unit(error[1], error_unit)}"
        within = None if point.get("within_limit") is None else bool(point["within_limit"])
        limit_text = with_unit(limit[1], limit_unit or error_unit)
    else:
        within = _measured_within(point, limit_unit in (unit or None, None))
        limit_text = with_unit(limit[1], limit_unit or unit or None)
    return clause + _limit_phrase(point, record, limit_text, within, conclude=conclude)


def row_clause(point: dict, names: list[str], asked: frozenset[str]) -> str:
    """Một dòng bảng không có giá trị đo chính (vd. Bảng A.5): cột danh nghĩa + cột được hỏi.

    ``names`` là thứ tự cột của bảng hiển thị; ``asked`` là cột câu hỏi nhắc tới. Không
    cột nào được hỏi thì nêu mọi cột có chữ (trừ STT).
    """
    cells = dict(filled_cells(point))
    nominal = next((name for name in names if role_for_column(name) == "nominal"), None)
    chosen = [name for name in names if name in asked and name != nominal]
    if not chosen:
        chosen = [name for name in names if name != nominal and role_for_column(name) != "ord"]
    parts = [cell_clause(name, cells[name]) for name in chosen if cells.get(name)]
    if nominal and cells.get(nominal):
        return f"tại {cell_clause(nominal, cells[nominal])}: {'; '.join(parts)}"
    return "; ".join(parts)
