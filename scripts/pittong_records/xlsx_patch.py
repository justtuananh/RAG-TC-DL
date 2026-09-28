"""Vá ô trực tiếp trên OOXML của tệp mẫu bằng ``zipfile`` + ``lxml``.

Không dùng ``openpyxl``/``xlsxwriter`` và không thêm phụ thuộc. Chuỗi ghi bằng
``t="inlineStr"`` (không đụng ``sharedStrings.xml``), số ghi bằng ``<v>``, ngày
ghi bằng số serial Excel; thuộc tính style ``s`` của ô luôn được giữ nguyên.

Khi vá, mọi ô công thức bị bỏ giá trị cache ``<v>`` để buộc tính lại; gói
``calcChain.xml`` cũng bị gỡ và ``calcPr`` được đặt ``fullCalcOnLoad="1"``.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from datetime import date

from lxml import etree

M_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_M = f"{{{M_NS}}}"
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)

_EXCEL_EPOCH = date(1899, 12, 30)


@dataclass(frozen=True)
class InlineStr:
    """Ghi chuỗi vào ô (``inlineStr``), giữ nguyên style."""

    text: str


@dataclass(frozen=True)
class Number:
    """Ghi số vào ô qua ``<v>``, giữ nguyên style."""

    value: float


@dataclass(frozen=True)
class SerialDate:
    """Ghi ngày dưới dạng số serial Excel, giữ nguyên style ngày của ô."""

    value: date


@dataclass(frozen=True)
class Formula:
    """Ghi công thức mới (bỏ cache cũ) vào ô, giữ nguyên style."""

    text: str


Patch = InlineStr | Number | SerialDate | Formula


def excel_serial(value: date) -> int:
    """Số serial ngày kiểu Excel (hệ 1900)."""
    return (value - _EXCEL_EPOCH).days


def _sheet_paths(workbook: bytes, rels: bytes) -> dict[str, str]:
    """Ánh xạ tên sheet → đường dẫn XML bên trong gói."""
    wb = etree.fromstring(workbook)
    rel_root = etree.fromstring(rels)
    rel_map = {
        rel.get("Id"): rel.get("Target")
        for rel in rel_root.findall(f"{{{PKG_REL_NS}}}Relationship")
    }
    mapping: dict[str, str] = {}
    for sheet in wb.iter(f"{_M}sheet"):
        target = rel_map.get(sheet.get(f"{{{R_NS}}}id"), "")
        mapping[sheet.get("name")] = "xl/" + target.lstrip("/")
    return mapping


def _column_index(ref: str) -> int:
    letters = re.match(r"([A-Za-z]+)", ref or "")
    if not letters:
        return 0
    index = 0
    for char in letters.group(1).upper():
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def _get_cell(root, ref: str):
    """Tìm ô theo địa chỉ; tạo mới (đúng thứ tự) nếu chưa có."""
    for cell in root.iter(f"{_M}c"):
        if cell.get("r") == ref:
            return cell
    row_no = int(re.search(r"(\d+)$", ref).group(1))
    sheet_data = root.find(f"{_M}sheetData")
    row = next((r for r in sheet_data.findall(f"{_M}row") if r.get("r") == str(row_no)), None)
    if row is None:
        row = etree.SubElement(sheet_data, f"{_M}row")
        row.set("r", str(row_no))
        sheet_data.insert(row_no - 1, row)
    cell = etree.Element(f"{_M}c")
    cell.set("r", ref)
    position = 0
    for existing in row.findall(f"{_M}c"):
        if _column_index(existing.get("r")) > _column_index(ref):
            break
        position += 1
    row.insert(position, cell)
    return cell


def _clear_children(cell) -> None:
    for child in list(cell):
        cell.remove(child)


def _set_number(cell, text: str) -> None:
    cell.attrib.pop("t", None)
    _clear_children(cell)
    value = etree.SubElement(cell, f"{_M}v")
    value.text = text


def _apply(cell, patch: Patch) -> None:
    """Áp một bản vá lên ô nhưng không đụng thuộc tính style ``s``."""
    if isinstance(patch, InlineStr):
        cell.set("t", "inlineStr")
        _clear_children(cell)
        container = etree.SubElement(cell, f"{_M}is")
        text_node = etree.SubElement(container, f"{_M}t")
        text_node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        text_node.text = patch.text
    elif isinstance(patch, SerialDate):
        _set_number(cell, str(excel_serial(patch.value)))
    elif isinstance(patch, Number):
        value = patch.value
        text = str(value) if isinstance(value, int) else repr(float(value))
        _set_number(cell, text)
    elif isinstance(patch, Formula):
        name = f"{_M}f"
        formula = cell.find(name)
        if formula is None:
            formula = etree.SubElement(cell, name)
        _clear_children(cell)
        cell.attrib.pop("t", None)
        cell.append(formula)
        formula.text = patch.text
    else:  # pragma: no cover - lập trình sai spec
        raise TypeError(f"Bản vá không rõ: {patch!r}")


def _strip_formula_cache(root) -> None:
    """Bỏ ``<v>`` mọi ô công thức để buộc tính lại."""
    for cell in root.iter(f"{_M}c"):
        if cell.find(f"{_M}f") is not None:
            for value in cell.findall(f"{_M}v"):
                cell.remove(value)
            cell.attrib.pop("t", None)


def _patch_sheet(data: bytes, cells: dict[str, Patch]) -> bytes:
    root = etree.fromstring(data)
    for ref, patch in cells.items():
        _apply(_get_cell(root, ref), patch)
    _strip_formula_cache(root)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _force_full_calc(workbook: bytes) -> bytes:
    """Đặt ``fullCalcOnLoad="1"`` trong ``calcPr`` để LibreOffice tính lại."""
    if b"fullCalcOnLoad" in workbook:
        return workbook
    if b"<calcPr" in workbook:
        return re.sub(rb"<calcPr\b", b'<calcPr fullCalcOnLoad="1"', workbook, count=1)
    return workbook.replace(b"</workbook>", b'<calcPr fullCalcOnLoad="1"/></workbook>')


def _strip_calc_chain(parts: dict[str, bytes]) -> dict[str, bytes]:
    """Gỡ ``calcChain.xml`` cùng khai báo của nó (chuỗi tính toán đã cũ)."""
    parts.pop("xl/calcChain.xml", None)
    content_types = parts.get("[Content_Types].xml", b"")
    parts["[Content_Types].xml"] = re.sub(
        rb'<Override PartName="/xl/calcChain\.xml"[^>]*/>', b"", content_types
    )
    rels = parts.get("xl/_rels/workbook.xml.rels", b"")
    parts["xl/_rels/workbook.xml.rels"] = re.sub(
        rb'<Relationship[^>]*Target="calcChain\.xml"[^>]*/>', b"", rels
    )
    return parts


def _write_zip(path, parts: list[tuple[str, bytes]]) -> None:
    """Ghi zip tất định (thứ tự cố định, cùng một mốc thời gian)."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts:
            info = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, data)


def patch_workbook(src, dst, patches: dict[str, dict[str, Patch]]) -> None:
    """Vá ``src`` bằng ``patches`` (tên sheet → địa chỉ ô → bản vá) ra ``dst``."""
    with zipfile.ZipFile(src) as archive:
        names = archive.namelist()
        parts = {name: archive.read(name) for name in names}
    sheet_paths = _sheet_paths(parts["xl/workbook.xml"], parts["xl/_rels/workbook.xml.rels"])
    for sheet_name, cells in patches.items():
        path = sheet_paths[sheet_name]
        parts[path] = _patch_sheet(parts[path], cells)
    parts["xl/workbook.xml"] = _force_full_calc(parts["xl/workbook.xml"])
    _strip_calc_chain(parts)
    _write_zip(dst, [(name, parts[name]) for name in names if name in parts])


def inject_caches(patched, computed) -> None:
    """Chép ``<v>`` đã tính của LibreOffice vào bản vá và ghi lại ``patched``.

    Nhờ vậy tệp ra giữ nguyên merge, style, độ rộng cột và ``sharedStrings``
    của mẫu, chỉ nhận thêm giá trị cache cho các ô công thức.
    """
    with zipfile.ZipFile(patched) as patched_zip, zipfile.ZipFile(computed) as computed_zip:
        names = patched_zip.namelist()
        parts = {name: patched_zip.read(name) for name in names}
        computed_parts = {name: computed_zip.read(name) for name in computed_zip.namelist()}
    patched_paths = _sheet_paths(parts["xl/workbook.xml"], parts["xl/_rels/workbook.xml.rels"])
    computed_paths = _sheet_paths(
        computed_parts["xl/workbook.xml"], computed_parts["xl/_rels/workbook.xml.rels"]
    )
    for sheet_name, patched_path in patched_paths.items():
        computed_path = computed_paths.get(sheet_name)
        if computed_path is None:
            continue
        parts[patched_path] = _merge_cell_values(parts[patched_path], computed_parts[computed_path])
    _write_zip(patched, [(name, parts[name]) for name in names if name in parts])


def _computed_values(data: bytes) -> dict[str, tuple[str, str | None]]:
    """Ánh xạ địa chỉ ô công thức → (giá trị ``<v>``, thuộc tính ``t``)."""
    root = etree.fromstring(data)
    values: dict[str, tuple[str, str | None]] = {}
    for cell in root.iter(f"{_M}c"):
        if cell.find(f"{_M}f") is None:
            continue
        value = cell.find(f"{_M}v")
        if value is not None:
            values[cell.get("r")] = (value.text, cell.get("t"))
    return values


def _merge_cell_values(patched_data: bytes, computed_data: bytes) -> bytes:
    """Gắn giá trị cache vào các ô công thức của bản vá."""
    values = _computed_values(computed_data)
    root = etree.fromstring(patched_data)
    for cell in root.iter(f"{_M}c"):
        if cell.find(f"{_M}f") is None or cell.get("r") not in values:
            continue
        text, cell_type = values[cell.get("r")]
        for old in cell.findall(f"{_M}v"):
            cell.remove(old)
        node = etree.SubElement(cell, f"{_M}v")
        node.text = text
        if cell_type:
            cell.set("t", cell_type)
        else:
            cell.attrib.pop("t", None)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
