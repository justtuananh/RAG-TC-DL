"""Câu hỏi nêu loại thiết bị chung chung (khớp nhiều QTKĐ) không được trả lời như một loại.

Lỗi gốc: "Áp kế pít tông có phạm vi đo và cấp chính xác là bao nhiêu?" khớp cả QTKĐ
1.071 (kiểu H3000) lẫn 1.159 (tiêu chuẩn), nhưng chatbot chọn một loại rồi trả lời
như thể đó là câu trả lời chung.
"""

from __future__ import annotations

import pytest

from knowledge.seed_data import DEVICE_TYPES, KNOWN_PROCEDURE_DEVICE_TYPES
from query.device_ambiguity import (
    DeviceProcedure,
    ambiguity_preface,
    find_device_ambiguity,
    load_device_procedures,
    scoped_retrieval_query,
)


def _catalog() -> list[DeviceProcedure]:
    aliases = {row["name_vi"]: tuple(row["aliases"]) for row in DEVICE_TYPES}
    return [
        DeviceProcedure(device_type=name, number=number, aliases=aliases.get(name, ()))
        for number, name in KNOWN_PROCEDURE_DEVICE_TYPES.items()
    ]


@pytest.mark.parametrize(
    "question",
    [
        "Áp kế pít tông có phạm vi đo và cấp chính xác là bao nhiêu?",
        "áp kế píttông dùng chuẩn nào",
        "Phạm vi đo của áp kế pittông?",
    ],
)
def test_generic_piston_gauge_question_is_ambiguous(question):
    ambiguity = find_device_ambiguity(question, _catalog())

    assert ambiguity is not None
    assert ambiguity.phrase == "áp kế píttông"
    assert [option.number for option in ambiguity.options] == ["1.071", "1.159"]


@pytest.mark.parametrize(
    "question",
    [
        # đã nêu rõ loại qua tên đầy đủ hoặc alias
        "Áp kế píttông kiểu H3000 có phạm vi đo bao nhiêu?",
        "Phạm vi đo của H3000?",
        "Áp kế pít tông tiêu chuẩn có cấp chính xác bao nhiêu?",
        # đã nêu số QTKĐ
        "Áp kế pít tông theo QTKĐ 1.159 có phạm vi đo bao nhiêu?",
        # loại thiết bị chỉ có một QTKĐ
        "Van an toàn có phạm vi đo bao nhiêu?",
        # không nhắc thiết bị nào
        "Sai số cho phép là bao nhiêu?",
        # chỉ trùng từ chung "thiết bị" - không đủ để coi là cùng một họ thiết bị
        "Thiết bị chuẩn cần những gì?",
    ],
)
def test_specific_or_unrelated_question_is_not_ambiguous(question):
    assert find_device_ambiguity(question, _catalog()) is None


def test_empty_catalog_is_never_ambiguous():
    assert find_device_ambiguity("Áp kế pít tông có phạm vi đo bao nhiêu?", []) is None


def test_preface_lists_every_type_with_its_procedure():
    ambiguity = find_device_ambiguity("Áp kế pít tông có phạm vi đo bao nhiêu?", _catalog())

    preface = ambiguity_preface(ambiguity)

    assert "chưa nêu rõ loại" in preface
    assert "Áp kế píttông kiểu H3000 (QTKĐ 1.071)" in preface
    assert "Áp kế píttông tiêu chuẩn (QTKĐ 1.159)" in preface
    assert "—" not in preface


def test_scoped_retrieval_query_names_every_candidate_procedure():
    ambiguity = find_device_ambiguity("Áp kế pít tông có phạm vi đo bao nhiêu?", _catalog())

    query = scoped_retrieval_query("Áp kế pít tông có phạm vi đo bao nhiêu?", ambiguity)

    assert query.startswith("Áp kế pít tông có phạm vi đo bao nhiêu?")
    assert "1.071" in query and "1.159" in query


def test_load_device_procedures_reads_procedures_with_their_aliases(data_db):
    session, _ = data_db

    catalog = load_device_procedures(session)

    assert [(item.device_type, item.number) for item in catalog] == [("Van an toàn", "1.061")]
