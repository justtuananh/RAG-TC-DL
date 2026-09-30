"""Định vị trích dẫn ``a | b | c`` về đúng sheet/dòng/ô của tệp Excel (P1).

Bề mặt xuất xứ của biên bản Excel không có Markdown: trích dẫn là các ô không rỗng
của một dòng nối bằng `` | ``. Bộ định vị trả toạ độ thật để giao diện vẽ lại đúng
lưới ô gốc và tô sáng ô chứa giá trị, thay vì in chuỗi có dấu ``|``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from query.sheet_locate import locate_in_file, locate_quote
from records.xlsx_grid import Sheet

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "scripts" / "pittong_records" / "template.xlsx"


def _sheets() -> list[Sheet]:
    return [
        Sheet(name="Chọn quả", rows=[["Quả số", "Khối lượng"], ["Gốc", "67,5707"]]),
        Sheet(
            name="KQ KĐ",
            rows=[
                ["TRUNG TÂM", "", "", "KẾT QUẢ"],
                [],
                ["Ký hiệu:  ", "МП-60", "Số hiệu:", "1045", "3", "3", "67,5707"],
                ["Phạm vi đo: (1 đến 60) kgf/cm2;", "", "", "6", "6", "168,9342"],
            ],
        ),
    ]


def test_full_row_quote_locates_sheet_row_and_cells():
    location = locate_quote(
        _sheets(), "Ký hiệu: | МП-60 | Số hiệu: | 1045 | 3 | 3 | 67,5707", "МП-60"
    )
    assert location == {
        "sheet": "KQ KĐ",
        "sheet_index": 1,
        "row": 2,
        "cols": [0, 1, 2, 3, 4, 5, 6],
        "highlight_cols": [1],
    }


def test_partial_row_quote_matches_contiguous_cells():
    location = locate_quote(_sheets(), "6 | 6 | 168,9342", "168,9342")
    assert location is not None
    assert (location["sheet"], location["row"]) == ("KQ KĐ", 3)
    assert location["cols"] == [3, 4, 5]
    assert location["highlight_cols"] == [5]


def test_value_inside_label_cell_highlights_that_cell():
    location = locate_quote(
        _sheets(), "Phạm vi đo: (1 đến 60) kgf/cm2; | 6 | 6 | 168,9342", "(1 đến 60) kgf/cm2;"
    )
    assert location is not None
    assert location["highlight_cols"] == [0]


def test_without_value_highlights_every_matched_cell():
    location = locate_quote(_sheets(), "Gốc | 67,5707", None)
    assert location is not None
    assert location["sheet_index"] == 0
    assert location["highlight_cols"] == location["cols"] == [0, 1]


def test_empty_cells_inside_quote_are_ignored():
    location = locate_quote(_sheets(), "TRUNG TÂM |  |  | KẾT QUẢ", None)
    assert location is not None
    assert location["cols"] == [0, 3]


def test_unknown_or_empty_quote_returns_none():
    assert locate_quote(_sheets(), "không có dòng này", None) is None
    assert locate_quote(_sheets(), " |  | ", None) is None
    assert locate_quote(_sheets(), None, None) is None


def test_locate_in_real_record_file():
    location = locate_in_file(TEMPLATE, "Ký hiệu: | МП-6M", "МП-6M")
    assert location is not None
    assert location["highlight_cols"]
    assert location["row"] >= 0


def test_locate_in_file_tolerates_non_spreadsheet(tmp_path):
    bogus = tmp_path / "x.xlsx"
    bogus.write_bytes(b"not a zip")
    assert locate_in_file(bogus, "a | b", None) is None


def test_source_view_of_spreadsheet_carries_location(monkeypatch):
    import ingestion_jobs
    from query.source import build_source_view

    monkeypatch.setattr(ingestion_jobs, "get_markdown", lambda stem: None)
    monkeypatch.setattr(ingestion_jobs, "get_source_path", lambda stem: TEMPLATE)
    monkeypatch.setattr(ingestion_jobs, "get_preview_path", lambda stem: TEMPLATE)
    view = build_source_view(
        file_stem="BB", section_path="Phiếu đo", quote="Ký hiệu: | МП-6M", value="МП-6M"
    )
    assert view["section_text"] is None
    assert view["source_location"] is not None
    assert view["source_location"]["highlight_cols"]


def test_source_view_of_word_record_has_no_location(tmp_path, monkeypatch):
    import ingestion_jobs
    from query.source import build_source_view

    monkeypatch.setattr(ingestion_jobs, "get_markdown", lambda stem: None)
    monkeypatch.setattr(ingestion_jobs, "get_source_path", lambda stem: tmp_path / "BB.docx")
    view = build_source_view(file_stem="BB", section_path=None, quote="a | b", value="a")
    assert view["source_location"] is None


def test_row_quote_locates_the_right_row_for_a_bare_cell_value(monkeypatch):
    import ingestion_jobs
    import query.sheet_locate as sheet_locate
    from query.source import build_source_view

    sheets = [
        Sheet(
            name="KQ KĐ",
            rows=[
                ["Tiết diện", "2,3"],
                ["Độ không vuông góc của đĩa cân với trục pít tông", "2,3", "< 5'"],
            ],
        )
    ]
    monkeypatch.setattr(ingestion_jobs, "get_markdown", lambda stem: None)
    monkeypatch.setattr(ingestion_jobs, "get_source_path", lambda stem: TEMPLATE)
    monkeypatch.setattr(ingestion_jobs, "get_preview_path", lambda stem: TEMPLATE)
    monkeypatch.setattr(sheet_locate, "read_sheets", lambda path: sheets)

    bare = build_source_view(file_stem="BB", section_path=None, quote="2,3", value="2,3")
    assert bare["source_location"]["row"] == 0  # chỉ có giá trị: khớp nhầm ô đầu tiên

    with_row = build_source_view(
        file_stem="BB",
        section_path=None,
        quote="2,3",
        value="2,3",
        sheet_quote="Độ không vuông góc của đĩa cân với trục pít tông | 2,3 | < 5'",
    )
    assert with_row["source_location"]["row"] == 1
    assert with_row["source_location"]["highlight_cols"] == [1]


def test_value_part_disambiguates_duplicate_cells_in_a_row():
    sheets = [Sheet(name="KQ", rows=[["5", "6", "6", "0,1"]])]
    ambiguous = locate_quote(sheets, "5 | 6 | 6 | 0,1", "6")
    assert ambiguous["highlight_cols"] == [1, 2]
    exact = locate_quote(sheets, "5 | 6 | 6 | 0,1", "6", value_part=2)
    assert exact["highlight_cols"] == [2]
    # vị trí không khớp giá trị (dữ liệu lệch) thì quay về dò theo giá trị
    assert locate_quote(sheets, "5 | 6 | 6 | 0,1", "6", value_part=3)["highlight_cols"] == [1, 2]


def test_cell_part_follows_the_reader_role_of_each_column():
    from query.provenance import cell_part

    cells = [
        {"column": "TT", "text": "1"},
        {"column": "Giá trị danh nghĩa", "text": "6"},
        {"column": "Ghi chú", "text": ""},
        {"column": "Giá trị đo", "text": "6"},
    ]
    assert cell_part(cells, "measured") == 2  # ô rỗng không tính vào trích dẫn
    assert cell_part(cells, "nominal") == 1
    assert cell_part(cells, "limit") is None
    assert cell_part(None, "measured") is None
