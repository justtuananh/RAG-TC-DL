"""Nhận diện bảng kết quả trong biên bản Excel theo tiêu đề bảng (spec §5.5).

Biên bản thật (ví dụ QTKĐ 1.159) đặt nhiều bảng trên một sheet, có bảng nằm SONG
SONG với khối đầu mục, tiêu đề cột nhiều tầng gộp ô. Vì vậy bảng được neo bằng
dòng tiêu đề ``"Bảng 2 - Khối lượng các quả cân"`` khớp với tiêu đề bảng của Phụ
lục A đã duyệt (``"Bảng A.4 - Khối lượng đĩa cân gốc, píttông, các quả cân"``):

- dòng tiêu đề cột bắt đầu ngay dưới tiêu đề bảng, CÙNG cột đầu;
- vùng cột là dải ô liền mạch của dòng tiêu đề cột (tính cả ô gộp);
- khối tiêu đề cột kéo xuống tới đáy các ô gộp bắt đầu ở dòng đầu;
- tên cột lấy từ CHÍNH biên bản (không theo vị trí cột của Phụ lục A, vì biên bản
  thật có thể đổi thứ tự hoặc đơn vị cột);
- dữ liệu dừng ở tiêu đề bảng kế tiếp, dòng nhãn kết thúc bằng ``:``, đề mục đánh
  số, hoặc hai dòng trống liên tiếp.

Bảng không neo được sẽ do bộ đọc cũ (khớp tiêu đề cột) xử lý như trước.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from knowledge import vnnum
from records.columns import (
    cell_number,
    map_measurement_row,
    role_for_column,
    unit_after_comma,
    unit_from_header,
)
from records.template import MappingConfig, ResultTable
from records.types import MeasurementDraft
from records.xlsx_grid import Sheet

TITLE_RE = re.compile(
    r"^\s*Bảng\s+(?P<code>[A-Z]?\.?\d+(?:\.\d+)*)\s*[-\u2013\u2014:]\s*(?P<rest>.+)$",
    re.IGNORECASE | re.DOTALL,
)
_PARENTHESES_RE = re.compile(r"\([^()]*\)")
_NUMBERED_HEADING_RE = re.compile(r"^\d+(?:\.\d+)*\.?\s+\D")
_MIN_TITLE_SCORE = 0.8
_MIN_SUBSET_TOKENS = 3
_HEADER_SEARCH_ROWS = 3
_MAX_EMPTY_ROWS = 1


@dataclass
class TableRegion:
    """Một bảng đã neo: vị trí trên sheet và các dòng số liệu đọc được."""

    sheet_index: int
    step_code: str
    first_row: int
    last_row: int
    col0: int
    col1: int
    measurements: list[MeasurementDraft] = field(default_factory=list)

    def covers(self, sheet_index: int, row: int, col: int) -> bool:
        return (
            sheet_index == self.sheet_index
            and self.first_row <= row <= self.last_row
            and self.col0 <= col <= self.col1
        )


def _clean(text: str) -> str:
    return vnnum.normalize_spaces(text or "").strip()


def _slug(text: str) -> str:
    from records.template import slugify

    return slugify(text)


def _title_core(text: str) -> str:
    """Phần nội dung của tiêu đề bảng (bỏ "Bảng X.n -" và cụm trong ngoặc), dạng slug."""
    match = TITLE_RE.match(_clean(text))
    rest = match.group("rest") if match else _clean(text)
    return _slug(_PARENTHESES_RE.sub(" ", rest))


def title_score(config_title: str, record_title: str) -> float:
    """Độ giống giữa tiêu đề bảng Phụ lục A và tiêu đề bảng trong biên bản (0..1)."""
    left, right = _title_core(config_title), _title_core(record_title)
    if not left or not right:
        return 0.0
    compact_left, compact_right = left.replace("_", ""), right.replace("_", "")
    if compact_left == compact_right:
        return 1.0
    tokens_left, tokens_right = set(left.split("_")), set(right.split("_"))
    smaller = min(len(tokens_left), len(tokens_right))
    if smaller >= _MIN_SUBSET_TOKENS and (
        tokens_left <= tokens_right or tokens_right <= tokens_left
    ):
        return 0.9
    return SequenceMatcher(None, compact_left, compact_right).ratio()


def step_code_for(table: ResultTable) -> str:
    """Mã bước ổn định giữa các hồ sơ: mã bảng Phụ lục A (``A.4``) hoặc khóa bảng."""
    match = TITLE_RE.match(_clean(table.title))
    return (match.group("code") if match else table.key)[:32]


def _title_cells(sheets: list[Sheet]) -> list[tuple[int, int, int, str]]:
    cells: list[tuple[int, int, int, str]] = []
    for sheet_index, sheet in enumerate(sheets):
        for row_index, row in enumerate(sheet.rows):
            for col_index, text in enumerate(row):
                if text and TITLE_RE.match(_clean(text)):
                    cells.append((sheet_index, row_index, col_index, text))
    return cells


def _header_start(sheet: Sheet, title_row: int, col: int) -> int | None:
    for row in range(title_row + 1, title_row + 1 + _HEADER_SEARCH_ROWS):
        if _clean(sheet.filled(row, col)):
            return row
    return None


def _header_block(sheet: Sheet, start: int, col0: int) -> tuple[int, int]:
    """``(col1, header_end)``: mép phải dải tiêu đề cột và dòng cuối khối tiêu đề."""
    col1 = col0
    while _clean(sheet.filled(start, col1 + 1)):
        col1 += 1
    bottoms = [
        merge.row1 for merge in sheet.merges if merge.row0 == start and col0 <= merge.col0 <= col1
    ]
    return col1, max([start, *bottoms])


def _column_groups(sheet: Sheet, rows: range, col0: int, col1: int) -> list[tuple[str, list[int]]]:
    """Tên cột (ghép các tầng tiêu đề) và các cột vật lý thuộc cùng một tên."""
    groups: list[tuple[str, list[int]]] = []
    for col in range(col0, col1 + 1):
        parts: list[str] = []
        for row in rows:
            text = _clean(sheet.filled(row, col))
            if text and (not parts or parts[-1] != text):
                parts.append(text)
        name = " ".join(parts)
        if groups and groups[-1][0] == name:
            groups[-1][1].append(col)
        else:
            groups.append((name, [col]))
    return groups


def _row_values(sheet: Sheet, row: int, groups: list[tuple[str, list[int]]]) -> list[str]:
    values: list[str] = []
    for _, cols in groups:
        values.append(
            next((_clean(sheet.cell(row, col)) for col in cols if _clean(sheet.cell(row, col))), "")
        )
    return values


def _ends_table(values: list[str]) -> bool:
    filled = [value for value in values if value]
    if any(TITLE_RE.match(value) for value in filled):
        return True
    if filled[0].endswith(":"):
        return True
    return len(filled) == 1 and bool(_NUMBERED_HEADING_RE.match(filled[0]))


def _is_subheading(values: list[str]) -> bool:
    filled = [value for value in values if value]
    return len(filled) == 1 and cell_number(filled[0]) is None


def _draft(names: list[str], values: list[str], step_code: str) -> MeasurementDraft:
    draft = map_measurement_row(names, values)
    draft.step_code = step_code
    draft.inherit_unit = False
    if draft.unit_text is None:
        nominal = next((name for name in names if role_for_column(name) == "nominal"), None)
        draft.unit_text = (unit_from_header(nominal) if nominal else None) or unit_after_comma(
            draft.label or ""
        )
    return draft


def _read_rows(sheet: Sheet, region: TableRegion, start: int, groups) -> None:
    names = [name for name, _ in groups]
    empty_run = 0
    for row in range(start, len(sheet.rows)):
        values = _row_values(sheet, row, groups)
        if not any(values):
            empty_run += 1
            if empty_run > _MAX_EMPTY_ROWS:
                break
            continue
        empty_run = 0
        if _ends_table(values):
            break
        region.last_row = row
        if not _is_subheading(values):
            region.measurements.append(_draft(names, values, region.step_code))


def _build_region(
    sheets: list[Sheet], anchor: tuple[int, int, int, str], table: ResultTable
) -> TableRegion | None:
    sheet_index, title_row, col0, _ = anchor
    sheet = sheets[sheet_index]
    start = _header_start(sheet, title_row, col0)
    if start is None:
        return None
    col1, header_end = _header_block(sheet, start, col0)
    groups = _column_groups(sheet, range(start, header_end + 1), col0, col1)
    region = TableRegion(sheet_index, step_code_for(table), title_row, header_end, col0, col1)
    _read_rows(sheet, region, header_end + 1, groups)
    return region


def locate_tables(sheets: list[Sheet], config: MappingConfig) -> list[TableRegion]:
    """Neo từng bảng Phụ lục A vào tiêu đề bảng giống nhất (mỗi tiêu đề dùng một lần)."""
    anchors = _title_cells(sheets)
    scored = sorted(
        (
            (title_score(table.title, anchor[3]), table_index, anchor_index)
            for table_index, table in enumerate(config.result_tables)
            for anchor_index, anchor in enumerate(anchors)
        ),
        reverse=True,
    )
    used_tables: set[int] = set()
    used_anchors: set[int] = set()
    regions: list[tuple[int, TableRegion]] = []
    for score, table_index, anchor_index in scored:
        if score < _MIN_TITLE_SCORE or table_index in used_tables or anchor_index in used_anchors:
            continue
        region = _build_region(sheets, anchors[anchor_index], config.result_tables[table_index])
        if region is not None:
            used_tables.add(table_index)
            used_anchors.add(anchor_index)
            regions.append((table_index, region))
    return [region for _, region in sorted(regions, key=lambda item: item[0])]
