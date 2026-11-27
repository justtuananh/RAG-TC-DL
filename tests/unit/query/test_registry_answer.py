"""Kế hoạch trả lời theo sổ đăng ký danh mục 877 - query.registry_answer."""

import pytest

from knowledge.catalog_codes import CatalogCode
from knowledge.registry import ProcedureEntry
from query import registry_answer
from retrieval.registry_match import RegistryMatch


def _procedure(number: str) -> ProcedureEntry:
    return ProcedureEntry(
        id=1,
        source_file="DANH MỤC QUY TRÌNH.docx",
        row=1,
        code_raw=f"QTKĐ {number} : 2021",
        code=CatalogCode(raw=f"QTKĐ {number} : 2021", prefix="QTKĐ", number=number, year=2021),
        title="Áp kế pít tông",
        issuer="",
        field="",
        kind="kiem_dinh",
    )


@pytest.fixture
def match_by_name(monkeypatch):
    """Danh mục khớp một quy trình theo tên (explicit=False), như khi câu hỏi không viết tiền tố QTKĐ."""
    entry = _procedure("1.159")
    monkeypatch.setattr(
        registry_answer.registry_match,
        "match",
        lambda question: RegistryMatch(procedures=(entry,), coverage=1.0, explicit=False),
    )
    monkeypatch.setattr(registry_answer, "_quantity_filter", lambda q, e, strict: (list(e), [], ""))
    monkeypatch.setattr(registry_answer, "_kind_filter", lambda q, e: (list(e), ""))


def test_section_name_in_document_named_by_number_is_not_a_catalog_listing(match_by_name):
    # Arrange: "những phương tiện kiểm định nào" là tên mục 4 của QTKĐ 1.159, không phải câu liệt kê danh mục
    question = "Quy trình kiểm định áp kế pít tông 1.159 yêu cầu những phương tiện kiểm định nào?"

    # Act
    resolved = registry_answer._resolve(question)

    # Assert
    assert resolved is not None
    assert resolved.deep
    assert "list" not in resolved.general
    assert "count" not in resolved.general


def test_document_named_by_number_keeps_range_part(match_by_name):
    resolved = registry_answer._resolve(
        "Áp kế pít tông 1.159 có dải đo bao nhiêu và cách kiểm tra độ kín ra sao?"
    )

    assert resolved is not None
    assert "range" in resolved.general
    assert "count" not in resolved.general


def test_listing_question_without_document_number_keeps_listing(match_by_name):
    resolved = registry_answer._resolve(
        "Liệt kê những phương tiện kiểm định áp kế pít tông và cách kiểm tra độ kín"
    )

    assert resolved is not None
    assert "list" in resolved.general


def test_number_is_matched_as_whole_token(match_by_name):
    assert (
        registry_answer._names_procedure_number("QTKĐ 1.1590 yêu cầu gì", [_procedure("1.159")])
        is False
    )
    assert (
        registry_answer._names_procedure_number("QTKĐ 1.159 yêu cầu gì", [_procedure("1.159")])
        is True
    )
