"""Định vị trích dẫn của biên bản Excel về đúng sheet/dòng/ô gốc (P1).

Bộ đọc hồ sơ (``records.xlsx_reader``/``records.columns``) lưu trích dẫn là các ô
KHÔNG RỖNG của một dòng nối bằng `` | ``. Tệp Excel không có Markdown nên bề mặt
xuất xứ không có "mục văn bản" để tô sáng; thay vào đó, hàm ở đây tìm lại dòng
sinh ra trích dẫn để giao diện vẽ đúng lưới ô gốc và tô đúng ô chứa giá trị.

Chỉ trả toạ độ (0-based, đúng chỉ số Excel); không bao giờ đổi nội dung ô. Không
tìm thấy hoặc không đọc được tệp thì trả ``None`` - nguồn chỉ để hiển thị, không
được chặn tra cứu.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from knowledge.vnnum import normalize_spaces
from records.xlsx_grid import Sheet, read_sheets

SEPARATOR = " | "


def _parts(quote: str | None) -> list[str]:
    items = (normalize_spaces(item) for item in (quote or "").split(SEPARATOR))
    return [item for item in items if item]


def _row_cells(row: list[str]) -> list[tuple[int, str]]:
    """``(cột, văn bản đã chuẩn hóa)`` của các ô không rỗng, theo thứ tự cột."""
    cells = ((col, normalize_spaces(text)) for col, text in enumerate(row))
    return [(col, text) for col, text in cells if text]


def _match_cols(cells: list[tuple[int, str]], parts: list[str]) -> list[int] | None:
    """Cột của dãy ô liên tiếp (bỏ ô rỗng) trùng đúng ``parts``; ``None`` nếu không có."""
    texts = [text for _, text in cells]
    width = len(parts)
    for start in range(len(texts) - width + 1):
        if texts[start : start + width] == parts:
            return [col for col, _ in cells[start : start + width]]
    return None


def _highlight_cols(
    cells: list[tuple[int, str]], cols: list[int], value: str | None, value_part: int | None
) -> list[int]:
    """Ô chứa giá trị cần tô.

    ``value_part`` (vị trí của ô nguồn trong trích dẫn, đã bỏ ô rỗng) là căn cứ chắc
    chắn nhất: một dòng có thể có hai ô cùng chữ ("6 | 6"). Thiếu vị trí hoặc vị trí
    không khớp giá trị thì dò theo giá trị: trùng khớp trước, chứa giá trị sau; không
    có thì tô cả dãy ô khớp.
    """
    wanted = normalize_spaces(value)
    texts = {col: text for col, text in cells if col in cols}
    if value_part is not None and 0 <= value_part < len(cols):
        col = cols[value_part]
        if not wanted or wanted in texts[col]:
            return [col]
    if not wanted:
        return list(cols)
    exact = [col for col in cols if texts[col] == wanted]
    if exact:
        return exact
    contains = [col for col in cols if wanted in texts[col]]
    return contains or list(cols)


def locate_quote(
    sheets: list[Sheet], quote: str | None, value: str | None, value_part: int | None = None
) -> dict[str, Any] | None:
    """Dòng đầu tiên có các ô liên tiếp trùng ``quote``; kèm cột cần tô sáng theo ``value``."""
    parts = _parts(quote)
    if not parts:
        return None
    for sheet_index, sheet in enumerate(sheets):
        for row_index, row in enumerate(sheet.rows):
            cells = _row_cells(row)
            cols = _match_cols(cells, parts)
            if cols is None:
                continue
            return {
                "sheet": sheet.name,
                "sheet_index": sheet_index,
                "row": row_index,
                "cols": cols,
                "highlight_cols": _highlight_cols(cells, cols, value, value_part),
            }
    return None


def locate_in_file(
    path: str | Path, quote: str | None, value: str | None, value_part: int | None = None
) -> dict[str, Any] | None:
    """Như ``locate_quote`` nhưng đọc thẳng tệp .xlsx; tệp hỏng/không đọc được → ``None``."""
    try:
        sheets = read_sheets(path)
    except Exception:  # noqa: BLE001 - nguồn chỉ để hiển thị, không chặn tra cứu
        return None
    return locate_quote(sheets, quote, value, value_part)
