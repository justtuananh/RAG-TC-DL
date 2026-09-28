"""Đọc lưới ô của MỌI sheet trong tệp Excel bằng OOXML thô (spec §5.5).

Tách khỏi ``xlsx_reader`` để bộ đọc hồ sơ chỉ lo nghiệp vụ. Mỗi sheet trả về một
``Sheet``: lưới chuỗi đặt đúng CHỈ SỐ DÒNG/CỘT của Excel (dòng trống vẫn giữ chỗ)
cùng danh sách vùng gộp ô, vì biên bản thật dùng gộp ô cho tiêu đề bảng nhiều tầng.

Quy ước giá trị ô giữ nguyên như trước (K01, K05): ô số là chuỗi kiểu Việt (dấu
phẩy thập phân), ô số mang style ngày đổi sang ``DD/MM/YYYY``.
"""

from __future__ import annotations

import math
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from lxml import etree

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}
_M = f"{{{NS['main']}}}"

_CELL_REF_RE = re.compile(r"^([A-Za-z]+)(\d+)$")
# Định dạng ngày/giờ dựng sẵn của Excel (mục 14..22 theo ECMA-376).
_BUILTIN_DATE_FMT_IDS = frozenset(range(14, 23))


@dataclass(frozen=True)
class Merge:
    """Vùng gộp ô, chỉ số 0-based, bao cả hai đầu."""

    row0: int
    col0: int
    row1: int
    col1: int


@dataclass
class Sheet:
    """Một sheet: tên, lưới chuỗi theo chỉ số thật, các vùng gộp ô."""

    name: str
    rows: list[list[str]]
    merges: list[Merge] = field(default_factory=list)

    def cell(self, row: int, col: int) -> str:
        if 0 <= row < len(self.rows) and 0 <= col < len(self.rows[row]):
            return self.rows[row][col]
        return ""

    def merge_at(self, row: int, col: int) -> Merge | None:
        for merge in self.merges:
            if merge.row0 <= row <= merge.row1 and merge.col0 <= col <= merge.col1:
                return merge
        return None

    def filled(self, row: int, col: int) -> str:
        """Giá trị ô, lấy từ ô góc trên trái nếu ô nằm trong vùng gộp."""
        merge = self.merge_at(row, col)
        if merge is None:
            return self.cell(row, col)
        return self.cell(merge.row0, merge.col0)


def _split_ref(ref: str) -> tuple[int, int] | None:
    """``"B12"`` → ``(11, 1)`` (dòng, cột 0-based); ``None`` nếu tham chiếu lạ."""
    match = _CELL_REF_RE.match(ref or "")
    if not match:
        return None
    col = 0
    for char in match.group(1).upper():
        col = col * 26 + (ord(char) - ord("A") + 1)
    return int(match.group(2)) - 1, col - 1


def column_index(ref: str) -> int:
    """``"B12"`` → 1 (0-based) để đặt ô đúng cột kể cả khi có ô trống."""
    parts = _split_ref(ref)
    return parts[1] if parts else 0


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = etree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(node.text or "" for node in si.iter(f"{_M}t")) for si in root.findall(f"{_M}si")
    ]


def _sheet_paths(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    """``(tên sheet, đường dẫn xml)`` theo đúng thứ tự trong ``workbook.xml``."""
    root = etree.fromstring(archive.read("xl/workbook.xml"))
    sheets = root.findall(f"{_M}sheets/{_M}sheet")
    if not sheets:
        raise ValueError("Tệp Excel không có sheet nào.")
    rels = etree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        rel.get("Id"): rel.get("Target") or ""
        for rel in rels.findall(f"{{{NS['pkg']}}}Relationship")
    }
    paths: list[tuple[str, str]] = []
    for index, sheet in enumerate(sheets, start=1):
        target = targets.get(sheet.get(f"{{{NS['rel']}}}id")) or f"worksheets/sheet{index}.xml"
        target = target.lstrip("/")
        paths.append(
            (
                sheet.get("name") or f"Sheet{index}",
                target if target.startswith("xl/") else f"xl/{target}",
            )
        )
    return paths


def _style_index(cell) -> int:
    """Chỉ số ``cellXfs`` của ô (thuộc tính ``s``); -1 nếu không có/không hợp lệ."""
    try:
        return int(cell.get("s"))
    except (TypeError, ValueError):
        return -1


def _is_date_format(code: str) -> bool:
    """``formatCode`` tuỳ biến là định dạng ngày, không phải chỉ giờ.

    Bỏ literal trong ngoặc kép/vuông trước khi xét; có ``d``/``y`` là ngày; chỉ
    còn ``m`` thì phải không kèm ``h`` hoặc ``:`` (nếu không là phút).
    """
    cleaned = re.sub(r'"[^"]*"', "", code or "")
    cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)
    if not re.search(r"[dmyDMY]", cleaned):
        return False
    if re.search(r"[dDyY]", cleaned):
        return True
    return not (re.search(r"[hH]", cleaned) or ":" in cleaned)


def _date_styles(archive: zipfile.ZipFile) -> set[int]:
    """Tập chỉ số ``cellXfs`` có định dạng ngày (dựng sẵn 14..22 hoặc tuỳ biến)."""
    try:
        root = etree.fromstring(archive.read("xl/styles.xml"))
    except KeyError:
        return set()
    custom: dict[int, str] = {}
    for numfmt in root.findall(f"{_M}numFmts/{_M}numFmt"):
        try:
            custom[int(numfmt.get("numFmtId"))] = numfmt.get("formatCode") or ""
        except (TypeError, ValueError):
            continue
    styles: set[int] = set()
    for index, xf in enumerate(root.findall(f"{_M}cellXfs/{_M}xf")):
        try:
            fmt_id = int(xf.get("numFmtId") or 0)
        except ValueError:
            continue
        if fmt_id in _BUILTIN_DATE_FMT_IDS or _is_date_format(custom.get(fmt_id, "")):
            styles.add(index)
    return styles


def _serial_to_date(text: str) -> str:
    """Số serial Excel (gốc 1899-12-30) → ``"DD/MM/YYYY"``; lỗi thì giữ nguyên."""
    try:
        serial = float(text)
    except (TypeError, ValueError):
        return text
    moment = datetime(1899, 12, 30) + timedelta(days=serial)
    return moment.strftime("%d/%m/%Y")


def _shortest_number(text: str) -> str:
    """Số máy (``999.99784999999997``, ``6.0000000000000001E-3``) → chuỗi ngắn nhất
    biểu diễn ĐÚNG cùng giá trị double (``999.99785``, ``0.006``).

    Đây là đổi cách viết, không làm tròn: ``float(kết quả) == float(text)``. Số
    nguyên và chuỗi không phải số giữ nguyên.
    """
    if not re.search(r"[.eE]", text):
        return text
    try:
        value = float(text)
    except ValueError:
        return text
    return repr(value) if math.isfinite(value) else text


def cell_value(cell, shared: list[str], date_styles: set[int]) -> str:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{_M}t"))
    value_node = cell.find(f"{_M}v")
    if value_node is None or value_node.text is None:
        return ""
    if cell_type == "s":
        try:
            return shared[int(value_node.text)]
        except (ValueError, IndexError):
            return ""
    if cell_type in (None, "n"):
        # K05: ô số mang style ngày (xl/styles.xml) là số serial Excel, đổi sang
        # "DD/MM/YYYY" TRƯỚC bước đổi dấu chấm của K01.
        if _style_index(cell) in date_styles:
            return _serial_to_date(value_node.text)
        # K01: ô số là số máy, luôn dùng dấu chấm thập phân; đổi sang chuỗi kiểu
        # Việt (phẩy thập phân, không nhóm nghìn) trước khi xuống tầng parse.
        return _shortest_number(value_node.text).replace(".", ",")
    return value_node.text


def _parse_merges(root) -> list[Merge]:
    merges: list[Merge] = []
    for node in root.findall(f"{_M}mergeCells/{_M}mergeCell"):
        start, _, end = (node.get("ref") or "").partition(":")
        first, last = _split_ref(start), _split_ref(end or start)
        if first and last:
            merges.append(Merge(first[0], first[1], last[0], last[1]))
    return merges


def _parse_sheet(name: str, root, shared: list[str], date_styles: set[int]) -> Sheet:
    cells: dict[tuple[int, int], str] = {}
    for position, row in enumerate(root.findall(f"{_M}sheetData/{_M}row")):
        # Thuộc tính ``r`` là số dòng thật; thiếu thì theo thứ tự xuất hiện.
        try:
            row_index = int(row.get("r")) - 1
        except (TypeError, ValueError):
            row_index = position
        for cell in row.findall(f"{_M}c"):
            cells[(row_index, column_index(cell.get("r", "")))] = cell_value(
                cell, shared, date_styles
            )
    height = max((r for r, _ in cells), default=-1) + 1
    rows: list[list[str]] = [[] for _ in range(height)]
    for (r, c), text in cells.items():
        row = rows[r]
        if len(row) <= c:
            row.extend([""] * (c + 1 - len(row)))
        row[c] = text
    return Sheet(name=name, rows=rows, merges=_parse_merges(root))


def read_sheets(path: str | Path) -> list[Sheet]:
    """Mọi sheet của tệp theo thứ tự workbook."""
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        date_styles = _date_styles(archive)
        sheets: list[Sheet] = []
        for name, sheet_path in _sheet_paths(archive):
            try:
                root = etree.fromstring(archive.read(sheet_path))
            except KeyError:
                continue
            sheets.append(_parse_sheet(name, root, shared, date_styles))
    return sheets
