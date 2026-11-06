"""Viết lại câu hỏi tiếp theo thành câu độc lập."""

from llm import generator
from query import history_context

PRIOR = [["Nhiệt độ môi trường khi kiểm định bàn tạo áp là bao nhiêu?", "Là (23 ± 5) oC [1]."]]


def _patch(monkeypatch, reply=None, exc=None):
    calls = []

    def fake(messages, **kw):
        calls.append(messages)
        if exc:
            raise exc
        return reply

    monkeypatch.setattr(generator, "chat_once", fake)
    return calls


def test_no_history_means_no_llm_call(monkeypatch):
    calls = _patch(monkeypatch, "x")
    assert history_context.standalone_query("Còn độ ẩm?", []) == "Còn độ ẩm?"
    assert calls == []


def test_followup_is_rewritten(monkeypatch):
    calls = _patch(monkeypatch, "Độ ẩm tương đối khi kiểm định bàn tạo áp là bao nhiêu?")
    out = history_context.standalone_query("Còn độ ẩm thì sao?", PRIOR)
    assert out == "Độ ẩm tương đối khi kiểm định bàn tạo áp là bao nhiêu?"
    assert "bàn tạo áp" in calls[0][1]["content"]


def test_llm_error_falls_back_to_original(monkeypatch):
    _patch(monkeypatch, exc=RuntimeError("down"))
    assert history_context.standalone_query("Còn độ ẩm?", PRIOR) == "Còn độ ẩm?"


def test_invented_number_falls_back(monkeypatch):
    _patch(monkeypatch, "Độ ẩm bàn tạo áp ở 99 bar là bao nhiêu?")
    assert history_context.standalone_query("Còn độ ẩm?", PRIOR) == "Còn độ ẩm?"


def test_empty_or_too_long_falls_back(monkeypatch):
    _patch(monkeypatch, "")
    assert history_context.standalone_query("Còn độ ẩm?", PRIOR) == "Còn độ ẩm?"
    _patch(monkeypatch, "a" * 500)
    assert history_context.standalone_query("Còn độ ẩm?", PRIOR) == "Còn độ ẩm?"
