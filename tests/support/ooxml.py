"""OOXML thô (docx/xlsx) cho bộ dữ liệu test lớp tri thức (Pha 2).

Không dùng python-docx/openpyxl để không thêm phụ thuộc runtime - chỉ
``zipfile`` + ``lxml`` (Việt hoá theo phong cách ``scripts/make_record_fixtures.py``).

Tất định: mọi hàm ``write_*`` ghi entry theo THỨ TỰ CỐ ĐỊNH, ``ZipInfo.date_time``
luôn là ``(1980, 1, 1, 0, 0, 0)`` và không có timestamp/uuid ngẫu nhiên nào trong
nội dung - gọi lại hai lần cho ra file giống hệt byte.

``styles_xml()`` định nghĩa các styleId ``heading1``..``heading9`` (+ ``Title``)
để Word/LibreOffice hiển thị đúng, và hai style tiêu đề "bản địa hoá" cho ca biên
K13 (K13: ``_heading_level`` phân giải styleId qua ``word/styles.xml``):

- ``TieuDeMuc1`` có ``w:name="heading 1"`` (nhận diện qua tên dựng sẵn);
- ``MucCon2`` có ``basedOn="TieuDeMuc1"`` (nhận diện qua chuỗi ``basedOn``).
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from datetime import date
from xml.sax.saxutils import escape as _xml_escape

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def _write_zip(path, parts: list[tuple[str, bytes]]) -> None:
    """Ghi zip tất định: thứ tự ``parts`` cố định, mọi ``ZipInfo`` cùng một ngày."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts:
            info = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, data)


def esc(text: object) -> str:
    """Escape XML, giữ ``xml:space="preserve"`` an toàn cho khoảng trắng Việt."""
    return _xml_escape(str(text if text is not None else ""))


# ─────────────────────────── DOCX: styles.xml ────────────────────────────────

_HEADING_STYLE_TPL = """<w:style w:type="paragraph" w:styleId="heading{n}">
  <w:name w:val="heading {n}"/>
  <w:basedOn w:val="Normal"/>
  <w:pPr><w:outlineLvl w:val="{lvl0}"/></w:pPr>
  <w:rPr><w:b/><w:sz w:val="{sz}"/></w:rPr>
</w:style>"""


def styles_xml() -> bytes:
    headings = []
    for n in range(1, 10):
        sz = max(20, 32 - (n - 1) * 2)
        headings.append(_HEADING_STYLE_TPL.format(n=n, lvl0=n - 1, sz=sz))
    body = "".join(headings)
    xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W_NS}">
  <w:docDefaults>
    <w:rPrDefault><w:rPr><w:sz w:val="22"/></w:rPr></w:rPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr><w:b/><w:sz w:val="36"/></w:rPr>
  </w:style>
  {body}
  <w:style w:type="paragraph" w:styleId="TieuDeMuc1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr><w:b/><w:sz w:val="28"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="MucCon2">
    <w:name w:val="Muc con 2"/>
    <w:basedOn w:val="TieuDeMuc1"/>
    <w:rPr><w:i/><w:sz w:val="24"/></w:rPr>
  </w:style>
</w:styles>"""
    return xml.encode("utf-8")


# ─────────────────────────── DOCX: body building ─────────────────────────────


@dataclass(frozen=True)
class Cell:
    """Một ô bảng docx; ``span`` là số cột grid mà ô này chiếm (``gridSpan``)."""

    text: str = ""
    span: int = 1
    vmerge: str | None = None  # "restart" | "continue" | None


CellLike = str | Cell


def _as_cell(value: CellLike) -> Cell:
    return value if isinstance(value, Cell) else Cell(text=str(value))


def heading(text: str, level: int = 1, *, style: str | None = None) -> dict:
    return {"t": "h", "lvl": level, "text": text, "style": style or f"heading{level}"}


def para(text: str) -> dict:
    return {"t": "p", "text": text}


def table(rows: list[list[CellLike]], grid_cols: int | None = None) -> dict:
    """``rows``: mỗi hàng là danh sách ``Cell``/``str``; ô cuối có thể ``span>1``."""
    norm_rows = [[_as_cell(c) for c in row] for row in rows]
    if grid_cols is None:
        grid_cols = max((sum(c.span for c in row) for row in norm_rows), default=1)
    return {"t": "tbl", "rows": norm_rows, "grid_cols": grid_cols}


def _run(text: str) -> str:
    return f'<w:r><w:t xml:space="preserve">{esc(text)}</w:t></w:r>'


def _p_xml(text: str, style: str | None) -> str:
    ppr = f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>" if style else ""
    return f"<w:p>{ppr}{_run(text)}</w:p>"


def _tc_xml(cell: Cell) -> str:
    ppr_parts = []
    if cell.span > 1:
        ppr_parts.append(f'<w:gridSpan w:val="{cell.span}"/>')
    if cell.vmerge is not None:
        val = "" if cell.vmerge == "restart" else f' w:val="{cell.vmerge}"'
        ppr_parts.append(f"<w:vMerge{val}/>")
    tcpr = f"<w:tcPr>{''.join(ppr_parts)}</w:tcPr>" if ppr_parts else ""
    return f"<w:tc>{tcpr}<w:p>{_run(cell.text)}</w:p></w:tc>"


def _tbl_xml(rows: list[list[Cell]], grid_cols: int) -> str:
    grid = "".join('<w:gridCol w:w="1200"/>' for _ in range(grid_cols))
    trs = "".join(f"<w:tr>{''.join(_tc_xml(c) for c in row)}</w:tr>" for row in rows)
    borders = (
        "<w:tblBorders>"
        + "".join(
            f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
            for side in ("top", "left", "bottom", "right", "insideH", "insideV")
        )
        + "</w:tblBorders>"
    )
    return (
        "<w:tbl>"
        f'<w:tblPr><w:tblW w:w="0" w:type="auto"/>{borders}</w:tblPr>'
        f"<w:tblGrid>{grid}</w:tblGrid>"
        f"{trs}"
        "</w:tbl>"
    )


def _body_xml(blocks: list[dict]) -> str:
    parts = []
    for block in blocks:
        if block["t"] == "h":
            parts.append(_p_xml(block["text"], block["style"]))
        elif block["t"] == "p":
            parts.append(_p_xml(block["text"], None))
        elif block["t"] == "tbl":
            parts.append(_tbl_xml(block["rows"], block["grid_cols"]))
        else:  # pragma: no cover - lập trình sai spec
            raise ValueError(f"Loại khối không rõ: {block['t']}")
    return "".join(parts)


_DOCX_CONTENT_TYPES = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

_DOCX_ROOT_RELS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{PKG_REL_NS}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""".encode()

_DOCX_DOC_RELS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{PKG_REL_NS}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""".encode()


def write_docx(path, blocks: list[dict]) -> None:
    """Ghi một .docx tất định gồm ``blocks`` (xem ``heading``/``para``/``table``)."""
    body = _body_xml(blocks)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W_NS}"><w:body>{body}'
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'
        "</w:body></w:document>"
    ).encode()
    parts = [
        ("[Content_Types].xml", _DOCX_CONTENT_TYPES),
        ("_rels/.rels", _DOCX_ROOT_RELS),
        ("word/document.xml", document),
        ("word/_rels/document.xml.rels", _DOCX_DOC_RELS),
        ("word/styles.xml", styles_xml()),
    ]
    _write_zip(path, parts)


# ─────────────────────────── XLSX ─────────────────────────────────────────────


@dataclass(frozen=True)
class DateCell:
    value: date


@dataclass(frozen=True)
class Sheet:
    name: str
    rows: list[list[object]] = field(default_factory=list)


def excel_serial(d: date) -> int:
    """Số serial ngày kiểu Excel (hệ 1900), dùng cho ô ngày ``DateCell``."""
    epoch = date(1899, 12, 30)
    return (d - epoch).days


def _col_letter(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def _sheet_xml(rows: list[list[object]], shared_index: dict[str, int], shared: list[str]) -> bytes:
    rows_xml = []
    for row_number, row in enumerate(rows, start=1):
        cells_xml = []
        for column, value in enumerate(row):
            if value is None or value == "":
                continue
            ref = f"{_col_letter(column)}{row_number}"
            if isinstance(value, DateCell):
                serial = excel_serial(value.value)
                cells_xml.append(f'<c r="{ref}" s="1"><v>{serial}</v></c>')
            elif isinstance(value, bool):
                cells_xml.append(f'<c r="{ref}"><v>{int(value)}</v></c>')
            elif isinstance(value, (int, float)):
                cells_xml.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                text = str(value)
                if text not in shared_index:
                    shared_index[text] = len(shared)
                    shared.append(text)
                cells_xml.append(f'<c r="{ref}" t="s"><v>{shared_index[text]}</v></c>')
        rows_xml.append(f'<row r="{row_number}">{"".join(cells_xml)}</row>')
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{M_NS}"><sheetData>{"".join(rows_xml)}</sheetData></worksheet>'
    )
    return xml.encode("utf-8")


_XLSX_STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="{M_NS}">
  <numFmts count="1">
    <numFmt numFmtId="164" formatCode="dd/mm/yyyy"/>
  </numFmts>
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="2">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
  </cellXfs>
</styleSheet>""".encode()

_XLSX_CONTENT_TYPES_TPL = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
{sheet_overrides}</Types>"""

_XLSX_ROOT_RELS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{PKG_REL_NS}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""".encode()


def write_xlsx(path, sheets: list[Sheet]) -> None:
    """Ghi một .xlsx tất định, nhiều sheet; sheet đầu là sheet chính (đọc bởi bộ đọc)."""
    shared: list[str] = []
    shared_index: dict[str, int] = {}
    sheet_parts: list[tuple[str, bytes]] = []
    sheet_entries = []
    wb_rels = []
    for i, sheet in enumerate(sheets, start=1):
        sheet_parts.append(
            (f"xl/worksheets/sheet{i}.xml", _sheet_xml(sheet.rows, shared_index, shared))
        )
        sheet_entries.append(f'<sheet name="{esc(sheet.name)}" sheetId="{i}" r:id="rId{i}"/>')
        wb_rels.append(
            f'<Relationship Id="rId{i}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{i}.xml"/>'
        )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{M_NS}" xmlns:r="{R_NS}">'
        f'<sheets>{"".join(sheet_entries)}</sheets></workbook>'
    ).encode()
    workbook_rels = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{PKG_REL_NS}">{"".join(wb_rels)}</Relationships>'
    ).encode()
    shared_items = "".join(f'<si><t xml:space="preserve">{esc(s)}</t></si>' for s in shared)
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="{M_NS}" count="{len(shared)}" uniqueCount="{len(shared)}">{shared_items}</sst>'
    ).encode()
    sheet_overrides = "".join(
        f'  <Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
        for i in range(1, len(sheets) + 1)
    )
    content_types = _XLSX_CONTENT_TYPES_TPL.format(sheet_overrides=sheet_overrides).encode("utf-8")

    parts = [
        ("[Content_Types].xml", content_types),
        ("_rels/.rels", _XLSX_ROOT_RELS),
        ("xl/workbook.xml", workbook),
        ("xl/_rels/workbook.xml.rels", workbook_rels),
        ("xl/styles.xml", _XLSX_STYLES),
        *sheet_parts,
        ("xl/sharedStrings.xml", shared_xml),
    ]
    _write_zip(path, parts)
