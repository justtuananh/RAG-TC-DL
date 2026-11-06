"""retrieval.table_linearize - bảng hai tầng tiêu đề -> dòng văn bản."""

from retrieval.table_linearize import linearize_tables

TABLE = """Bảng 2 - Danh mục

| TT | Tên phương tiện | Đặc trưng kỹ thuật đo lường |  |
| --- | --- | --- | --- |
|  |  | Phạm vi đo | Sai số |
| 1 | Áp kế chuẩn | Phù hợp | Sai số ≤ ± 1% |
| 2 | Nhiệt kế | (0 đến 35) oC | Sai số ≤ 0,4 oC |
|  |  |  | Ghi chú thêm |
| 3 | Ni vô |  | ± 2' |

CHÚ THÍCH: hết"""


def test_two_level_header_and_values_kept():
    out = linearize_tables(TABLE)
    assert "- 2. Nhiệt kế: Phạm vi đo = (0 đến 35) oC" in out
    assert "Sai số = Sai số ≤ 0,4 oC" in out
    assert "(tiếp) Sai số = Ghi chú thêm" in out
    assert "- 3. Ni vô: Sai số = ± 2'" in out
    assert "Bảng 2 - Danh mục" in out and "CHÚ THÍCH: hết" in out
    assert "| TT |" not in out


def test_fallback_when_first_column_not_tt():
    t = "| P (bar) | Số đọc | Sai số |\n| --- | --- | --- |\n| 10 | 10,1 | 0,1 |"
    assert linearize_tables(t) == t


def test_fallback_when_truncated_without_header():
    t = "…\n| 5 | Thước | (0 đến 500) mm | ± 1 mm |"
    assert linearize_tables(t) == t


def test_fallback_on_ragged_rows():
    t = "| TT | A | B |\n| --- | --- | --- |\n| 1 | x |\n"
    assert linearize_tables(t) == t


def test_plain_text_untouched():
    assert linearize_tables("a\n\nb | c") == "a\n\nb | c"


LONG = """| TT | Tên | Đặc trưng kỹ thuật đo lường |  |
| --- | --- | --- | --- |
|  |  | Phạm vi đo | Cấp chính xác hoặc độ chính xác hoặc sai số hoặc độ không đảm bảo đo |
| 1 | Áp kế chuẩn | Phù hợp với áp kế cần kiểm định (sau đây viết tắt là AKKĐ) | ĐKĐBĐ < 1/4 sai số cho phép của AKKĐ |
| 2 | Ẩm kế | (0 ÷ 100) %RH | ± 5 %RH |"""


def test_long_label_shortened_with_one_legend():
    out = linearize_tables(LONG)
    legend = 'Cột "Cấp chính xác" = "Cấp chính xác hoặc độ chính xác hoặc sai số hoặc độ không đảm bảo đo"'
    assert out.count("hoặc độ chính xác") == 1 and legend in out
    assert "- 2. Ẩm kế: Phạm vi đo = (0 ÷ 100) %RH; Cấp chính xác = ± 5 %RH" in out


def test_abbreviation_cell_quoted():
    out = linearize_tables(LONG)
    assert "Phạm vi đo = «Phù hợp với áp kế cần kiểm định (sau đây viết tắt là AKKĐ)»" in out
