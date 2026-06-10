"""Chấm câu trả lời — eval.scoring (thuần, KHÔNG service).

Khoá ngữ nghĩa chuẩn hoá tiếng Việt/đo lường + coverage/citation/refusal/ảo giác.
"""

import pytest

from eval.scoring import (
    citation_correctness,
    fact_coverage,
    fact_present,
    hallucination_flags,
    is_refusal,
    normalize_latex,
    normalize_number,
    normalize_text,
    score_question,
)

# ── normalize ─────────────────────────────────────────────────────────────────


def test_normalize_number_tolerates_sign_space_percent():
    assert normalize_number("± 3 %") == "3%"
    assert normalize_number("3%") == "3%"
    assert normalize_number("3 %") == "3%"


def test_normalize_number_thousands_and_decimal_comma():
    assert normalize_number("1 400 bar") == "1400bar"
    assert normalize_number("0,15 bar") == "0.15bar"


def test_normalize_text_unit_gluing_and_lower():
    assert normalize_text("40 BAR") == "40bar"
    assert "12tháng" in normalize_text("Chu kỳ 12 tháng")


def test_normalize_latex_space_and_brace_invariant():
    a = r"$\Delta P_{cd}=P_m-P_{cd}$"
    b = r"$\DeltaP_{cd} = P_{m} - P_{cd}$"
    assert normalize_latex(a) == normalize_latex(b)


# ── fact_present / coverage ───────────────────────────────────────────────────


def test_fact_present_number_alias():
    f = {"type": "number", "text": "3 %", "aliases": ["± 3 %"]}
    assert fact_present(f, "Sai số cho phép bằng ± 3% áp suất chỉnh đặt.")
    assert not fact_present(f, "Không có số liệu nào ở đây.")


def test_fact_present_formula_verbatim():
    f = {"type": "formula", "text": r"$\DeltaP_{cd} = P_{m} - P_{cd}$"}
    assert fact_present(f, r"Công thức: $\Delta P_{cd} = P_m - P_{cd}$ với các đại lượng…")


def test_fact_present_term():
    f = {"type": "term", "text": "kẹp chì"}
    assert fact_present(f, "Van phải còn nguyên KẸP CHÌ hoặc dấu niêm phong.")


def test_fact_coverage_fraction_and_empty():
    facts = [
        {"type": "number", "text": "3 %"},
        {"type": "number", "text": "0,15 bar"},
        {"type": "term", "text": "không xuất hiện đâu cả"},
    ]
    cov, flags = fact_coverage(facts, "Bằng ± 3 % nhưng không nhỏ hơn 0,15 bar.")
    assert flags == [True, True, False]
    assert cov == pytest.approx(2 / 3)
    assert fact_coverage([], "bất kỳ") == (1.0, [])


# ── refusal ───────────────────────────────────────────────────────────────────


def test_is_refusal():
    assert is_refusal("Không tìm thấy thông tin này trong các tài liệu QTKĐ được cung cấp.")
    assert not is_refusal("Sai số cho phép là ± 3 %.")


# ── citation correctness ──────────────────────────────────────────────────────


def _hit(file_stem, section_path, parent_text):
    return {
        "payload": {"file_stem": file_stem, "section_path": section_path, "text": parent_text},
        "parent_payload": {"text": parent_text},
    }


def test_citation_grounded_strict_when_cited():
    retrieved = [_hit("F", "6 Tiến hành > 6.3 Đo", "Sai số cho phép bằng ± 3 % áp suất.")]
    fact = {
        "type": "number",
        "text": "3 %",
        "source": {"file_stem": "F", "section_path": "6 Tiến hành > 6.3 Đo"},
    }
    res = citation_correctness([fact], "Sai số là ± 3 % [1].", retrieved)
    assert res["accuracy_lenient"] == 1.0
    assert res["accuracy_strict"] == 1.0


def test_citation_lenient_but_not_strict_without_marker():
    retrieved = [_hit("F", "6 Tiến hành > 6.3 Đo", "Sai số cho phép bằng ± 3 % áp suất.")]
    fact = {
        "type": "number",
        "text": "3 %",
        "source": {"file_stem": "F", "section_path": "6 Tiến hành > 6.3 Đo"},
    }
    res = citation_correctness([fact], "Sai số là ± 3 %.", retrieved)  # không dẫn [n]
    assert res["accuracy_lenient"] == 1.0
    assert res["accuracy_strict"] == 0.0


def test_citation_ungrounded_when_source_not_retrieved():
    retrieved = [_hit("OTHER", "1 Khác", "Nội dung không liên quan.")]
    fact = {
        "type": "number",
        "text": "3 %",
        "source": {"file_stem": "F", "section_path": "6 Tiến hành > 6.3 Đo"},
    }
    res = citation_correctness([fact], "Sai số là ± 3 % [1].", retrieved)
    assert res["grounded_lenient"] == 0
    assert res["ungrounded"]


# ── hallucination ─────────────────────────────────────────────────────────────


def test_hallucination_flags_unsupported_number():
    retrieved = [_hit("F", "6 > 6.3", "Áp suất thử là 40 bar trong 2 phút.")]
    h = hallucination_flags([], "Áp suất thử là 50 bar.", retrieved)
    assert h["count"] == 1
    assert any("50 bar" in t.replace(" ", " ") for t in h["flagged"])


def test_hallucination_clean_when_supported():
    retrieved = [_hit("F", "6 > 6.3", "Áp suất thử là 40 bar trong 2 phút.")]
    h = hallucination_flags([], "Áp suất thử là 40 bar [1].", retrieved)
    assert h["count"] == 0


# ── score_question gộp ────────────────────────────────────────────────────────


def test_score_question_out_of_scope_refusal():
    item = {"id": 1, "category": "out_of_scope", "must_refuse": True, "required_facts": []}
    rec = score_question(
        item, "Không tìm thấy thông tin này trong các tài liệu QTKĐ được cung cấp.", []
    )
    assert rec["refusal_correct"] is True
    assert rec["coverage"] is None
    assert rec["hallucination"]["count"] == 0


def test_score_question_lookup_full_coverage():
    retrieved = [_hit("F", "6 > 6.3", "Sai số cho phép bằng ± 3 % áp suất chỉnh đặt.")]
    item = {
        "id": 2,
        "category": "lookup",
        "required_facts": [
            {
                "type": "number",
                "text": "3 %",
                "source": {"file_stem": "F", "section_path": "6 > 6.3"},
            }
        ],
    }
    rec = score_question(item, "Sai số cho phép là ± 3 % [1].", retrieved)
    assert rec["coverage"] == 1.0
    assert rec["citation"]["accuracy_strict"] == 1.0
    assert rec["refusal_correct"] is True  # không cần từ chối, và không từ chối


# ── Sửa thước đo 2026-06-11 (gold-self-test từng phạt chính gold) ──────────────


def test_normalize_degree_c_equals_oc():
    # Corpus ghi "oC" (chữ o thượng tiêu bị phẳng); model hay viết "°C".
    assert normalize_number("2 °C") == normalize_number("2 oC")


def test_normalize_min_equals_phut():
    assert normalize_number("2 min") == normalize_number("2 phút")
    # r/min hai phía chuẩn hoá giống nhau → substring vẫn khớp
    assert normalize_number("30 r/min") == normalize_number("30 r/min")


def test_hallucination_table_cell_grounding():
    # Số nằm riêng trong Ô BẢNG, đơn vị ở tiêu đề cột → không được cờ.
    retrieved = [
        {
            "payload": {
                "file_stem": "f",
                "section_path": "s",
                "text": "| DN | Thời gian, min |\n| --- | --- |\n| ≤ 50 | 2 |",
            }
        }
    ]
    h = hallucination_flags([], "Thời gian thử tối thiểu là 2 phút [1].", retrieved)
    assert h["count"] == 0
    # Số KHÔNG có trong bảng lẫn văn xuôi → vẫn cờ (giữ precision).
    h2 = hallucination_flags([], "Thời gian thử là 7 phút [1].", retrieved)
    assert h2["count"] == 1
