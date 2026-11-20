"""Bảng có tên ("Bảng C.1: Sai số cho phép của ...") trong Markdown của tài liệu: tên, tiêu đề cột, các dòng.

Thuần văn bản, không gọi dịch vụ. Dùng để biết một giới hạn (sai số cho phép) được tra theo những thông số
nào: tiêu đề cột ("Phạm vi đo", "Loại nhiệt kế", "Giá trị độ chia nhỏ nhất"), phần "(Theo ... và ...)" trong
tiêu đề cột giới hạn, và phần khác nhau giữa tên các bảng ("nhúng toàn phần" / "nhúng một phần").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CAPTION_RE = re.compile(r"^\**\s*(Bảng\s+(?:[A-Z]\.)?\d+(?:\.\d+)*)\s*[:.\-–]\s*(.+?)\s*\**\s*$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")
_LOOKAHEAD = 6  # số dòng có chữ tối đa giữa tên bảng và dòng đầu của bảng


@dataclass(frozen=True)
class CaptionedTable:
    label: str  # "Bảng C.1"
    caption: str  # "Sai số cho phép của nhiệt kế thủy tinh chất lỏng nhúng toàn phần"
    header: tuple[str, ...]  # dòng tiêu đề đầu
    subheaders: tuple[tuple[str, ...], ...]  # dòng tiêu đề phụ (ô đầu rỗng) ngay sau dòng phân cách
    rows: tuple[tuple[str, ...], ...]
    text: str  # nguyên văn: dòng tên bảng + bảng Markdown

    @property
    def title(self) -> str:
        return f"{self.label}: {self.caption}"

    def column(self, index: int) -> list[str]:
        return [row[index] for row in self.rows if index < len(row)]


def _cells(line: str) -> tuple[str, ...]:
    parts = line.strip().strip("|").split("|")
    return tuple(" ".join(part.replace(" / ", " ").split()) for part in parts)


def _table_lines(lines: list[str], start: int) -> list[str] | None:
    """Các dòng của bảng Markdown đầu tiên ngay sau tên bảng."""
    seen = 0
    for i in range(start, len(lines)):
        stripped = lines[i].strip()
        if not stripped:
            continue
        if stripped.startswith("|"):
            block = []
            for line in lines[i:]:
                if not line.strip().startswith("|"):
                    break
                block.append(line.rstrip())
            return block
        seen += 1
        if seen >= _LOOKAHEAD:
            return None
    return None


def _split(block: list[str]) -> tuple[tuple[str, ...], list[tuple[str, ...]], list[tuple[str, ...]]]:
    rows = [_cells(line) for line in block]
    header = rows[0]
    body = [row for row in rows[1:] if not all(_SEPARATOR_CELL_RE.match(cell) for cell in row if cell)]
    subheaders = []
    while body and not body[0][0] and any(body[0][1:]):
        subheaders.append(body.pop(0))
    return header, subheaders, body


def captioned_tables(markdown: str) -> list[CaptionedTable]:
    lines = markdown.splitlines()
    tables: list[CaptionedTable] = []
    for i, line in enumerate(lines):
        caption = _CAPTION_RE.match(line.strip())
        if not caption:
            continue
        block = _table_lines(lines, i + 1)
        if not block:
            continue
        header, subheaders, rows = _split(block)
        text = f"{line.strip()}\n\n" + "\n".join(block)
        tables.append(
            CaptionedTable(caption.group(1), caption.group(2), header, tuple(subheaders), tuple(rows), text)
        )
    return tables
