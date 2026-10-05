"""latex.restore_formulas: công thức trong câu trả lời phải là bản NGUYÊN VĂN của nguồn.

qwen2.5:7b chép công thức nhưng "biến tấu" hình thức (thêm/bỏ \\left \\right, thêm
\\tag{n}, ^{2} thành ^2, × thành \\times). Nguồn là thứ người dùng đối chiếu với ảnh
công thức gốc, nên câu trả lời phải hiện đúng chuỗi LaTeX của nguồn.
"""

from core.latex import restore_formulas

SOURCE_M = r"M = P \times A_{0} \times \frac{g_{0}}{g} \times (1 + \frac{\rho_{a}}{\rho_{Mt}})"
CONTEXT = f"[1] Nguồn: QTKD_1.159 — 6.3.1\n---\n| ${SOURCE_M}$ |  |\n\ntrong đó: P là áp suất chuẩn"


def test_added_left_right_is_restored_to_the_source():
    answer = (
        "Theo [1]:\n\n$$ M = P \\times A_{0} \\times \\frac{g_{0}}{g} \\times "
        "\\left(1 + \\frac{\\rho_{a}}{\\rho_{Mt}}\\right) $$"
    )
    assert restore_formulas(answer, CONTEXT) == f"Theo [1]:\n\n$${SOURCE_M}$$"


def test_dropped_left_right_tag_and_brace_changes_are_restored():
    source = r"b=\frac{\sum{\left( x_{i}-\hat{x} \right)}}{\sum{\left( x_{i}-\hat{x} \right)^{2}}}"
    answer = r"$$ b = \frac{\sum{(x_{i}-\hat{x})}}{\sum{(x_{i}-\hat{x})^2}} \tag{2} $$"
    assert restore_formulas(answer, f"${source}$") == f"$${source}$$"


def test_times_sign_matches_its_latex_command():
    assert restore_formulas(r"$a=\hat{y}-b \times \hat{x}$", r"$a=\hat{y}-b×\hat{x}$") == (
        r"$a=\hat{y}-b×\hat{x}$"
    )


def test_inline_formula_keeps_inline_delimiters():
    source = r"$\tau = \tau_{t}\frac{\eta_{t}}{\eta}$"
    answer = r"Ta có $\tau = \tau_{t} \frac{\eta_{t}}{\eta}$."
    assert restore_formulas(answer, source) == f"Ta có {source}."


def test_formula_absent_from_the_source_is_left_alone():
    answer = "$$Y = a + bX$$"
    assert restore_formulas(answer, CONTEXT) == answer


def test_ambiguous_match_is_left_alone():
    """Hai công thức nguồn cùng khoá: không đoán, giữ nguyên câu trả lời."""
    context = r"$x^{2}=a$ và $x^2=a$"
    answer = r"$$x^{ 2 } = a$$"
    assert restore_formulas(answer, context) == answer


def test_verbatim_answer_and_plain_text_are_unchanged():
    answer = f"Công thức: ${SOURCE_M}$ với giá trị ± 3 %."
    assert restore_formulas(answer, CONTEXT) == answer
    assert restore_formulas("Không có công thức.", CONTEXT) == "Không có công thức."
