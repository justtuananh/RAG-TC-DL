"""Chạy guard độ trung thực công thức trong tầng unit/CI — scripts.check_fidelity.

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
