"""Kiểm số liệu: số trong câu trả lời phải có trong nguồn."""

from llm.number_check import unsupported

CTX = "Độ ẩm tương đối: (65 ± 15) %;\nNhiệt độ môi trường: (20 ± 5) oC;\nPhạm vi làm việc đến 1 400 bar.\nSai số ± 3% nhưng không nhỏ hơn ± 0,15 bar."


def test_exact_numbers_pass():
    ans = "Độ ẩm là (65 ± 15) % [1], nhiệt độ (20 ± 5) oC, phạm vi 1 400 bar, tối thiểu 0,15 bar."
    assert unsupported(ans, CTX) == []


def test_tolerance_changed_is_flagged():
    assert unsupported("Độ ẩm là (65 ± 10) % [1].", CTX) == ["65 ± 10"]


def test_number_with_unit_not_in_context_is_flagged():
    assert unsupported("Chu kỳ là 18 tháng.", CTX) == ["18 tháng"]


def test_section_numbers_and_codes_are_ignored():
    assert unsupported("Theo QTKĐ 1.061 mục 6.3.2 [1] và điều 5.1.", CTX) == []


def test_thousands_group_and_decimal_comma_equivalent():
    assert unsupported("Đến 1400 bar và 0.15 bar.", CTX) == []


def test_latex_pm_is_understood():
    assert unsupported("Sai số $\\pm 3\\%$ và $(65 \\pm 15)\\%$", CTX) == []
    assert unsupported("Độ ẩm $(65 \\pm 12)\\%$", CTX) == ["65 \\pm 12".replace("\\pm", "±")]


def test_dedup_and_citation_markers():
    assert unsupported("7 bar [7]. Lại 7 bar [1].", CTX) == ["7 bar"]
