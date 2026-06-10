"""MathML → LaTeX (nửa thuần-Python của pipeline công thức — rủi ro #1).

ingestion.mtef_to_latex.mathml_to_latex KHÔNG cần Ruby/Docker. Đây là phần giá trị
cao nhất của ingestion: nếu nó sai, công thức indexed sẽ sai.
"""

from ingestion.mtef_to_latex import mathml_to_latex

_M = "http://www.w3.org/1998/Math/MathML"


def _w(inner: str) -> str:
    return f'<math xmlns="{_M}">{inner}</math>'


def test_fraction():
    assert mathml_to_latex(_w("<mfrac><mn>1</mn><mn>2</mn></mfrac>")) == r"\frac{1}{2}"


def test_superscript_subscript():
    assert mathml_to_latex(_w("<msup><mi>x</mi><mn>2</mn></msup>")) == "x^{2}"
    assert mathml_to_latex(_w("<msub><mi>P</mi><mn>1</mn></msub>")) == "P_{1}"
    assert mathml_to_latex(_w("<msubsup><mi>x</mi><mn>1</mn><mn>2</mn></msubsup>")) == "x_{1}^{2}"


def test_sqrt():
    assert mathml_to_latex(_w("<msqrt><mi>x</mi></msqrt>")) == r"\sqrt{x}"


def test_unicode_mapping():
    assert mathml_to_latex(_w("<mi>α</mi>")) == r"\alpha"
    assert mathml_to_latex(_w("<mo>×</mo>")) == r"\times"
    assert mathml_to_latex(_w("<mo>≤</mo>")) == r"\leq"
    assert mathml_to_latex(_w("<mi>°</mi>")) == r"^{\circ}"


def test_fenced():
    assert mathml_to_latex(_w("<mfenced><mi>a</mi></mfenced>")) == r"\left( a \right)"


def test_matrix_table():
    out = mathml_to_latex(
        _w("<mtable><mtr><mtd><mi>a</mi></mtd><mtd><mi>b</mi></mtd></mtr></mtable>")
    )
    assert out == r"\begin{matrix} a & b \end{matrix}"


def test_malformed_returns_none_without_raising():
    assert mathml_to_latex("<math><mfrac>") is None
    assert mathml_to_latex("") is None
    assert mathml_to_latex("không phải xml") is None
