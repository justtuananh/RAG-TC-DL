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


def test_merge_identical_builds_neutral_line_with_refs_after_value():
    merged = md.merge_identical(
        [
            ("1.061 (van an toàn)", "Chu kỳ kiểm định của van an toàn là 12 tháng [1]."),
            ("1.062 (bàn tạo áp)", "Chu kỳ là 12 tháng [2]"),
            ("1.063 (bình phân ly)", "12 tháng [3]"),
            ("C", "± 0,4 oC [4]"),
        ]
    )

    assert merged == [
        ("1.061 (van an toàn), 1.062 (bàn tạo áp), 1.063 (bình phân ly)", "12 tháng [1][2][3]"),
        ("C", "± 0,4 oC [4]"),
    ]


def test_merge_identical_keeps_range_between_numbers():
    merged = md.merge_identical([("A", "Phạm vi đo từ 0 đến 100 °C [1]"), ("B", "0 đến 100 °C [2]")])

    assert merged == [("A, B", "0 đến 100 °C [1][2]")]


def test_merge_identical_skips_when_value_too_long_or_missing():
    entries = [("A", "x " * 60 + "5 bar [1]"), ("B", "5 bar [2]")]

    assert md.merge_identical(entries, max_value_chars=20)[0][0] == "A"
    assert md.merge_identical([("A", "không nêu"), ("B", "không nêu")]) == [
        ("A", "không nêu"),
        ("B", "không nêu"),
    ]


def test_names_unknown_document_when_code_absent_from_sources():
    sources = ["Quy trình theo TCVN 1234:2010 và ĐLVN 99"]

    assert md.names_unknown_document("Chu kỳ theo QCVN 01:2008 là bao lâu?", sources)
    assert md.names_unknown_document("Theo nghị định 44/2016/NĐ-CP thì sao?", sources)
    assert not md.names_unknown_document("Theo tcvn 1234:2010 thì sao?", sources)
    assert not md.names_unknown_document("Chu kỳ kiểm định van an toàn?", sources)


def test_uncovered_groups_ignores_negated_and_uncited_sentences():
    groups = md.group_by_document(["A", "B", "C"])
    answer = "A là 5 bar [1]. B không nêu [2]."

    assert [g.stem for g in md.uncovered_groups(answer, groups)] == ["B", "C"]
    assert md.uncovered_groups("5 bar [1] [2]\n9 bar [3]", groups) == []


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


def _general(monkeypatch, text):
    monkeypatch.setattr("llm.generator.stream_ollama", lambda messages: iter([text]))


def test_general_answer_first_then_only_uncovered_document_asked(monkeypatch):
    seen = _patch(monkeypatch, set(), ["7 bar [2]"])
    _general(monkeypatch, "A là 5 bar [1].")

    events = _events(chat_stream.chat_stream_events(ChatRequest(message="Áp suất?"), None))

    assert len(seen) == 1
    assert "[2] Nguồn: B" in seen[0][0]["content"] and "[1] Nguồn: A" not in seen[0][0]["content"]
    assert "A là 5 bar [1]." in events[-1]["answer"] and "- **B**: 7 bar [2]" in events[-1]["answer"]


def test_no_followup_when_general_answer_cites_every_document(monkeypatch):
    seen = _patch(monkeypatch, set(), [])
    _general(monkeypatch, "A 5 bar [1]; B 7 bar [2].")

    chat_stream_events = chat_stream.chat_stream_events(ChatRequest(message="Áp suất?"), None)
    events = _events(chat_stream_events)

    assert seen == []
    assert "- **" not in events[-1]["answer"]


def test_followup_no_info_keeps_general_answer(monkeypatch):
    _patch(monkeypatch, {"A", "B"}, ["không nêu"])
    _general(monkeypatch, "A là 5 bar [1].")

    events = _events(chat_stream.chat_stream_events(ChatRequest(message="So sánh A và B"), None))

    assert "không nêu" not in events[-1]["answer"]
    assert "A là 5 bar [1]." in events[-1]["answer"]


def test_followup_count_is_capped(monkeypatch):
    seen = _patch(monkeypatch, set(), ["x [1]"] * 10)
    monkeypatch.setattr(
        "retrieval.retriever.retrieve", lambda *a, **k: [_hit(c, f"{c} 5 bar") for c in "ABCDEF"]
    )
    cap = chat_stream.get_settings().llm.multi_document.max_followups
    _general(monkeypatch, "chung")

    list(chat_stream.chat_stream_events(ChatRequest(message="Áp suất?"), None))

    assert len(seen) == cap


def test_unknown_document_code_uses_one_pass(monkeypatch):
    seen = _patch(monkeypatch, set(), [])
    _general(monkeypatch, "Tài liệu không nêu QCVN 01:2008.")

    events = _events(chat_stream.chat_stream_events(ChatRequest(message="Chu kỳ theo QCVN 01:2008?"), None))

    assert seen == []
    assert "QCVN 01:2008" in events[-1]["answer"]


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
