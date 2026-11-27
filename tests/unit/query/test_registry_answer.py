"""Kế hoạch trả lời theo sổ đăng ký danh mục 877 - query.registry_answer."""

import pytest

from knowledge.registry import ProcedureEntry
from query import registry_answer
from retrieval.registry_match import RegistryMatch


def _procedure() -> ProcedureEntry:
    return ProcedureEntry.__new__(ProcedureEntry)


@pytest.fixture
def explicit_document(monkeypatch):
    """Câu hỏi nêu mã QTKĐ 1.159: danh mục khớp bằng mã, một dòng quy trình."""
    entry = _procedure()
    monkeypatch.setattr(
        registry_answer.registry_match,
        "match",
        lambda question: RegistryMatch(procedures=(entry,), codes=(), coverage=1.0, explicit=True),
    )
    monkeypatch.setattr(
        registry_answer, "_without_listed_procedures", lambda entries: list(entries)
    )
    monkeypatch.setattr(registry_answer, "_quantity_filter", lambda q, e, strict: (list(e), [], ""))
    monkeypatch.setattr(registry_answer, "_kind_filter", lambda q, e: (list(e), ""))
    return entry


def test_section_name_in_named_document_is_not_a_catalog_listing(explicit_document):
    # Arrange: "những phương tiện kiểm định nào" là tên mục 4 của QTKĐ 1.159, không phải câu liệt kê danh mục
    question = "Quy trình kiểm định áp kế pít tông 1.159 yêu cầu những phương tiện kiểm định nào?"

    # Act
    resolved = registry_answer._resolve(question)

    # Assert
    assert resolved is not None
    assert resolved.deep
    assert "list" not in resolved.general
    assert "count" not in resolved.general


def test_named_document_with_range_question_keeps_general_part(explicit_document):
    resolved = registry_answer._resolve(
        "QTKĐ 1.159 có dải đo bao nhiêu và cách kiểm tra độ kín ra sao?"
    )

    assert resolved is not None
    assert "range" in resolved.general
    assert "count" not in resolved.general
