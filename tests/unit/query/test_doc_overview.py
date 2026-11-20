"""Trả lời "để làm gì / nói về gì / gồm những mục nào" từ hồ sơ tài liệu - query.doc_overview."""

import pytest

from query import doc_overview
from retrieval.doc_profile import DocCode, DocProfile, Section

PROFILE = DocProfile(
    file_stem="QTKD_1.061_2021_ND_V2_2",
    code=DocCode("QTKĐ", "1.061", 2021),
    title="VAN AN TOÀN CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar",
    scope_heading="1 Phạm vi áp dụng",
    scope_text="Quy trình kỹ thuật này quy định quy trình kiểm định van an toàn.",
    sections=(
        Section("1", "Phạm vi áp dụng", 1),
        Section("6", "Tiến hành kiểm định", 1),
        Section("6.1", "Kiểm tra bên ngoài", 2),
    ),
    keywords=(),
)


@pytest.mark.parametrize(
    "question,intent",
    [
        ("QTKĐ 1.061:2021 dùng để làm gì?", doc_overview.PURPOSE),
        ("QTKĐ 1.160 kiểm định loại áp kế nào, cấp chính xác đến bao nhiêu?", doc_overview.PURPOSE),
        ("QTKĐ 1.085:2017 áp dụng cho những dụng cụ đo dung tích thủy tinh nào?", doc_overview.PURPOSE),
        ("File QTKĐ 1.106_2018 nói về nội dung gì?", doc_overview.OVERVIEW),
        ("TCVN 6165:1996 là tài liệu gì?", doc_overview.OVERVIEW),
        ("QTKĐ 1.062 là quy trình kiểm định gì?", doc_overview.OVERVIEW),
        ("Mục lục QTKĐ 1.213:2025 gồm những phần nào?", doc_overview.TOC),
        ("QTKĐ 1.037_2021 gồm những mục nào?", doc_overview.TOC),
        ("Chu kỳ kiểm định của van an toàn là bao lâu?", None),
        ("Điều kiện kiểm định bàn tạo áp theo QTKĐ 1.062:2021 là gì?", None),
        ("Ai là chủ nhiệm biên soạn đề cương QTKĐ 1.072:2022?", None),
        ("Công thức tính E_FD dùng để làm gì?", None),
    ],
)
def test_classify_intent(question, intent):
    assert doc_overview.classify_intent(question) == intent


@pytest.fixture
def one_document(monkeypatch):
    monkeypatch.setattr(doc_overview.router, "route_files", lambda q: frozenset({PROFILE.file_stem}))
    monkeypatch.setattr(doc_overview.doc_profile, "profile_for", lambda stem: PROFILE)
    monkeypatch.setattr(doc_overview.doc_summary, "approved_text", lambda stem: None)


APPROVED = "- **Đối tượng và phạm vi:** van an toàn đến 1 400 bar."


@pytest.fixture
def approved_summary(one_document, monkeypatch):
    monkeypatch.setattr(doc_overview.doc_summary, "approved_text", {PROFILE.file_stem: APPROVED}.get)


def test_overview_uses_the_approved_summary(approved_summary):
    answer = doc_overview.try_document_answer("Tóm tắt QTKĐ 1.061")
    assert "Tóm tắt đã được người duyệt phê duyệt [1]:" in answer.text and APPROVED in answer.text
    assert answer.hits[0]["payload"]["section_path"] == doc_overview.SUMMARY_SECTION
    assert answer.hits[0]["payload"]["text"] == APPROVED


def test_purpose_question_still_quotes_the_scope_verbatim(approved_summary):
    answer = doc_overview.try_document_answer("QTKĐ 1.061 dùng để làm gì?")
    assert APPROVED not in answer.text and "Theo mục 1 Phạm vi áp dụng [1]:" in answer.text


def test_summary_can_be_kept_out_of_chat(approved_summary, settings_override):
    settings_override({"doc_summary.use_in_chat": False})
    answer = doc_overview.try_document_answer("Tóm tắt QTKĐ 1.061")
    assert APPROVED not in answer.text and "Theo mục 1 Phạm vi áp dụng [1]:" in answer.text


def test_purpose_answer_quotes_scope_verbatim_with_citation(one_document):
    answer = doc_overview.try_document_answer("QTKĐ 1.061 dùng để làm gì?")
    assert answer.text.startswith("**QTKĐ 1.061:2021 - VAN AN TOÀN")
    assert "Theo mục 1 Phạm vi áp dụng [1]:" in answer.text
    assert "> Quy trình kỹ thuật này quy định quy trình kiểm định van an toàn." in answer.text
    payload = answer.hits[0]["payload"]
    assert payload["file_stem"] == PROFILE.file_stem and payload["text"] == PROFILE.scope_text


def test_overview_adds_main_sections(one_document):
    answer = doc_overview.try_document_answer("QTKĐ 1.061 nói về nội dung gì?")
    assert "Tài liệu gồm các mục chính: 1 Phạm vi áp dụng; 6 Tiến hành kiểm định." in answer.text


def test_toc_lists_sections_with_indentation(one_document):
    answer = doc_overview.try_document_answer("Mục lục QTKĐ 1.061 gồm những phần nào?")
    assert "- 1 Phạm vi áp dụng\n- 6 Tiến hành kiểm định\n  - 6.1 Kiểm tra bên ngoài" in answer.text
    assert answer.hits[0]["payload"]["section_path"] == "Mục lục"


def test_two_documents_sharing_a_number_are_answered_separately(monkeypatch):
    other = DocProfile(
        "cot",
        DocCode("QTKĐ", "1.062", 2016),
        "Cột đo xăng dầu",
        "1 Phạm vi áp dụng",
        "Quy trình này dùng để kiểm định cột đo xăng dầu.",
        (),
        (),
    )
    profiles = {PROFILE.file_stem: PROFILE, "cot": other}
    monkeypatch.setattr(doc_overview.router, "route_files", lambda q: frozenset(profiles))
    monkeypatch.setattr(doc_overview.doc_profile, "profile_for", profiles.get)
    answer = doc_overview.try_document_answer("QTKĐ 1.062 dùng để làm gì?")
    assert answer.text.startswith("Có 2 tài liệu khớp")
    assert "[1]" in answer.text and "[2]" in answer.text and len(answer.hits) == 2


def test_falls_back_to_rag_when_no_document_or_no_scope(monkeypatch):
    monkeypatch.setattr(doc_overview.router, "route_files", lambda q: frozenset())
    assert doc_overview.try_document_answer("QTKĐ 1.999 dùng để làm gì?") is None
    empty = DocProfile("x", None, "", "", "", (), ())
    monkeypatch.setattr(doc_overview.router, "route_files", lambda q: frozenset({"x"}))
    monkeypatch.setattr(doc_overview.doc_profile, "profile_for", lambda stem: empty)
    assert doc_overview.try_document_answer("QTKĐ x dùng để làm gì?") is None


def test_disabled_in_settings_returns_none(one_document, settings_override):
    settings_override({"doc_profile.enabled": False})
    assert doc_overview.try_document_answer("QTKĐ 1.061 dùng để làm gì?") is None
