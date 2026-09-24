"""Bộ đọc bảng Markdown: header hai tầng, ô gộp, và an toàn khi không khớp."""

from __future__ import annotations

from knowledge.rules.markdown_tables import parse_tables

TWO_LEVEL = """\
Bảng 1 - Các phép kiểm định

| TT | Tên phép kiểm định | Theo điều (mục) của QTKĐ | Chế độ kiểm định |  |  |
| --- | --- | --- | --- | --- | --- |
|  |  |  | Ban đầu | Định kỳ | Sau sửa chữa |
| 1 | Kiểm tra bên ngoài | 6.1 | + | + | + |
| 2 | Kiểm tra kỹ thuật | 6.2 | + |  | + |
"""

TWO_COLUMN = """\
| TT | Tên phương tiện kiểm định | Đặc trưng kỹ thuật đo lường |  |
| --- | --- | --- | --- |
|  |  | Phạm vi đo | Cấp chính xác |
| 1 | Ẩm kế | (0 ÷ 100) %RH | ± 5 %RH |
"""


def test_two_level_header_is_combined_per_column():
    table = parse_tables(TWO_LEVEL)[0]
    assert table.headers[0] == "TT"
    assert table.headers[1] == "Tên phép kiểm định"
    assert table.headers[3] == "Chế độ kiểm định Ban đầu"
    assert table.headers[4] == "Định kỳ"
    assert table.headers[5] == "Sau sửa chữa"


def test_subheader_row_not_treated_as_data():
    table = parse_tables(TWO_LEVEL)[0]
    assert [row.cells[0] for row in table.rows] == ["1", "2"]


def test_two_level_headers_two_columns():
    table = parse_tables(TWO_COLUMN)[0]
    assert table.headers[2] == "Đặc trưng kỹ thuật đo lường Phạm vi đo"
    assert table.headers[3] == "Cấp chính xác"
    assert table.rows[0].cells[1] == "Ẩm kế"


def test_row_offsets_point_at_raw_line():
    text = TWO_LEVEL
    table = parse_tables(text)[0]
    for row in table.rows:
        assert text[row.start : row.end] == row.raw
        assert row.raw.startswith("|")


def test_no_table_returns_empty():
    assert parse_tables("Chỉ là văn xuôi, không có bảng.") == []


def test_table_without_data_rows_is_returned_empty():
    text = "| A | B |\n| --- | --- |\n"
    tables = parse_tables(text)
    assert len(tables) == 1
    assert tables[0].rows == ()


def test_base_offset_applied_to_rows():
    table = parse_tables(TWO_LEVEL, base_offset=1000)[0]
    assert table.rows[0].start >= 1000
