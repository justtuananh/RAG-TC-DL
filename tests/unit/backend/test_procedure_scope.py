"""``procedure_params`` chỉ trả lời bằng dữ kiện đã duyệt khi câu hỏi hỏi đúng loại dữ kiện.

Bộ test ``test_chatbot`` (2026-10-01): model phân loại đưa mọi câu hỏi có số QTKĐ vào
``procedure_params``; 14/18 câu hỏi quy định nhận bảng mọi dữ kiện của QTKĐ (không có câu
trả lời) thay vì đáp án nguyên văn của văn bản QTKĐ.
"""

from __future__ import annotations

import pytest

from query.procedure_scope import (
    asked_kinds,
    fact_clause,
    facts_answer,
    scope_procedure_params,
    select_facts,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "question",
    [
        "Độ chênh áp tối đa của van an toàn theo QTKĐ 1.061 là bao nhiêu phần trăm áp suất chỉnh đặt?",
        "Độ tụt áp cho phép sau 5 phút khi kiểm định bàn tạo áp theo QTKĐ 1.062 là bao nhiêu?",
        "Công thức xác định dung tích làm việc của bình phân ly theo QTKĐ 1.063 là gì?",
        "Thời gian quay tự do tối thiểu của pít tông H3000 theo QTKĐ 1.071 là bao nhiêu?",
        "Tốc độ hạ của pít tông H3000 không được vượt quá bao nhiêu theo QTKĐ 1.071?",
        "Độ tăng/giảm áp cho phép sau 5 phút khi kiểm định DPI 610 theo QTKĐ 1.190 là bao nhiêu?",
        # Điều kiện kiểm định chung: QTKĐ còn nêu điều kiện ngoài nhiệt độ / độ ẩm.
        "Điều kiện kiểm định của QTKĐ 1.159 là gì?",
        "QTKĐ 1.061 áp dụng cho thiết bị nào?",
        # Không hỏi giá trị sai số cho phép / điều kiện môi trường khi kiểm định.
        "Nguyên nhân gây sai số khi đo áp suất theo QTKĐ 1.159 là gì?",
        "Nhiệt độ làm việc tối đa của van an toàn theo QTKĐ 1.061 là bao nhiêu?",
        "Nhiệt độ bảo quản áp kế theo QTKĐ 1.159 là bao nhiêu?",
    ],
)
def test_regulation_questions_without_a_fact_kind_go_to_text(question):
    assert asked_kinds(question) is None
    payload = {"branch": "data", "intent": "procedure_params", "params": {"procedure_number": "1"}}
    assert scope_procedure_params(payload, question) == {"branch": "text", "confidence": 1.0}


@pytest.mark.parametrize(
    ("question", "kinds", "labels"),
    [
        (
            "Chu kỳ kiểm định của áp kế pít tông theo QTKĐ 1.159 là bao lâu?",
            ["calibration_interval"],
            [],
        ),
        (
            "Áp kế pít tông kiểu H3000-SP-70/700 theo QTKĐ 1.071 có phạm vi đo và cấp chính xác là bao nhiêu?",
            ["working_range", "accuracy_class"],
            [],
        ),
        (
            "Giới hạn đo của thiết bị kiểu DPI 610 theo QTKĐ 1.190 là bao nhiêu?",
            ["working_range"],
            [],
        ),
        (
            "Sai số cho phép của áp suất chỉnh đặt van an toàn trong QTKĐ 1.061?",
            ["max_permissible_error"],
            [],
        ),
        (
            "Điều kiện nhiệt độ và độ ẩm khi kiểm định bàn tạo áp theo QTKĐ 1.062 là bao nhiêu?",
            ["env_condition"],
            ["nhiet do", "do am"],
        ),
        ("Thông số tham chiếu của QTKĐ 1.061?", [], []),
    ],
)
def test_fact_questions_name_the_asked_kinds(question, kinds, labels):
    assert asked_kinds(question) == (kinds, labels)


def test_scope_adds_the_asked_kinds_and_keeps_generic_questions():
    payload = {
        "branch": "data",
        "intent": "procedure_params",
        "params": {"procedure_number": "1.159"},
    }
    scoped = scope_procedure_params(payload, "Chu kỳ kiểm định theo QTKĐ 1.159?")
    assert scoped["params"] == {
        "procedure_number": "1.159",
        "asked_kinds": ["calibration_interval"],
        "asked_labels": [],
    }
    assert scope_procedure_params(payload, "Thông số của QTKĐ 1.159?") == payload
    other = {"branch": "data", "intent": "record_lookup", "params": {"serial": "1045"}}
    assert scope_procedure_params(other, "Độ chênh áp tối đa") == other


def _fact(kind, label, value, condition=None):
    return {"fact_kind": kind, "label": label, "value_text": value, "condition_text": condition}


def test_select_facts_needs_every_asked_part():
    facts = [
        _fact(
            "env_condition",
            "Nhiệt độ môi trường",
            "(23 ± 5) oC",
            "nhiệt độ không được thay đổi quá 2 oC/h",
        ),
        _fact("calibration_interval", "Chu kỳ kiểm định", "02 năm"),
    ]
    assert select_facts(facts, ["calibration_interval"], []) == [facts[1]]
    assert select_facts(facts, ["env_condition"], ["nhiet do"]) == [facts[0]]
    # Hỏi cả độ ẩm mà không có dữ kiện độ ẩm: không trả lời thiếu.
    assert select_facts(facts, ["env_condition"], ["nhiet do", "do am"]) is None
    assert select_facts(facts, ["working_range", "calibration_interval"], []) is None


def test_select_facts_refuses_same_label_values_without_conditions():
    """Ba "Phạm vi đo" của QTKĐ 1.159 (khí tuyệt đối, khí tương đối, chất lỏng) không ghi
    điều kiện: kể ba khoảng trần trụi là mất ngữ cảnh, văn bản QTKĐ trả lời đúng hơn."""
    facts = [
        _fact("working_range", "Phạm vi đo", "(0,001 5 đến 7) MPa"),
        _fact("working_range", "Phạm vi đo", "(-0,1 đến 100) MPa"),
    ]
    assert select_facts(facts, ["working_range"], []) is None
    with_conditions = [
        _fact("working_range", "Phạm vi đo", "(0,001 5 đến 7) MPa", "khí, áp suất tuyệt đối"),
        _fact("working_range", "Phạm vi đo", "(-0,1 đến 100) MPa", "khí, áp suất tương đối"),
    ]
    assert select_facts(with_conditions, ["working_range"], []) == with_conditions


def test_facts_answer_keeps_values_and_conditions_verbatim():
    clauses = [
        fact_clause(
            _fact(
                "env_condition",
                "Nhiệt độ môi trường",
                "(23 ± 5) oC;",
                "nhiệt độ không được thay đổi quá 2 oC/h",
            ),
            "Điều kiện môi trường",
        ),
        fact_clause(
            _fact("calibration_interval", "Chu kỳ kiểm định", "02 năm"), "Chu kỳ kiểm định"
        ),
    ]
    assert facts_answer("1.159", clauses, asked=True) == (
        "Theo QTKĐ 1.159: nhiệt độ môi trường (23 ± 5) oC, nhiệt độ không được thay đổi quá "
        "2 oC/h; chu kỳ kiểm định 02 năm."
    )
    assert facts_answer("1.159", clauses[1:], asked=False) == (
        "QTKĐ 1.159 có 1 dữ kiện đã duyệt:\n\n- chu kỳ kiểm định 02 năm"
    )
