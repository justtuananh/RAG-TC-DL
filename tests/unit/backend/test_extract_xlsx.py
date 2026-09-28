"""Bộ trích bảng tính -> Markdown (ingestion.extract_xlsx).

Tự dựng một workbook nhỏ bằng OOXML thô: tiêu đề 2 tầng bằng ô gộp (A1:A2 dọc,
B1:C1 ngang), một cột trống hoàn toàn, và một ô nhiều dòng, đúng các ca mà bảng
Markdown phải xử lý để giữ hợp lệ.
"""

from __future__ import annotations

import zipfile

import pytest

from ingestion.extract_xlsx import extract_xlsx

_M = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
_XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


def _cell_xml(ref: str, text: str) -> str:
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _write_sheet_xlsx(path, name: str, cells: dict[str, str], merges: list[str]) -> None:
    """Ghi .xlsx tối thiểu với ô inlineStr + vùng gộp (không cần styles/sharedStrings)."""
    rows: dict[int, list[str]] = {}
    for ref, text in cells.items():
        col = "".join(ch for ch in ref if ch.isalpha())
        row = int("".join(ch for ch in ref if ch.isdigit()))
        rows.setdefault(row, []).append(_cell_xml(f"{col}{row}", text))
    row_xml = "".join(f'<row r="{r}">{"".join(sorted(v))}</row>' for r, v in sorted(rows.items()))
    merge_xml = (
        f'<mergeCells count="{len(merges)}">'
        + "".join(f'<mergeCell ref="{ref}"/>' for ref in merges)
        + "</mergeCells>"
        if merges
        else ""
    )
    sheet = (
        f"{_XML_DECL}<worksheet xmlns=\"{_M}\"><sheetData>{row_xml}</sheetData>"
        f"{merge_xml}</worksheet>"
    ).encode()
    workbook = (
        f'{_XML_DECL}<workbook xmlns="{_M}" xmlns:r="{_R}">'
        f'<sheets><sheet name="{name}" sheetId="1" r:id="rId1"/></sheets></workbook>'
    ).encode()
    workbook_rels = (
        f'{_XML_DECL}<Relationships xmlns="{_PKG}">'
        f'<Relationship Id="rId1" Type="{_R}/worksheet" Target="worksheets/sheet1.xml"/>'
        f"</Relationships>"
    ).encode()
    content_types = (
        f'{_XML_DECL}<Types xmlns="{_PKG}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f'<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        f"</Types>"
    ).encode()
    root_rels = (
        f'{_XML_DECL}<Relationships xmlns="{_PKG}">'
        f'<Relationship Id="rId1" Type="{_R}/officeDocument" Target="xl/workbook.xml"/>'
        f"</Relationships>"
    ).encode()
    with zipfile.ZipFile(path, "w") as archive:
        for part, data in [
            ("[Content_Types].xml", content_types),
            ("_rels/.rels", root_rels),
            ("xl/workbook.xml", workbook),
            ("xl/_rels/workbook.xml.rels", workbook_rels),
            ("xl/worksheets/sheet1.xml", sheet),
        ]:
            archive.writestr(part, data)


@pytest.fixture
def minh_hoa_xlsx(tmp_path):
    """Workbook: tiêu đề 2 tầng, cột C trống, ô nhiều dòng ở B3."""
    path = tmp_path / "danh-muc.xlsx"
    _write_sheet_xlsx(
        path,
        "NAS-2022",
        {
            "A1": "TT",
            "B1": "PHƯƠNG TIỆN ĐO ÁP SUẤT",
            "D1": "GHI CHÚ",
            "B2": "Tên",
            "C2": "Dải đo",
            "A3": "1",
            "B3": "Dòng 1\nDòng 2",
            "C3": "0 - 10",
            "D3": "ok",
            "A4": "2",
            "B4": "abc",
            "C4": "10 - 20",
        },
        merges=["A1:A2", "B1:C1"],
    )
    return path


def test_sheet_heading_and_two_level_header(minh_hoa_xlsx):
    result = extract_xlsx(minh_hoa_xlsx)
    assert "# NAS-2022" in result.markdown
    assert "PHƯƠNG TIỆN ĐO ÁP SUẤT - Tên" in result.markdown
    assert "PHƯƠNG TIỆN ĐO ÁP SUẤT - Dải đo" in result.markdown
    # A1:A2 gộp dọc: tiêu đề không bị lặp "TT - TT".
    assert "| TT |" in result.markdown


def test_multiline_cell_becomes_single_line(minh_hoa_xlsx):
    result = extract_xlsx(minh_hoa_xlsx)
    assert "Dòng 1 / Dòng 2" in result.markdown
    assert "Dòng 1\nDòng 2" not in result.markdown


def test_empty_column_removed(tmp_path):
    """Cột không có dữ liệu ở bất kỳ dòng nào bị bỏ khỏi bảng."""
    path = tmp_path / "thua-cot.xlsx"
    _write_sheet_xlsx(
        path,
        "S",
        {"A1": "A", "B1": "B", "D1": "D", "A2": "1", "B2": "2", "D2": "4"},
        merges=[],
    )
    result = extract_xlsx(path)
    header = next(line for line in result.markdown.splitlines() if line.startswith("| A"))
    assert header.count("|") == 4  # 3 cột giữ lại -> 4 dấu |
    assert "Cột" not in header


def test_counts_for_report(minh_hoa_xlsx):
    result = extract_xlsx(minh_hoa_xlsx)
    assert result.n_sheets == 1
    assert result.n_tables == 1
    assert result.n_rows == 2
