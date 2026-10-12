"""Chat stream chỉ còn nhánh văn bản: không phân loại intent, ``done`` không có branch/data.

Giữ hành vi nhánh văn bản (SSE sources/delta/done, xử lý mơ hồ thiết bị) và khoá
việc gỡ bộ phân loại intent: module ``query.router`` không còn tồn tại.
"""

from __future__ import annotations

import importlib
import json

import pytest

from api.schemas import ChatRequest
from api.services import chat_stream
from llm.guards import REFUSAL_SENTENCE


def _events(events) -> list[dict]:
    return [json.loads(line[6:]) for line in events if line.startswith("data: ")]


def _hit(file_stem: str, text: str, *, parent: str | None = None) -> dict:
    item = {
        "payload": {
            "file_stem": file_stem,
            "section_path": "6 Tiến hành",
            "kind": "paragraph",
            "text": text,
        },
        "rerank_score": 0.9,
    }
    if parent is not None:
        item["parent_payload"] = {"text": parent}
    return item


def test_done_event_has_only_text_fields(monkeypatch):
    monkeypatch.setattr(
        "retrieval.retriever.retrieve",
        lambda *a, **k: [_hit("QTKD_1.061", "Sai số cho phép là 0,5 %.")],
    )
    monkeypatch.setattr(
        "llm.generator.stream_ollama", lambda messages: iter(["Sai số là 0,5 % [1]"])
    )

    events = _events(list(chat_stream.chat_stream_events(ChatRequest(message="Sai số?"), None)))

    assert [event["type"] for event in events] == ["status", "sources", "status", "delta", "done"]
    done = events[-1]
    assert set(done) == {"type", "answer", "sources"}
    assert done["answer"] == "Sai số là 0,5 % [1]"
    assert done["sources"][0]["file_stem"] == "QTKD_1.061"


def test_empty_retrieval_done_has_no_data_branch(monkeypatch):
    monkeypatch.setattr("retrieval.retriever.retrieve", lambda *a, **k: [])

    events = _events(list(chat_stream.chat_stream_events(ChatRequest(message="hỏi"), None)))

    assert events == [
        {"type": "status", "text": "⏳ Đang nhúng câu hỏi (embedding)…"},
        {
            "type": "done",
            "answer": "Không tìm thấy thông tin liên quan trong tài liệu QTKĐ.",
            "sources": [],
        },
    ]


def test_calculation_guard_returns_refusal_before_retrieval(monkeypatch):
    def _boom(*a, **k):  # pragma: no cover - không được gọi
        raise AssertionError("retrieve không được gọi khi câu hỏi là tính toán")

    monkeypatch.setattr("retrieval.retriever.retrieve", _boom)

    events = _events(
        list(chat_stream.chat_stream_events(ChatRequest(message="tính giúp 2 + 3 = ?"), None))
    )

    assert events == [{"type": "done", "answer": REFUSAL_SENTENCE, "sources": []}]


def test_intent_router_module_is_gone():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("query.router")


def test_generic_device_question_answers_every_type(data_db, monkeypatch):
    from db.models import DeviceType, Procedure

    session, _ = data_db
    h3000 = DeviceType(name_vi="Áp kế píttông kiểu H3000", aliases=["h3000"])
    standard = DeviceType(name_vi="Áp kế píttông tiêu chuẩn", aliases=[])
    session.add_all([h3000, standard])
    session.flush()
    session.add_all(
        [
            Procedure(number="1.071", year=2022, device_type_id=h3000.id),
            Procedure(number="1.159", year=2021, device_type_id=standard.id),
        ]
    )
    session.commit()

    captured: dict = {}

    def fake_retrieve(message, *args, **kwargs):
        captured["query"] = message
        return [
            _hit("QTKD_1.159_2021_ND_FINAL", "phạm vi đo (-0,1 đến 100) MPa"),
            _hit("QTKD_1.071_2022_FINAL", "phạm vi đo từ 10 bar đến 700 bar"),
        ]

    def fake_stream(messages):
        captured["messages"] = messages
        return iter(["- Áp kế píttông tiêu chuẩn: (-0,1 đến 100) MPa [1]"])

    monkeypatch.setattr("retrieval.retriever.retrieve", fake_retrieve)
    monkeypatch.setattr("llm.generator.stream_ollama", fake_stream)

    events = _events(
        list(
            chat_stream.chat_stream_events(
                ChatRequest(message="Áp kế pít tông có phạm vi đo bao nhiêu?"), session
            )
        )
    )
    done = events[-1]

    assert "1.071" in captured["query"] and "1.159" in captured["query"]
    assert "KHÔNG chọn một loại" in captured["messages"][-1]["content"]
    assert done["answer"].startswith("Câu hỏi chưa nêu rõ loại **áp kế píttông** nào.")
    assert "Áp kế píttông kiểu H3000 (QTKĐ 1.071)" in done["answer"]
    assert "Áp kế píttông tiêu chuẩn (QTKĐ 1.159)" in done["answer"]
    assert set(done) == {"type", "answer", "sources"}


def test_source_quote_carries_the_formula_a_definition_refers_to(monkeypatch):
    definition = "$A_{0s}$ là diện tích hiệu dụng của píttông chuẩn, m2;"
    formula = "| $P_{s,i} = \\frac{F}{A_{0s}}$ |  |\n| --- | --- |"
    parent = "\n\n".join(
        ["Áp suất chuẩn được tính theo công thức sau:", formula, "trong đó:", definition]
    )
    monkeypatch.setattr(
        "retrieval.retriever.retrieve",
        lambda *a, **k: [
            {
                "payload": {
                    "file_stem": "QTKD_1.159",
                    "section_path": "6.3.2 Xác định diện tích hiệu dụng",
                    "kind": "paragraph",
                    "text": definition,
                },
                "anchor_texts": [definition],
                "parent_payload": {"text": parent},
                "rerank_score": 0.9,
            }
        ],
    )
    monkeypatch.setattr("llm.generator.stream_ollama", lambda messages: iter(["A0s [1]"]))

    events = _events(list(chat_stream.chat_stream_events(ChatRequest(message="Diện tích?"), None)))

    source = events[-1]["sources"][0]
    assert source["child_text"] == definition
    assert formula in source["quote"]
    assert source["quote"].endswith(definition)


# ── Nhánh văn bản giữ nguyên (port từ test_chat_router_routes.py) ────────────


def test_text_branch_unchanged(monkeypatch):
    """Câu hỏi thường đi thẳng nhánh văn bản: SSE có sources + delta, done có câu trả lời."""
    monkeypatch.setattr(
        "retrieval.retriever.retrieve",
        lambda *a, **k: [_hit("QTKD_1.061", "Sai số cho phép là 0,5 %.")],
    )
    monkeypatch.setattr(
        "llm.generator.stream_ollama", lambda messages: iter(["Sai số là 0,5 % [1]"])
    )
    events = _events(
        list(
            chat_stream.chat_stream_events(
                ChatRequest(message="Sai số cho phép là bao nhiêu?"), None
            )
        )
    )
    types = [event["type"] for event in events]
    assert "sources" in types and "delta" in types
    done = events[-1]
    assert done["type"] == "done"
    assert done["answer"] == "Sai số là 0,5 % [1]"
    assert done["sources"][0]["file_stem"] == "QTKD_1.061"


def test_text_branch_uses_unchanged_retrieve_pipeline(monkeypatch):
    """Nhánh văn bản gọi đúng phễu retrieve của production: ``retrieve()`` trần.

    Độ rộng phễu đọc từ settings.retrieval nên API không truyền top_k/top_n; test
    khóa đúng lời gọi đó (không hồi quy).
    """
    captured: dict = {}

    def fake_retrieve(message, *args, **kwargs):
        captured["message"] = message
        captured["kwargs"] = kwargs
        return []

    monkeypatch.setattr("retrieval.retriever.retrieve", fake_retrieve)
    list(chat_stream.chat_stream_events(ChatRequest(message="Sai số cho phép là bao nhiêu?"), None))
    assert captured["kwargs"] == {}


# ── Câu hỏi nêu loại thiết bị chung chung (khớp nhiều QTKĐ) ───────────────────

GENERIC_PISTON_QUESTION = "Áp kế pít tông có phạm vi đo và cấp chính xác là bao nhiêu?"


@pytest.fixture
def piston_procedures(data_factory):
    """Thêm hai loại áp kế píttông, mỗi loại một QTKĐ, như kho thật (1.071 và 1.159)."""
    from db.models import DeviceType, Procedure

    factory, _ = data_factory
    session = factory()
    try:
        h3000 = DeviceType(name_vi="Áp kế píttông kiểu H3000", aliases=["h3000"])
        standard = DeviceType(name_vi="Áp kế píttông tiêu chuẩn", aliases=[])
        session.add_all([h3000, standard])
        session.flush()
        session.add_all(
            [
                Procedure(number="1.071", year=2022, device_type_id=h3000.id),
                Procedure(number="1.159", year=2021, device_type_id=standard.id),
            ]
        )
        session.commit()
        yield session
    finally:
        session.close()


def test_ambiguous_device_question_answers_text_branch(piston_procedures, monkeypatch):
    """Câu hỏi nêu loại thiết bị chung chung vẫn được trả lời ở nhánh văn bản.

    Bộ phân loại intent/data đã gỡ nên không còn nhánh số liệu trả bảng của một
    QTKĐ; ``done`` chỉ còn trường văn bản (không ``branch``/``data``).
    """
    monkeypatch.setattr(
        "retrieval.retriever.retrieve",
        lambda *a, **k: [_hit("QTKD_1.159_2021_ND_FINAL", "phạm vi đo (-0,1 đến 100) MPa")],
    )
    monkeypatch.setattr(
        "llm.generator.stream_ollama",
        lambda messages: iter(["- Áp kế píttông tiêu chuẩn: (-0,1 đến 100) MPa [1]"]),
    )
    events = _events(
        list(
            chat_stream.chat_stream_events(
                ChatRequest(message=GENERIC_PISTON_QUESTION), piston_procedures
            )
        )
    )
    done = events[-1]
    assert done["type"] == "done"
    assert set(done) == {"type", "answer", "sources"}
    assert done["answer"].startswith("Câu hỏi chưa nêu rõ loại **áp kế píttông** nào.")
    assert "(-0,1 đến 100) MPa [1]" in done["answer"]
    assert done["sources"][0]["file_stem"] == "QTKD_1.159_2021_ND_FINAL"


def test_specific_device_question_has_no_ambiguity_preface(piston_procedures, monkeypatch):
    monkeypatch.setattr(
        "retrieval.retriever.retrieve",
        lambda *a, **k: [_hit("QTKD_1.071_2022_FINAL", "phạm vi đo từ 10 bar đến 700 bar")],
    )
    monkeypatch.setattr(
        "llm.generator.stream_ollama", lambda messages: iter(["10 bar đến 700 bar [1]"])
    )
    events = _events(
        list(
            chat_stream.chat_stream_events(
                ChatRequest(message="Áp kế píttông kiểu H3000 có phạm vi đo bao nhiêu?"),
                piston_procedures,
            )
        )
    )
    done = events[-1]
    assert done["answer"] == "10 bar đến 700 bar [1]"


def test_done_answer_shows_the_source_formula_verbatim(monkeypatch):
    """7b thêm \\left( \\right) khi chép công thức; câu trả lời cuối phải là bản của nguồn."""
    source = r"M = P \times A_{0} \times (1 + \frac{\rho_{a}}{\rho_{Mt}})"
    monkeypatch.setattr(
        "retrieval.retriever.retrieve",
        lambda *a, **k: [_hit("QTKD_1.159_2021_ND_FINAL", f"Theo công thức: ${source}$")],
    )
    rewritten = r"\[ M = P \times A_{0} \times \left(1 + \frac{\rho_{a}}{\rho_{Mt}}\right) \] [1]"
    monkeypatch.setattr("llm.generator.stream_ollama", lambda messages: iter([rewritten]))
    events = _events(
        list(
            chat_stream.chat_stream_events(ChatRequest(message="Công thức tính M của 1.159?"), None)
        )
    )
    done = events[-1]
    assert done["answer"] == f"$${source}$$ [1]"
