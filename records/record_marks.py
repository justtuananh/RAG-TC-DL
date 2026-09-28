"""Trường hồ sơ không nằm ở dạng ``Nhãn: giá trị`` của Phụ lục A (spec §5.5).

Biên bản thật ghi ba loại thông tin mà bộ ánh xạ nhãn không bắt được:

- dòng kết luận ``"4. Kết luận: Đạt yêu cầu kỹ thuật đo lường"``;
- ô đánh dấu ``☒ Đạt / ☐ Không đạt`` (Word dùng ký tự Unicode, Excel hay dùng font
  Wingdings với mã riêng ``\\uf0fe``/``\\uf0a3``);
- tên người ký nằm DƯỚI tiêu đề chữ ký (``KIỂM ĐỊNH VIÊN`` ... ``Phạm Văn Hà``).

Hàm ở đây làm việc trên lưới ô thuần (danh sách dòng), không phụ thuộc định dạng
tệp. Không đoán: không có dấu hiệu rõ thì không sinh trường.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from knowledge import vnnum
from records.types import FieldDraft

Grid = list[list[str]]

CONCLUSION_LABEL = "Kết luận"
_CHECKED = "☒☑■✔✓"
_UNCHECKED = "☐□"
_BOXES = _CHECKED + _UNCHECKED
_MARK_BEFORE_RE = re.compile(rf"([{_BOXES}])\s*([^{_BOXES}]+)")
_MARK_AFTER_RE = re.compile(rf"([^{_BOXES}]+?)\s*([{_BOXES}])")
_CONCLUSION_RE = re.compile(
    r"^(?:(?:\d+|[IVX]+)[.)]\s*)?Kết\s+luận\s*:\s*(?P<value>\S.*)$", re.IGNORECASE | re.DOTALL
)
_PARENTHESES_RE = re.compile(r"\([^()]*\)")
# Tiêu đề chữ ký → nhãn trường (khớp alias ``inspector_name``/``reviewer_name``).
_SIGNATURE_TITLES = {
    "kiểm định viên": "Kiểm định viên",
    "người kiểm định": "Người kiểm định",
    "người thực hiện": "Người thực hiện",
    "người kiểm soát": "Người kiểm soát",
    "người soát lại": "Người soát lại",
    "người duyệt": "Người duyệt",
}
_SIGNATURE_LOOKAHEAD_ROWS = 8


@dataclass(frozen=True)
class Mark:
    """Một ô đánh dấu: nhãn cạnh ô và trạng thái đã chọn."""

    label: str
    checked: bool
    quote: str


def _clean(text: str) -> str:
    return vnnum.normalize_spaces(text or "").strip()


def marks_in_text(text: str) -> list[Mark]:
    """Tách các ô đánh dấu trong một chuỗi; dấu đứng trước hoặc sau nhãn."""
    cleaned = _clean(text)
    if not any(char in _BOXES for char in cleaned):
        return []
    before = cleaned[0] in _BOXES
    pattern = _MARK_BEFORE_RE if before else _MARK_AFTER_RE
    marks: list[Mark] = []
    for match in pattern.finditer(cleaned):
        box, label = (
            (match.group(1), match.group(2)) if before else (match.group(2), match.group(1))
        )
        label = label.strip(" ;,.:")
        if label:
            marks.append(Mark(label=label, checked=box in _CHECKED, quote=cleaned))
    return marks


def _all_cells(grids: list[Grid]):
    for grid in grids:
        for row_index, row in enumerate(grid):
            for col_index, cell in enumerate(row):
                if cell and cell.strip():
                    yield grid, row_index, col_index, cell


def _verdict_key(text: str) -> str:
    """``"khong_dat"``/``"dat"`` theo phần mở đầu của chuỗi kết luận, rỗng nếu không rõ."""
    normalized = _clean(text).casefold()
    if normalized.startswith("không đạt"):
        return "khong_dat"
    if normalized.startswith("đạt"):
        return "dat"
    return ""


def verdict_from_marks(grids: list[Grid]) -> tuple[str | None, str]:
    """Kết luận từ ô đánh dấu: có "Không đạt" được chọn thì không đạt."""
    checked = [
        mark for *_, cell in _all_cells(grids) for mark in marks_in_text(cell) if mark.checked
    ]
    for wanted, verdict in (("khong_dat", "Không đạt"), ("dat", "Đạt")):
        for mark in checked:
            if _verdict_key(mark.label) == wanted and len(_clean(mark.label)) <= len(verdict):
                return verdict, mark.quote
    return None, ""


def conclusion_line(grids: list[Grid]) -> tuple[str | None, str]:
    """Giá trị của dòng ``Kết luận: ...`` đầu tiên (tiêu đề mục không có ':' bị bỏ)."""
    for *_, cell in _all_cells(grids):
        match = _CONCLUSION_RE.match(_clean(cell))
        if match:
            return match.group("value").strip(), _clean(cell)
    return None, ""


def _signature_title(text: str) -> str | None:
    key = _PARENTHESES_RE.sub(" ", _clean(text)).strip(" :").casefold()
    return _SIGNATURE_TITLES.get(vnnum.normalize_spaces(key))


def _name_below(grid: Grid, row_index: int, col_index: int) -> str | None:
    """Ô có chữ đầu tiên phía dưới cùng cột, bỏ qua dòng hướng dẫn trong ngoặc."""
    for below in grid[row_index + 1 : row_index + 1 + _SIGNATURE_LOOKAHEAD_ROWS]:
        text = _clean(below[col_index]) if col_index < len(below) else ""
        if not text or text.startswith("("):
            continue
        if _signature_title(text) is not None:
            return None
        return text
    return None


def signature_fields(grids: list[Grid]) -> list[FieldDraft]:
    """Tên người ký dưới mỗi tiêu đề chữ ký đã biết (mỗi tiêu đề lấy lần đầu)."""
    fields: list[FieldDraft] = []
    seen: set[str] = set()
    for grid, row_index, col_index, cell in _all_cells(grids):
        label = _signature_title(cell)
        if label is None or label in seen:
            continue
        name = _name_below(grid, row_index, col_index)
        if name:
            fields.append(FieldDraft(label=label, value=name, quote=f"{_clean(cell)} | {name}"))
            seen.add(label)
    return fields


def record_mark_fields(grids: list[Grid]) -> tuple[list[FieldDraft], list[str]]:
    """Trường kết luận + chữ ký; cảnh báo khi dòng kết luận mâu thuẫn ô đánh dấu."""
    fields: list[FieldDraft] = []
    warnings: list[str] = []
    line, line_quote = conclusion_line(grids)
    marked, marked_quote = verdict_from_marks(grids)
    if line:
        fields.append(FieldDraft(label=CONCLUSION_LABEL, value=line, quote=line_quote))
        line_key = _verdict_key(line)
        if marked and line_key and line_key != _verdict_key(marked):
            warnings.append(
                f"Kết luận '{line}' mâu thuẫn với ô đánh dấu '{marked_quote}'; cần người duyệt xem lại."
            )
    elif marked:
        fields.append(FieldDraft(label=CONCLUSION_LABEL, value=marked, quote=marked_quote))
    fields.extend(signature_fields(grids))
    return fields, warnings
