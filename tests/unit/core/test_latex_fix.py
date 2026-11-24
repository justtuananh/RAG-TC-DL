"""Regression cho latex.fix_latex (gộp về một nguồn dùng chung).

Giữ nguyên hành vi chuẩn hoá LaTeX để KaTeX render: bỏ backtick, đổi \\[..\\]/\\(..\\),
gộp \\\\ → \\. Khớp với frontend liveApi.fixLatex.
"""

from core.latex import fix_latex


def test_giu_nguyen_text_thuong():
    assert fix_latex("Thời gian quay tự do ≥ 3 phút") == "Thời gian quay tự do ≥ 3 phút"


def test_chuoi_rong():
    assert fix_latex("") == ""


def test_bo_backtick_quanh_cong_thuc():
    assert fix_latex("`$x$`") == "$x$"


def test_backslash_inline():
    assert fix_latex(r"\(a+b\)") == "$a+b$"


def test_backslash_display():
    assert fix_latex(r"\[a\]") == "$$a$$"


def test_gop_double_backslash_trong_display():
    assert fix_latex(r"$$\\frac{a}{b}$$") == r"$$\frac{a}{b}$$"


def test_khoi_display_co_trich_dan_sau_dong_dong_gop_mot_dong():
    # qwen2.5 viết "$$ [1]": dấu đóng không đứng riêng một dòng nên khối không đóng,
    # nút trích dẫn rơi vào trong công thức (KaTeX báo lỗi, chữ đỏ).
    formula = r"\tau = \tau_{t} \times \frac{\eta_{t}}{\eta}"
    answer = "- Trong QTKĐ 1.071:\n  $$\n  " + formula + "\n  $$ [1]\n\nTiếp."
    assert fix_latex(answer) == "- Trong QTKĐ 1.071:\n  $$" + formula + "$$ [1]\n\nTiếp."


def test_khoi_display_dong_dung_chuan_giu_nguyen():
    answer = "Công thức:\n\n$$\n" + r"\tau = \tau_{t}" + "\n$$\n\n[1]"
    assert fix_latex(answer) == answer
