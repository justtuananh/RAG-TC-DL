"""Xuất Excel kèm cột xuất xứ cho kết quả lọc hiện tại (spec §9 S8).

Không thêm phụ thuộc: bộ ghi XLSX tối giản dùng ``zipfile`` + XML (cùng tinh thần
với ``records/xlsx_reader`` — đọc/ghi OOXML thô). Mỗi giá trị số/ngày đi kèm một
cột nguồn chỉ rõ tài liệu · mục · chunk sinh ra nó (P1), để bảng xuất ra vẫn đối
chiếu được chứ không phải một bảng số rời nguồn.
"""

from __future__ import annotations

import zipfile
from collections.abc import Callable
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

# Tiêu đề cột (Việt) và thứ tự — cột nguồn xen ngay sau ô số tương ứng.
EXPORT_HEADERS: tuple[str, ...] = (
    "STT",
    "Số hiệu",
    "Loại thiết bị",
    "Đại lượng",
    "Ký hiệu/Model",
    "Hãng sản xuất",
    "Đơn vị sử dụng",
    "QTKĐ",
    "Chế độ",
    "Ngày kiểm định",
    "Nguồn ngày kiểm định",
    "Hết hiệu lực",
    "Nguồn hết hiệu lực",
    "Kết luận",
    "Nhiệt độ (°C)",
    "Nguồn nhiệt độ",
    "Độ ẩm (%RH)",
    "Nguồn độ ẩm",
    "Phạm vi đo – nhỏ nhất (SI)",
    "Phạm vi đo – lớn nhất (SI)",
    "Đơn vị phạm vi",
    "Nguồn phạm vi",
    "Cấp chính xác",
    "Nguồn cấp chính xác",
    "Số điểm đo",
    "Tài liệu nguồn",
    "Mục nguồn",
    "Chunk nguồn",
    "Trích dẫn nguồn",
)

FactLookup = Callable[[int], dict[str, Any] | None]


def _column_letter(index: int) -> str:
    """0 → A, 25 → Z, 26 → AA…"""
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _cell_xml(ref: str, value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        value = "Đạt" if value else "Không"
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"><v>{value}</v></c>'
    return (
        f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'
    )


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    "</Types>"
)
_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
    "</Relationships>"
)
_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
    '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="2"><fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill></fills>'
    '<borders count="1"><border/></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/></cellXfs>'
    "</styleSheet>"
)


def _workbook_xml(sheet_name: str) -> str:
    safe = escape(sheet_name[:31] or "Sheet1")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{safe}" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )


_WORKBOOK_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    "</Relationships>"
)


def _sheet_xml(headers: list[str], rows: list[list[Any]]) -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    parts.append(
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    )
    header_cells = "".join(
        _cell_xml(f"{_column_letter(col)}1", value) for col, value in enumerate(headers)
    )
    parts.append(f'<row r="1">{header_cells}</row>')
    # Header in đậm: đánh lại style s="1" cho các ô tiêu đề.
    parts[-1] = parts[-1].replace('t="inlineStr"', 't="inlineStr" s="1"')
    for row_index, row in enumerate(rows, start=2):
        cells = "".join(
            _cell_xml(f"{_column_letter(col)}{row_index}", value) for col, value in enumerate(row)
        )
        parts.append(f'<row r="{row_index}">{cells}</row>')
    parts.append("</sheetData></worksheet>")
    return "".join(parts)


def build_xlsx(sheet_name: str, headers: list[str], rows: list[list[Any]]) -> bytes:
    """Đóng gói một bảng thành tệp ``.xlsx`` hợp lệ (inline string, không phụ thuộc)."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _ROOT_RELS)
        archive.writestr("xl/workbook.xml", _workbook_xml(sheet_name))
        archive.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        archive.writestr("xl/styles.xml", _STYLES)
        archive.writestr("xl/worksheets/sheet1.xml", _sheet_xml(headers, rows))
    return buffer.getvalue()


def _source_ref(*, file_stem: Any, section_path: Any, chunk_id: Any) -> str:
    parts = [str(part) for part in (file_stem, section_path, chunk_id) if part]
    return " › ".join(parts) if parts else ""


def _fact_ref(fact_id: Any, lookup: FactLookup | None) -> str:
    if fact_id is None:
        return ""
    if lookup is not None:
        try:
            source = lookup(int(fact_id))
        except Exception:  # noqa: BLE001 - cột nguồn không được chặn xuất tệp
            source = None
        if source:
            ref = _source_ref(
                file_stem=source.get("file_stem"),
                section_path=source.get("section_path"),
                chunk_id=source.get("chunk_id"),
            )
            if ref:
                return f"{ref} · dữ kiện #{fact_id}"
    return f"dữ kiện #{fact_id}"


def build_export_rows(
    records: list[dict[str, Any]],
    fact_lookup: FactLookup | None = None,
) -> list[list[Any]]:
    """Ánh xạ hồ sơ đã duyệt sang hàng Excel, xen cột nguồn sau mỗi ô số."""
    rows: list[list[Any]] = []
    for index, record in enumerate(records, start=1):
        record_ref = _source_ref(
            file_stem=record.get("file_stem"),
            section_path=record.get("extraction_section_path"),
            chunk_id=record.get("extraction_chunk_id"),
        )
        range_ref = _fact_ref(record.get("range_fact_id"), fact_lookup)
        accuracy_ref = _fact_ref(record.get("accuracy_fact_id"), fact_lookup)
        expires_ref = record_ref
        if record.get("expires_from_fact_id") is not None:
            expires_ref = _fact_ref(record.get("expires_from_fact_id"), fact_lookup)

        rows.append(
            [
                index,
                record.get("serial_no"),
                record.get("device_type_name"),
                record.get("quantity_name"),
                record.get("model_code"),
                record.get("manufacturer"),
                record.get("owner_org"),
                record.get("procedure_number"),
                record.get("mode_label"),
                record.get("calibrated_at"),
                record_ref,
                record.get("expires_at"),
                expires_ref,
                record.get("verdict_label"),
                record.get("env_temp_c"),
                record_ref,
                record.get("env_humidity_pct"),
                record_ref,
                record.get("range_min"),
                record.get("range_max"),
                record.get("range_unit_code"),
                range_ref,
                record.get("accuracy_text"),
                accuracy_ref,
                record.get("measurement_count"),
                record.get("file_stem"),
                record.get("extraction_section_path"),
                record.get("extraction_chunk_id"),
                record.get("extraction_quote"),
            ]
        )
    return rows


def records_xlsx(
    records: list[dict[str, Any]],
    fact_lookup: FactLookup | None = None,
    *,
    sheet_name: str = "Du lieu kiem dinh",
) -> bytes:
    """Tệp ``.xlsx`` của danh sách hồ sơ đã lọc, kèm cột xuất xứ."""
    return build_xlsx(sheet_name, list(EXPORT_HEADERS), build_export_rows(records, fact_lookup))
