"""Chỉ dẫn trả lời từng tài liệu cho câu hỏi không chỉ định một QTKĐ."""

from __future__ import annotations


from api.schemas import ChatRequest
from api.services import chat_stream
from query.multi_document import group_documents, per_document_guidance


def test_group_documents_keeps_order_and_refs():
    docs = group_documents(["A", "B", "A"], {"A": "Áp kế", "B": ""})

    assert [d.label for d in docs] == ["A (Áp kế)", "B"]
    assert [d.refs for d in docs] == [(1, 3), (2,)]


def test_guidance_has_one_line_per_document():
    text = per_document_guidance(group_documents(["A", "B", "A"]))

    assert text is not None
    assert text.count("\n- **") == 2
    assert "[1][3]" in text and "[2]" in text
    assert "KHÔNG chọn một giá trị" in text


def test_single_document_gives_no_guidance():
    assert per_document_guidance(group_documents(["A", "A"])) is None


def _hit(stem):
    return {
        "payload": {"file_stem": stem, "section_path": "3", "kind": "paragraph", "text": "x"},
        "rerank_score": 0.9,
    }


def test_chat_stream_generic_question_adds_guidance(monkeypatch):
    monkeypatch.setattr("retrieval.router.route_files", lambda q: frozenset())
    monkeypatch.setattr("retrieval.doc_titles.title_for", lambda s: "")
    guidance = chat_stream._multi_document_guidance("hỏi chung", [_hit("A"), _hit("B")])
    assert guidance and "**A**" in guidance and "**B**" in guidance


def test_chat_stream_single_named_document_no_guidance(monkeypatch):
    monkeypatch.setattr("retrieval.router.route_files", lambda q: frozenset({"A"}))
    monkeypatch.setattr("retrieval.doc_titles.title_for", lambda s: "")
    assert chat_stream._multi_document_guidance("q", [_hit("A"), _hit("B")]) is None


def test_chat_stream_comparison_lists_only_named_documents(monkeypatch):
    monkeypatch.setattr("retrieval.router.route_files", lambda q: frozenset({"A", "C"}))
    monkeypatch.setattr("retrieval.doc_titles.title_for", lambda s: "")
    guidance = chat_stream._multi_document_guidance("q", [_hit("A"), _hit("B"), _hit("C")])
    assert guidance and "**A**" in guidance and "**C**" in guidance and "**B**" not in guidance
    assert "[3]" in guidance


def test_chat_stream_passes_guidance_to_llm(monkeypatch):
    seen = {}
    monkeypatch.setattr("retrieval.retriever.retrieve", lambda *a, **k: [_hit("A"), _hit("B")])
    monkeypatch.setattr("retrieval.router.route_files", lambda q: frozenset())
    monkeypatch.setattr("retrieval.doc_titles.title_for", lambda s: "")

    def fake_stream(messages):
        seen["last"] = messages[-1]["content"]
        return iter(["ok [1]"])

    monkeypatch.setattr("llm.generator.stream_ollama", fake_stream)
    list(chat_stream.chat_stream_events(ChatRequest(message="Giá trị nào?"), None))
    assert "**A**" in seen["last"]
