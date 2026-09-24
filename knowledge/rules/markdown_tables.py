"""Đọc bảng Markdown, kể cả bảng có header hai tầng (Bảng 1, Bảng 2).

Corpus QTKĐ do pipeline docx→Markdown sinh ra có dạng header hai tầng đặc thù:
ô gộp ở tầng trên để trống ở các cột tiếp theo, và tầng dưới lại nằm **sau** dòng
phân cách:

    | TT | Tên phép kiểm định | ... | Chế độ kiểm định |  |  |
    | --- | --- | --- | --- | --- | --- |
    |  |  |  | Ban đầu | Định kỳ | Sau sửa chữa |
    | 1 | Kiểm tra bên ngoài | ... | + | + | + |

Bộ đọc nhận ra dòng "tầng dưới" (ô đầu rỗng, có ô ở cột mà tầng trên để trống),
gộp tên cột theo từng cột, và giữ nguyên văn + khoảng ký tự của từng dòng để tầng
ghi dựng xuất xứ P1. Không khớp mẫu → trả rỗng, không đoán.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SEPARATOR_RE = re.compile(r"^:?-{2,}:?$")


@dataclass(frozen=True)
class TableRow:
    """Một dòng dữ liệu: các ô, nguyên văn, và khoảng ký tự tuyệt đối."""

    cells: tuple[str, ...]
    raw: str
    start: int
    end: int


@dataclass(frozen=True)
class MarkdownTable:
    """Bảng đã gộp header theo cột; ``headers[i]`` là tên đầy đủ của cột ``i``."""

    headers: tuple[str, ...]
    rows: tuple[TableRow, ...]
    start: int
    end: int


def _split_cells(line: str) -> tuple[str, ...]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return tuple(cell.strip() for cell in stripped.split("|"))


def _is_separator(cells: tuple[str, ...]) -> bool:
    return bool(cells) and all(_SEPARATOR_RE.match(cell) for cell in cells)


def _is_subheader(cells: tuple[str, ...], top: tuple[str, ...]) -> bool:
    """Dòng ngay sau phân cách là tầng header dưới nếu ô đầu rỗng và có ô lấp
    vào cột mà tầng trên để trống (ô gộp)."""
    if not cells or cells[0].strip():
        return False
    return any(
        cells[index].strip() and (index >= len(top) or not top[index].strip())
        for index in range(1, len(cells))
    )


def _combine_headers(header_rows: list[tuple[str, ...]]) -> tuple[str, ...]:
    width = max((len(row) for row in header_rows), default=0)
    combined: list[str] = []
    for index in range(width):
        parts = [
            row[index].strip() for row in header_rows if index < len(row) and row[index].strip()
        ]
        combined.append(" ".join(parts))
    return tuple(combined)


def parse_tables(text: str, base_offset: int = 0) -> list[MarkdownTable]:
    """Trả mọi bảng Markdown trong ``text``, offset tuyệt đối tính từ ``base_offset``."""
    if not text:
        return []
    lines: list[tuple[str, int]] = []
    offset = 0
    for line in text.split("\n"):
        lines.append((line, offset))
        offset += len(line) + 1

    tables: list[MarkdownTable] = []
    index = 0
    while index < len(lines) - 1:
        line, start = lines[index]
        if "|" not in line:
            index += 1
            continue
        header_cells = _split_cells(line)
        if not _is_separator(_split_cells(lines[index + 1][0])):
            index += 1
            continue

        rows: list[TableRow] = []
        cursor = index + 2
        while cursor < len(lines):
            row_line, row_start = lines[cursor]
            if not row_line.strip() or "|" not in row_line:
                break
            cells = _split_cells(row_line)
            if _is_separator(cells):
                break
            rows.append(
                TableRow(
                    cells=cells,
                    raw=row_line,
                    start=base_offset + row_start,
                    end=base_offset + row_start + len(row_line),
                )
            )
            cursor += 1

        header_rows = [header_cells]
        if rows and _is_subheader(rows[0].cells, header_cells):
            header_rows.append(rows[0].cells)
            rows = rows[1:]

        last_line, last_start = lines[cursor - 1]
        tables.append(
            MarkdownTable(
                headers=_combine_headers(header_rows),
                rows=tuple(rows),
                start=base_offset + start,
                end=base_offset + last_start + len(last_line),
            )
        )
        index = cursor
    return tables
