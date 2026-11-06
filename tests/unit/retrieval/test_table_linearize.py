"""retrieval.table_linearize - bảng hai tầng tiêu đề -> dòng văn bản."""

from retrieval.table_linearize import linearize_tables, prune_long_tables

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


VALUE_TABLE = """| Giới hạn đo, / MPa | Cấp chính xác hoặc độ chính xác (%) của AKKĐ |  |  |
| --- | --- | --- | --- |
|  | 0,01 | 0,02 | 0,05 |
| Từ -0,1 đến 6 | 4 | 3 | 2 |
| Lớn hơn 6 | 6 | 5 | 3 |"""


def test_value_table_becomes_row_lines():
    out = linearize_tables(VALUE_TABLE)
    assert "- Giới hạn đo, / MPa = Từ -0,1 đến 6: Cấp chính xác 0,01 = 4; Cấp chính xác 0,02 = 3" in out
    assert "- Giới hạn đo, / MPa = Lớn hơn 6: Cấp chính xác 0,01 = 6" in out
    assert "| --- |" not in out


def test_value_table_can_be_disabled():
    assert linearize_tables(VALUE_TABLE, value_tables=False) == VALUE_TABLE


def test_value_table_with_empty_cell_unchanged():
    t = VALUE_TABLE.replace("| 6 | 5 | 3 |", "| 6 |  | 3 |")
    assert linearize_tables(t) == t


def _long_table(n: int) -> str:
    head = "| TT | Tên | Giá trị |\n| --- | --- | --- |"
    rows = [f"| {i} | Mục thứ {i} loại{i} | {i * 10} |" for i in range(1, n + 1)]
    return head + "\n" + "\n".join(rows)


def test_prune_long_table_keeps_header_and_matching_rows():
    out = prune_long_tables("Bảng:\n" + _long_table(20), "cho biết loại7 là gì", 12)
    assert "| TT | Tên | Giá trị |" in out and "| --- |" in out
    assert "| 7 | Mục thứ 7 loại7 | 70 |" in out
    assert "| 8 |" not in out
    assert "giữ 1/20 dòng" in out and out.startswith("Bảng:")


def test_prune_short_table_or_no_match_unchanged():
    short = _long_table(5)
    assert prune_long_tables(short, "loại3", 12) == short
    long = _long_table(20)
    assert prune_long_tables(long, "không liên quan gì", 12) == long
    assert prune_long_tables(long, "loại3", 0) == long
    assert prune_long_tables(long, "", 12) == long


def test_prune_ignores_words_present_in_most_rows():
    long = _long_table(20)  # "mục" và "thứ" có ở mọi dòng: không đủ để chọn dòng
    assert prune_long_tables(long, "mục thứ", 12) == long
