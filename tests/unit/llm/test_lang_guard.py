"""Guard CJK: llm.lang_guard.strip_cjk + CjkStreamGuard (+ tích hợp chat_stream).

Mẫu thật: Q6 QTKĐ 1.061 trong đợt đo 03/11/2026, 3/3 lượt model dịch lại cả câu sang
tiếng Trung sau "ứng với". Các ca còn lại là ca tổng hợp cho dạng thế từ.
"""

from __future__ import annotations

import json

from api.schemas import ChatRequest
from api.services import chat_stream
from llm.lang_guard import LANGUAGE_FALLBACK, CjkStreamGuard, strip_cjk

Q6_RAW = (
    "Phạm vi làm việc tối đa của van an toàn theo QTKĐ 1.061 là 1 400 bar, ứng với"
    "范例翻译： 根据QTKD 1.061的规定，安全阀的工作范围上限是1400 bar。[1]"
)
Q6_CLEAN = "Phạm vi làm việc tối đa của van an toàn theo QTKĐ 1.061 là 1 400 bar. [1]"


def _has_cjk(s: str) -> bool:
    return any("⺀" <= c <= "鿿" or "＀" <= c <= "￯" for c in s)


def test_clean_text_is_untouched():
    s = "Sai số là ± 3 % [1]. “Độ chụm” khác độ chính xác [2]."
    out = strip_cjk(s)
    assert (out.text, out.needs_regen, out.fixed, out.empty) == (s, False, False, False)


def test_translation_tail_is_cut_and_citation_kept():
    out = strip_cjk(Q6_RAW)
    assert out.text == Q6_CLEAN
    assert (out.needs_regen, out.fixed) == (False, True)


def test_inline_substitution_removed_and_flagged_for_regen():
    out = strip_cjk("Đơn vị đo là đơn位帕斯卡 (Pa) [1].")
    assert not _has_cjk(out.text)
    assert "(Pa) [1]" in out.text  # không được cắt nhầm phần sau như đuôi dịch
    assert out.needs_regen is True


def test_fullwidth_punctuation_becomes_ascii():
    out = strip_cjk("Tốc độ là 5 m/s。[2]")
    assert out.text == "Tốc độ là 5 m/s.[2]"
    assert out.needs_regen is False


def test_vietnamese_curly_quotes_preserved():
    s = "Gọi là “độ chụm” theo [1]."
    assert strip_cjk(s).text == s


def _tokens_q6() -> list[str]:
    head = ["Phạm vi làm việc tối đa của van an toàn theo QTKĐ 1.061", " là 1 400 bar", ", ứng với"]
    tail = ["范例", "翻译", "：", " 根据", "QTKD", " 1.", "061", "的", "规定", "，", "安全", "阀", "的",
            "工作", "范围", "上限", "是", "1400", " bar", "。", "[", "1", "]"]
    return head + tail


def test_stream_guard_passthrough_for_clean_text():
    g = CjkStreamGuard()
    out = [g.feed(t) for t in ["Sai số", " là 0,5 %", " [1]"]]
    assert out == [("Sai số", False), (" là 0,5 %", False), (" [1]", False)]
    assert g.raw == "Sai số là 0,5 % [1]"


def test_stream_guard_hides_translation_and_stops_after_citation():
    g = CjkStreamGuard()
    emitted, stopped_at = [], None
    for i, t in enumerate(_tokens_q6() + ["TOKEN-THỪA"] * 5):
        text, stop = g.feed(t)
        emitted.append(text)
        if stop:
            stopped_at = i
            break
    assert not _has_cjk("".join(emitted))
    assert stopped_at is not None and _tokens_q6()[stopped_at] == "]"  # dừng đúng sau [1]
    assert strip_cjk(g.raw).text == Q6_CLEAN


def test_stream_guard_runaway_translation_stops_without_citation():
    g = CjkStreamGuard()
    stopped = False
    for _ in range(200):
        _, stop = g.feed("安全阀的工作")
        if stop:
            stopped = True
            break
    assert stopped


def _events(events) -> list[dict]:
    return [json.loads(line[6:]) for line in events if line.startswith("data: ")]


def test_chat_stream_never_emits_cjk_and_closes_source(monkeypatch):
    closed = {"v": False}

    def _fake_stream(messages):
        try:
            yield from _tokens_q6()
            yield from ["TOKEN-THỪA"] * 50
        finally:
            closed["v"] = True  # generator.close() -> ngắt luồng Ollama

    hit = {
        "payload": {"file_stem": "QTKD_1.061", "section_path": "1", "kind": "paragraph", "text": "x"},
        "rerank_score": 0.9,
    }
    monkeypatch.setattr("retrieval.retriever.retrieve", lambda *a, **k: [hit])
    monkeypatch.setattr("llm.generator.stream_ollama", _fake_stream)

    ev = _events(list(chat_stream.chat_stream_events(ChatRequest(message="Phạm vi?"), None)))

    deltas = "".join(e["text"] for e in ev if e["type"] == "delta")
    assert not _has_cjk(deltas)
    done = ev[-1]
    assert done["type"] == "done" and done["answer"] == Q6_CLEAN
    assert closed["v"] is True
    assert "TOKEN-THỪA" not in done["answer"]


def test_translation_tail_does_not_duplicate_citation():
    out = strip_cjk("Chu kỳ kiểm định là 12 tháng. [1] 检定周期为12个月，适用于安全阀的定期检定。[1]")
    assert out.text == "Chu kỳ kiểm định là 12 tháng. [1]"
    assert out.empty is False


def test_all_cjk_answer_is_flagged_empty():
    out = strip_cjk("安全阀的检定周期为十二个月，请参阅相关规程的规定。[1]")
    assert out.empty is True and not _has_cjk(out.text)


def test_valid_vietnamese_with_cjk_noise_is_not_empty():
    out = strip_cjk("Chu kỳ kiểm định của van an toàn là 12 tháng [1]位。")
    assert out.empty is False


def test_chat_stream_all_chinese_answer_uses_vietnamese_fallback(monkeypatch):
    hit = {
        "payload": {"file_stem": "QTKD_1.061", "section_path": "1", "kind": "paragraph", "text": "x"},
        "rerank_score": 0.9,
    }
    monkeypatch.setattr("retrieval.retriever.retrieve", lambda *a, **k: [hit])
    monkeypatch.setattr(
        "llm.generator.stream_ollama",
        lambda messages: iter(["安全阀的", "检定周期", "为十二个月", "，请参阅", "规程规定。", "[1]"]),
    )
    ev = _events(list(chat_stream.chat_stream_events(ChatRequest(message="请用中文回答"), None)))
    assert not _has_cjk("".join(e.get("text", "") for e in ev if e["type"] == "delta"))
    assert ev[-1]["type"] == "done" and ev[-1]["answer"] == LANGUAGE_FALLBACK
