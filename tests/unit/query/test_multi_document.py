"""Hỏi riêng từng tài liệu cho câu hỏi không chỉ định một QTKĐ (logic thuần + luồng chat)."""

from __future__ import annotations

import json

from api.schemas import ChatRequest
from api.services import chat_stream
from query import multi_document as md


def test_group_by_document_keeps_order_and_positions():
    groups = md.group_by_document(["A", "B", "A"])

    assert [g.stem for g in groups] == ["A", "B"]
    assert [g.positions for g in groups] == [(0, 2), (1,)]


def test_select_single_named_document_is_not_split():
    groups = md.group_by_document(["A", "B"])

    assert md.select_documents(groups, frozenset({"A"})) is None


def test_select_generic_takes_all_up_to_cap():
    groups = md.group_by_document(["A", "B", "C", "D"])

    chosen = md.select_documents(groups, frozenset(), max_documents=3)

    assert [g.stem for g in chosen] == ["A", "B", "C"]


def test_select_comparison_keeps_only_named():
    groups = md.group_by_document(["A", "B", "C"])

    chosen = md.select_documents(groups, frozenset({"A", "C"}))

    assert [g.stem for g in chosen] == ["A", "C"]


def test_select_needs_min_documents():
    assert md.select_documents(md.group_by_document(["A", "A"]), frozenset()) is None


def test_is_empty_answer():
    assert md.is_empty_answer("không nêu")
    assert md.is_empty_answer("Không tìm thấy thông tin này trong các tài liệu QTKĐ được cung cấp.")
    assert md.is_empty_answer("  ")
    assert not md.is_empty_answer("Sai số ≤ 0,4 oC [1]")


def test_merge_identical_groups_same_numbers_and_keeps_refs():
    merged = md.merge_identical(
        [("A", "± 0,2 oC [1]"), ("B", "sai số ± 0,2 oC [2]"), ("C", "± 0,4 oC [3]"), ("D", "không nêu")]
    )

    assert merged == [("A; B", "± 0,2 oC [1] [2]"), ("C", "± 0,4 oC [3]"), ("D", "không nêu")]


def test_render_one_line_per_entry():
    assert md.render([("A", "x [1]"), ("B", "y\n [2]")]) == "- **A**: x [1]\n- **B**: y [2]"


def _hit(stem, text):
    return {
        "payload": {"file_stem": stem, "section_path": "3", "kind": "paragraph", "text": text},
        "rerank_score": 0.9,
    }


def _events(lines):
    return [json.loads(line[6:]) for line in lines if line.startswith("data: ")]


def _patch(monkeypatch, named, answers):
    monkeypatch.setattr("retrieval.retriever.retrieve", lambda *a, **k: [_hit("A", "a 5 bar"), _hit("B", "b 7 bar")])
    monkeypatch.setattr("retrieval.router.route_files", lambda q: frozenset(named))
    monkeypatch.setattr("retrieval.doc_titles.title_for", lambda s: "")
    seen = []

    def fake_chat_once(messages, **kwargs):
        seen.append(messages)
        return answers[len(seen) - 1]

    monkeypatch.setattr("llm.generator.chat_once", fake_chat_once)
    return seen


def test_chat_asks_each_document_separately_with_global_numbers(monkeypatch):
    seen = _patch(monkeypatch, set(), ["5 bar [1]", "7 bar [2]"])

    events = _events(chat_stream.chat_stream_events(ChatRequest(message="Áp suất?"), None))

    assert len(seen) == 2
    assert "[2] Nguồn: B" in seen[1][0]["content"] and "[1] Nguồn: A" not in seen[1][0]["content"]
    assert events[-1]["answer"] == "- **A**: 5 bar [1]\n- **B**: 7 bar [2]"


def test_generic_question_drops_documents_without_content(monkeypatch):
    _patch(monkeypatch, set(), ["5 bar [1]", "không nêu"])

    events = _events(chat_stream.chat_stream_events(ChatRequest(message="Áp suất?"), None))

    assert events[-1]["answer"] == "- **A**: 5 bar [1]"


def test_named_comparison_keeps_no_info_line(monkeypatch):
    _patch(monkeypatch, {"A", "B"}, ["5 bar [1]", "không nêu"])

    events = _events(chat_stream.chat_stream_events(ChatRequest(message="So sánh A và B"), None))

    assert events[-1]["answer"] == "- **A**: 5 bar [1]\n- **B**: không nêu"


def test_single_named_document_uses_one_pass(monkeypatch):
    _patch(monkeypatch, {"A"}, [])
    monkeypatch.setattr("llm.generator.stream_ollama", lambda messages: iter(["5 bar [1]"]))

    events = _events(chat_stream.chat_stream_events(ChatRequest(message="Áp suất của A?"), None))

    assert events[-1]["answer"] == "5 bar [1]"


def test_llm_error_falls_back_to_single_pass(monkeypatch):
    _patch(monkeypatch, set(), [])
    monkeypatch.setattr("llm.generator.stream_ollama", lambda messages: iter(["chung [1]"]))

    events = _events(chat_stream.chat_stream_events(ChatRequest(message="Áp suất?"), None))

    assert events[-1]["answer"] == "chung [1]"
