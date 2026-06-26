"""Regression cho latex.fix_latex (tách từ app.py + api_server.py về 1 nguồn).

Giữ nguyên hành vi chuẩn hoá LaTeX để KaTeX render: bỏ backtick, đổi \\[..\\]/\\(..\\),
gộp \\\\ → \\. Khớp với frontend liveApi.fixLatex.
"""

from latex import fix_latex


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
