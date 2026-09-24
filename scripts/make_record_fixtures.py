#!/usr/bin/env python
"""Sinh tệp mẫu hồ sơ kiểm định (đã làm sạch) cho test Sprint 7.

Vì repo chưa có hồ sơ thật, script này tạo hai mẫu tối giản nhưng đúng cấu trúc
OOXML để test bộ đọc mà không cần Word/Excel:

- ``tests/data/record_bien_ban.docx`` — biên bản kiểm định van an toàn;
- ``tests/data/record_phieu_do.xlsx`` — phiếu đo có bảng kết quả.

Chạy lại: ``python scripts/make_record_fixtures.py``.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tests" / "data"

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def _paragraph(text: str) -> str:
    return f"<w:p><w:r><w:t xml:space=\"preserve\">{text}</w:t></w:r></w:p>"


def _table(rows: list[list[str]]) -> str:
    trs = []
    for row in rows:
        cells = "".join(
            f"<w:tc><w:p><w:r><w:t xml:space=\"preserve\">{cell}</w:t></w:r></w:p></w:tc>"
            for cell in row
        )
        trs.append(f"<w:tr>{cells}</w:tr>")
    return f"<w:tbl>{''.join(trs)}</w:tbl>"


def _docx_document() -> str:
    paragraphs = [
        "BIÊN BẢN KIỂM ĐỊNH",
        "Tên phương tiện đo: Van an toàn",
        "Ký hiệu: VA-100",
        "Số hiệu: SN-2024-001",
        "Nơi (hãng) sản xuất: Công ty ABC",
        "Đơn vị sử dụng: Nhà máy X",
        "Số giấy chứng nhận: GCN-001",
        "Người kiểm định: Nguyễn Văn A",
        "Người soát lại: Nguyễn Văn B",
        "Nhiệt độ: 20",
        "Độ ẩm: 55",
        "Chế độ kiểm định: Định kỳ",
        "Ngày kiểm định: 15/01/2024",
        "Kết luận: Đạt",
    ]
    body = "".join(_paragraph(text) for text in paragraphs)
    body += _table(
        [
            ["Lần kiểm tra", "Áp suất", "Sai số", "Ghi chú"],
            ["1", "10,5", "0,2", ""],
            ["2", "10,6", "0,3", ""],
            ["3", "10,4", "-0,1", ""],
        ]
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )


def make_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _DOC_RELS)
        archive.writestr("word/document.xml", _docx_document())


_XLSX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>"""

_XLSX_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_XLSX_WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="PhieuDo" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""

_XLSX_WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""

# Nội dung phiếu đo: (giá trị, là số?) — chuỗi dùng shared string.
_SHEET: list[list[object]] = [
    ["PHIẾU ĐO", "", "", "", "", ""],
    ["Tên phương tiện đo:", "Van an toàn", "", "", "", ""],
    ["Số hiệu:", "SN-2024-002", "", "", "", ""],
    ["Ký hiệu:", "VA-200", "", "", "", ""],
    ["Ngày kiểm định:", "20/02/2024", "", "", "", ""],
    ["Chế độ kiểm định:", "Định kỳ", "", "", "", ""],
    ["Kết luận:", "Không đạt", "", "", "", ""],
    ["Nhiệt độ:", "21", "", "", "", ""],
    ["Độ ẩm:", "60", "", "", "", ""],
    ["", "", "", "", "", ""],
    ["Lần kiểm tra", "Giá trị danh nghĩa", "Giá trị đo", "Sai số", "Giới hạn", "Ghi chú"],
    [1, 10.0, 10.1, 0.1, 0.5, ""],
    [2, 10.0, 10.2, 0.2, 0.5, ""],
    [3, 10.0, 9.8, -0.2, 0.5, ""],
]


def _column_letter(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def _sheet_xml() -> str:
    shared: list[str] = []
    shared_index: dict[str, int] = {}
    rows_xml: list[str] = []
    for row_number, row in enumerate(_SHEET, start=1):
        cells_xml: list[str] = []
        for column, value in enumerate(row):
            if value == "":
                continue
            ref = f"{_column_letter(column)}{row_number}"
            if isinstance(value, (int, float)):
                cells_xml.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                text = str(value)
                if text not in shared_index:
                    shared_index[text] = len(shared)
                    shared.append(text)
                cells_xml.append(f'<c r="{ref}" t="s"><v>{shared_index[text]}</v></c>')
        rows_xml.append(f'<row r="{row_number}">{"".join(cells_xml)}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(rows_xml)}</sheetData></worksheet>"
    )
    shared_items = "".join(f"<si><t xml:space=\"preserve\">{item}</t></si>" for item in shared)
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(shared)}" uniqueCount="{len(shared)}">{shared_items}</sst>'
    )
    return sheet, shared_xml


def make_xlsx(path: Path) -> None:
    sheet_xml, shared_xml = _sheet_xml()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _XLSX_CONTENT_TYPES)
        archive.writestr("_rels/.rels", _XLSX_ROOT_RELS)
        archive.writestr("xl/workbook.xml", _XLSX_WORKBOOK)
        archive.writestr("xl/_rels/workbook.xml.rels", _XLSX_WORKBOOK_RELS)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        archive.writestr("xl/sharedStrings.xml", shared_xml)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    make_docx(DATA / "record_bien_ban.docx")
    make_xlsx(DATA / "record_phieu_do.xlsx")
    print(f"Đã ghi mẫu vào {DATA}")


if __name__ == "__main__":
    main()
