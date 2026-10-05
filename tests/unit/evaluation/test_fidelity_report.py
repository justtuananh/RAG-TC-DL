"""Chạy guard độ trung thực công thức trong tầng unit/CI - scripts.check_fidelity.

Khẳng định artifact ĐÃ commit (build/spike_a) đạt mọi bất biến, và kiểm các hàm
con (phát hiện brace lệch, '$' lạ, \\left/\\right không cân).
"""

from scripts.check_fidelity import _brace_problem, _latex_problem, check_fidelity


def test_committed_report_passes_all_invariants(build_dir):
    problems = check_fidelity(build_dir)
    assert problems == [], "Guard fidelity báo lỗi:\n" + "\n".join(problems)


def test_brace_problem_detects_imbalance():
    assert _brace_problem("{a}") is None
    assert _brace_problem("{a") is not None
    assert _brace_problem("a}") is not None
    assert _brace_problem(r"\{a\}") is None  # brace escaped là literal


def test_latex_problem_flags_stray_dollar():
    assert _latex_problem("$x$") is not None
    assert _latex_problem(r"\frac{1}{2}") is None


def test_latex_problem_left_right_balance():
    assert _latex_problem(r"\left( a \right)") is None
    assert _latex_problem(r"\left( a") is not None
    assert _latex_problem(r"\leftarrow x") is None  # không nhầm \leftarrow là \left


def test_latex_problem_flags_command_glued_to_a_letter():
    """`\\DeltaP` là lệnh lạ, KaTeX hiện chữ đỏ (QTKĐ 1.061, 1.159)."""
    assert _latex_problem(r"\DeltaP_{cd} = P_{m} - P_{cd}") is not None
    assert _latex_problem(r"g\Deltah") is not None
    assert _latex_problem(r"\Delta P_{cd} = P_{m} - P_{cd}") is None
    assert _latex_problem(r"\rho_{f} \times \theta_{s}") is None


def test_latex_problem_flags_unescaped_brace_delimiter():
    r"""`\left{` là lỗi cú pháp, ngoặc nhọn phải là `\left\{` (QTKĐ 1.160, 1.190)."""
    assert _latex_problem(r"max\left{ a \right}") is not None
    assert _latex_problem(r"\max\left\{ a \right\}") is None


def test_latex_problem_flags_empty_fraction_part():
    r"""Mẫu / tử số rỗng là dấu hiệu mất nội dung (căn thức bị gem bỏ, QTKĐ 1.159)."""
    assert _latex_problem(r"\frac{U(t)}{}") is not None
    assert _latex_problem(r"\delta = \frac{}{p}") is not None
    assert _latex_problem(r"\frac{\sqrt{(\Delta p)^{2}}}{p}") is None
