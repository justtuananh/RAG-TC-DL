"""Bảng tính (.xlsx) -> Markdown cho kho văn bản (không phải hồ sơ/biên bản).

Mỗi sheet là một mục ``# <tên sheet>``. Mỗi vùng bảng liền mạch (các dòng có dữ
liệu, ngăn bởi dòng trống) thành một bảng Markdown pipe:

  * ô gộp / tiêu đề nhiều tầng được ghép theo CỘT bằng giá trị ô góc trên trái
    (nhờ ``records.xlsx_grid`` giữ vùng gộp), nối các tầng bằng " - ";
  * dòng/cột trống hoàn toàn bị bỏ;
  * ô nhiều dòng thay xuống dòng bằng " / " để bảng Markdown luôn hợp lệ.

Chỉ đọc, không sửa tệp nguồn; không thêm phụ thuộc (dùng lxml gián tiếp qua
``records.xlsx_grid``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from records.xlsx_grid import Sheet, read_sheets

_MAX_HEADER_ROWS = 3


@dataclass
class XlsxResult:
    markdown: str
    n_sheets: int
    n_tables: int
    n_rows: int = 0
    n_paragraphs: int = 0


def _clean(text: str) -> str:
    """Ô nhiều dòng -> một dòng (" / "), escape "|" để bảng Markdown hợp lệ."""
    lines = [part.strip() for part in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return " / ".join(part for part in lines if part).replace("|", "\\|")


def _regions(sheet: Sheet) -> list[tuple[int, int]]:
    """Các dải dòng liền mạch có dữ liệu (dòng trống ngăn cách các vùng)."""
    regions: list[tuple[int, int]] = []
    start: int | None = None
    for row_index, row in enumerate(sheet.rows):
        nonempty = any(cell.strip() for cell in row)
        if nonempty and start is None:
            start = row_index
        elif not nonempty and start is not None:
            regions.append((start, row_index - 1))
            start = None
    if start is not None:
        regions.append((start, len(sheet.rows) - 1))
    return regions


def _columns(sheet: Sheet, start: int, end: int) -> list[int]:
    """Cột có dữ liệu trong vùng (ô gộp tính theo ô góc trên trái)."""
    width = max((len(row) for row in sheet.rows), default=0)
    return [
        col
        for col in range(width)
        if any(sheet.filled(row, col).strip() for row in range(start, end + 1))
    ]


def _header_rows(sheet: Sheet, start: int, end: int) -> int:
    """Số tầng tiêu đề: theo vùng gộp dọc ở dòng đầu, tối đa 3 tầng."""
    header = 1
    for merge in sheet.merges:
        if merge.row0 == start and merge.row1 > start:
            header = max(header, min(merge.row1 - start + 1, _MAX_HEADER_ROWS))
    return min(header, end - start + 1)


def _column_header(sheet: Sheet, start: int, header_rows: int, col: int) -> str:
    """Ghép tiêu đề cột qua các tầng, bỏ phần lặp liền kề do ô gộp dọc."""
    parts: list[str] = []
    for row in range(start, start + header_rows):
        value = _clean(sheet.filled(row, col))
        if value and (not parts or parts[-1] != value):
            parts.append(value)
    return " - ".join(parts) or f"Cột {col + 1}"


def _table_md(sheet: Sheet, start: int, end: int) -> tuple[str, int]:
    """Một vùng -> (bảng Markdown, số dòng dữ liệu); ("", 0) nếu rỗng."""
    columns = _columns(sheet, start, end)
    if not columns:
        return "", 0
    header_rows = _header_rows(sheet, start, end)
    lines = [
        "| " + " | ".join(_column_header(sheet, start, header_rows, col) for col in columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    data_rows = 0
    for row in range(start + header_rows, end + 1):
        cells = [_clean(sheet.filled(row, col)) for col in columns]
        if not any(cells):
            continue
        lines.append("| " + " | ".join(cells) + " |")
        data_rows += 1
    return "\n".join(lines), data_rows


def extract_xlsx(path: str | Path) -> XlsxResult:
    """Mọi sheet -> Markdown; trả luôn số sheet/bảng để dựng entry báo cáo."""
    sheets = read_sheets(path)
    sections: list[str] = []
    n_tables = 0
    n_rows = 0
    for sheet in sheets:
        blocks = [f"# {sheet.name}"]
        for start, end in _regions(sheet):
            table, rows = _table_md(sheet, start, end)
            if table:
                blocks.append(table)
                n_tables += 1
                n_rows += rows
        sections.append("\n\n".join(blocks))
    markdown = "\n\n".join(sections).strip() + "\n"
    return XlsxResult(markdown=markdown, n_sheets=len(sheets), n_tables=n_tables, n_rows=n_rows)
