"""OMML (công thức Word gốc) → LaTeX: các lỗi đã gặp ở QTKĐ 1.160, 1.190, 1.063."""

from lxml import etree

from ingestion.omml import omml_to_latex

_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _o(inner: str) -> str:
    return omml_to_latex(etree.fromstring(f'<m:oMath xmlns:m="{_M}">{inner}</m:oMath>'))


def _r(text: str) -> str:
    return f"<m:r><m:t>{text}</m:t></m:r>"


def test_brace_delimiter_is_escaped():
    d = (
        '<m:d><m:dPr><m:begChr m:val="{"/><m:endChr m:val="}"/></m:dPr><m:e>'
        + _r("a")
        + "</m:e></m:d>"
    )
    assert _o(d) == r"\left\{ a \right\}"


def test_empty_delimiter_is_a_null_fence():
    d = (
        '<m:d><m:dPr><m:begChr m:val=""/><m:endChr m:val="|"/></m:dPr><m:e>'
        + _r("a")
        + "</m:e></m:d>"
    )
    assert _o(d) == r"\left. a \right|"


def test_only_symbols_katex_cannot_render_are_rewritten():
    """``∆`` (U+2206) không có trong font KaTeX; Greek, × KaTeX render được nên giữ nguyên văn."""
    assert _o(_r("∆P=ρ×g×h")) == r"\Delta P=ρ×g×h"


def test_non_ascii_letter_is_text():
    sub = "<m:sSub><m:e>" + _r("V") + "</m:e><m:sub>" + _r("đ") + "</m:sub></m:sSub>"
    assert _o(sub) == r"V_{\text{đ}}"


def test_named_function_becomes_a_command():
    func = "<m:func><m:fName>" + _r("max") + "</m:fName><m:e>" + _r("x") + "</m:e></m:func>"
    assert _o(func) == r"\max x"
