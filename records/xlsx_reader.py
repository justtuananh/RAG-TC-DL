"""Đọc phiếu đo Excel theo mẫu cố định (spec §5.5, §9 S7).

Giống ``docx_reader``, bộ đọc này dùng OOXML thô (``zipfile`` + ``lxml``) thay vì
``openpyxl`` để giữ tính offline và không thêm phụ thuộc. Nó nhận diện dải bảng
và tiêu đề cột từ cấu hình ánh xạ trường (``records.template``), rồi trả
``RecordDraft`` thuần dữ liệu.

Bất biến P1/P2 giữ nguyên: mỗi ô số giữ nguyên văn; ``error_value`` chỉ đọc từ
cột sai số của phiếu, không bao giờ tính từ ``measured``/``nominal``.
"""

from __future__ import annotations

import re
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from lxml import etree

from knowledge import vnnum
from records.docx_reader import (
    _extract_labeled_fields,
    _map_measurement_row,
    _row_is_header,
    _slug,
)
from records.template import MappingConfig
from records.types import FieldDraft, MeasurementDraft, RecordDraft

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
}
_M = f"{{{NS['main']}}}"

EXTRACTOR = "record:xlsx.v1"
DEFAULT_SECTION_PATH = "Phiếu đo"

_CELL_REF_RE = re.compile(r"^([A-Za-z]+)(\d+)$")


def _column_index(ref: str) -> int:
    """``"B12"`` → 1 (0-based) để đặt ô đúng cột kể cả khi có ô trống."""
    match = _CELL_REF_RE.match(ref or "")
    if not match:
        return 0
    letters = match.group(1).upper()
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = etree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values: list[str] = []
    for si in root.findall(f"{_M}si"):
        values.append("".join(node.text or "" for node in si.iter(f"{_M}t")))
    return values


def _first_sheet_path(archive: zipfile.ZipFile) -> str:
    root = etree.fromstring(archive.read("xl/workbook.xml"))
    sheets = root.findall(f"{_M}sheets/{_M}sheet")
    if not sheets:
        raise ValueError("Tệp Excel không có sheet nào.")
    rid = sheets[0].get(f"{{{NS['rel']}}}id")
    rels = etree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for rel in rels.findall(f"{{{NS['pkg']}}}Relationship"):
        if rel.get("Id") == rid:
            target = rel.get("Target") or "worksheets/sheet1.xml"
            return f"xl/{target.lstrip('/')}"
    return "xl/worksheets/sheet1.xml"


def _cell_value(cell, shared: list[str], date_styles: set[int]) -> str:
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
        return value_node.text.replace(".", ",")
    return value_node.text


def _style_index(cell) -> int:
    """Chỉ số ``cellXfs`` của ô (thuộc tính ``s``); -1 nếu không có/không hợp lệ."""
    try:
        return int(cell.get("s"))
    except (TypeError, ValueError):
        return -1


# Định dạng ngày/giờ dựng sẵn của Excel (mục 14..22 theo ECMA-376).
_BUILTIN_DATE_FMT_IDS = frozenset(range(14, 23))


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



def _read_grid(path: str | Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        date_styles = _date_styles(archive)
        sheet_path = _first_sheet_path(archive)
        root = etree.fromstring(archive.read(sheet_path))

    grid: list[list[str]] = []
    for row in root.findall(f"{_M}sheetData/{_M}row"):
        cells: dict[int, str] = {}
        for cell in row.findall(f"{_M}c"):
            index = _column_index(cell.get("r", ""))
            cells[index] = _cell_value(cell, shared, date_styles)
        width = max(cells) + 1 if cells else 0
        grid.append([cells.get(i, "") for i in range(width)])
    return grid


def _header_fields(grid: list[list[str]], labels: list[str]) -> list[FieldDraft]:
    """Trường đầu mục: nhãn ở một ô, giá trị ở ô kế bên phải cùng dòng."""
    label_keys = {_slug(label) for label in labels}
    fields: list[FieldDraft] = []
    seen: set[str] = set()
    for row in grid:
        for index, cell in enumerate(row):
            if not cell.strip():
                continue
            text = vnnum.normalize_spaces(cell).strip()
            # Mẫu Excel: nhãn ở một ô, giá trị ở ô kế bên phải cùng dòng.
            if _slug(text) in label_keys and _slug(text) not in seen:
                value = next(
                    (candidate.strip() for candidate in row[index + 1 :] if candidate.strip()),
                    "",
                )
                fields.append(
                    FieldDraft(
                        label=text.rstrip(":").strip(),
                        value=value,
                        quote=" | ".join(c for c in row if c.strip()),
                    )
                )
                seen.add(_slug(text))
                continue
            # Nhãn và giá trị có thể nằm chung ô ("Số hiệu: ABC").
            for label, value in _extract_labeled_fields(text, labels):
                key = _slug(label)
                if key and key not in seen:
                    fields.append(FieldDraft(label=label, value=value, quote=text))
                    seen.add(key)
    return fields


def _measurements(grid: list[list[str]], config: MappingConfig) -> list[MeasurementDraft]:
    measurements: list[MeasurementDraft] = []
    for table in config.result_tables:
        if not table.columns:
            continue
        header_index = next(
            (i for i, row in enumerate(grid) if _row_is_header(row, table.columns)),
            None,
        )
        if header_index is None:
            continue
        data_rows = grid[header_index + 1 :]
        # Bỏ dòng header tầng dưới (ô đầu rỗng, ô khác có chữ) ngay sau header.
        if data_rows and data_rows[0] and not data_rows[0][0].strip():
            data_rows = data_rows[1:]
        for row in data_rows:
            cells = list(row) + [""] * (len(table.columns) - len(row))
            cells = cells[: len(table.columns)]
            if not any(cell.strip() for cell in cells):
                continue
            measurements.append(_map_measurement_row(table.columns, cells))
    return measurements


def read_xlsx(
    path: str | Path, config: MappingConfig, *, section_path: str | None = None
) -> RecordDraft:
    """Đọc một phiếu đo Excel theo ``config``; trả ``RecordDraft`` giữ nguyên văn."""
    grid = _read_grid(path)
    labels = [item.label for item in config.header_fields]
    source_lines = [" | ".join(cell for cell in row if cell.strip()) for row in grid]
    return RecordDraft(
        extractor=EXTRACTOR,
        source_text="\n".join(line for line in source_lines if line),
        section_path=section_path or DEFAULT_SECTION_PATH,
        fields=_header_fields(grid, labels),
        measurements=_measurements(grid, config),
    )
