"""retrieval.subsection - định vị mục con đánh số trong section cha."""

from retrieval import subsection

PARENT = (
    "## 6.3 Kiểm tra đo lường\n\nMở đầu.\n\n"
    "6.3.1 Xác định sai số của áp suất chỉnh đặt\n\nTăng áp suất từ từ đến điểm đặt.\n\n"
    "6.3.2 Xác định độ chênh áp\n\nĐộ chênh áp tối đa là 7 % áp suất chỉnh đặt.\n\n"
    "0,5 bar là giá trị nhỏ nhất.\n"
)
PATH = "6 Tiến hành kiểm định > 6.3 Kiểm tra đo lường"


def test_section_number_of_last_component():
    assert subsection.section_number(PATH) == "6.3"
    assert subsection.section_number("Phụ lục A") is None


def test_locates_nearest_preceding_subsection():
    out = subsection.locate(PATH, PARENT, "Độ chênh áp tối đa là 7 % áp suất chỉnh đặt.")
    assert out == PATH + " > 6.3.2 Xác định độ chênh áp"
    out = subsection.locate(PATH, PARENT, "Tăng áp suất từ từ đến điểm đặt.")
    assert out.endswith("> 6.3.1 Xác định sai số của áp suất chỉnh đặt")


def test_anchor_before_first_subsection_keeps_path():
    assert subsection.locate(PATH, PARENT, "Mở đầu.") == PATH


def test_numeric_data_lines_are_not_headings():
    text = "## 5.1 X\n\n5.1 mm là chiều dày\n\n5.1.1 Nhận dạng\n\nnội dung\n"
    # "5.1 mm" trùng số mục cha (không bắt đầu bằng '5.1.') nên không phải mục con
    assert subsection.locate("5 A > 5.1 X", text, "nội dung") == "5 A > 5.1 X > 5.1.1 Nhận dạng"
    assert subsection.locate("5 A > 5.1 X", text, "5.1 mm là chiều dày") == "5 A > 5.1 X"


def test_unknown_anchor_or_no_number_returns_unchanged():
    assert subsection.locate(PATH, PARENT, "không có trong cha") == PATH
    assert subsection.locate("Phụ lục A", PARENT, "Mở đầu.") == "Phụ lục A"
    assert subsection.locate(PATH, "", "x") == PATH
