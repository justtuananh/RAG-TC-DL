"""Lưới bảng của hồ sơ danh mục, giữ từng đoạn trong một ô (docx) hoặc từng dòng (xlsx).

Bộ đọc hồ sơ kiểm định nối mọi ``w:t`` của một ô thành một chuỗi, nên "Nguyễn Đăng
Vinh" và năm sinh "1970" (hai đoạn) dính thành "Nguyễn Đăng Vinh1970". Danh mục NAS
dựa vào ranh giới đoạn, nên ở đây mỗi ô là danh sách dòng.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from ingestion.docx_grid import grid_slots
from knowledge import vnnum
from records.xlsx_grid import read_sheets

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

Cell = list[str]
Row = list[Cell]


@dataclass
class Block:
    """Một khối theo thứ tự tài liệu: đoạn văn (``text``) hoặc bảng (``rows``)."""

    kind: str  # "p" | "table"
    text: str = ""
    rows: list[Row] | None = None


def _clean(text: str) -> str:
    return vnnum.normalize_spaces(text or "").strip()


def _docx_cell(tc) -> Cell:
    lines = (_clean("".join(t.text or "" for t in p.iter(f"{_W}t"))) for p in tc.iter(f"{_W}p"))
    return [line for line in lines if line]


def _docx_row(tr) -> Row:
    row: Row = []
    for slot in grid_slots(tr):
        # Ô tiếp nối của ô gộp dọc để trống; ô gridSpan chiếm N cột (nội dung ở cột đầu).
        row.append([] if slot.continues else _docx_cell(slot.cell))
        row.extend([] for _ in range(slot.span - 1))
    return row


def _docx_blocks(path: Path) -> list[Block]:
    with zipfile.ZipFile(path) as archive:
        body = etree.fromstring(archive.read("word/document.xml")).find(f"{_W}body")
    blocks: list[Block] = []
    for child in body if body is not None else []:
        if child.tag == f"{_W}p":
            text = _clean("".join(t.text or "" for t in child.iter(f"{_W}t")))
            if text:
                blocks.append(Block("p", text=text))
        elif child.tag == f"{_W}tbl":
            blocks.append(Block("table", rows=[_docx_row(tr) for tr in child.findall(f"{_W}tr")]))
    return blocks


def _xlsx_blocks(path: Path) -> list[Block]:
    blocks: list[Block] = []
    for sheet in read_sheets(path):
        rows = [
            [[_clean(line) for line in cell.split("\n") if _clean(line)] for cell in row]
            for row in sheet.rows
        ]
        blocks.append(Block("p", text=sheet.name))
        blocks.append(Block("table", rows=rows))
    return blocks


def load_blocks(path: str | Path) -> list[Block]:
    """Khối đoạn/bảng của tệp ``.docx``/``.xlsx`` (bản đã chuyển từ ``.doc``/``.xls``)."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _docx_blocks(path)
    if suffix == ".xlsx":
        return _xlsx_blocks(path)
    raise ValueError(f"Định dạng danh mục không hỗ trợ: {suffix or '(không rõ)'}.")


def cell_text(cell: Cell, sep: str = " ") -> str:
    return _clean(sep.join(cell))


def row_quote(row: Row) -> str:
    """Nguyên văn một dòng (P1): ô nối " | ", đoạn trong ô nối " / "."""
    return " | ".join(" / ".join(cell) for cell in row)
