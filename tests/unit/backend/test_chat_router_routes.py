"""Tích hợp chat lai vào /api/chat/stream (Sprint 9).

Kiểm ba nhánh không hồi quy: text giữ nguyên pipeline RAG; data trả bảng sổ cái
kèm xuất xứ; mixed ghép cả hai với trích dẫn tách bạch. Cổng tính toán vẫn chặn
trước mọi thứ.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import api_server
from db import get_db
from query import intents, router
from query.table_model import LEDGER_NOTE, Cell, Column, DataTable, make_payload


@pytest.fixture
def client(data_factory):
    factory, _ = data_factory

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    api_server.app.dependency_overrides[get_db] = override_get_db
    with TestClient(api_server.app) as test_client:
        yield test_client
    api_server.app.dependency_overrides.clear()


def _events(response) -> list[dict]:
    events = []
    for line in response.text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def _decision(payload: dict) -> intents.IntentDecision:
    decision = intents.decide(payload)
    assert decision.request is not None
    return decision


def test_calculation_guard_still_first(client, monkeypatch):
    called = {"route": 0}

    def spy(*args, **kwargs):
        called["route"] += 1
        return intents.text_decision("spy")

    monkeypatch.setattr(router, "plan_route", spy)
    response = client.post("/api/chat/stream", json={"message": "tính giúp 2 + 3 = ?"})
    events = _events(response)
    assert events[0]["type"] == "done"
    assert events[0]["answer"] == api_server.REFUSAL_SENTENCE
    assert called["route"] == 0


def test_text_branch_unchanged(client, monkeypatch):
    monkeypatch.setattr(router, "plan_route", lambda *a, **k: intents.text_decision("test"))
    monkeypatch.setattr(
        api_server,
        "retrieve",
        lambda *a, **k: [
            {
                "payload": {
                    "file_stem": "QTKD_1.061",
                    "section_path": "6 Tiến hành",
                    "kind": "paragraph",
                    "text": "Sai số cho phép là 0,5 %.",
                },
                "parent_payload": None,
                "rerank_score": 0.9,
            }
        ],
    )
    monkeypatch.setattr(api_server, "stream_ollama", lambda messages: iter(["Sai số là 0,5 % [1]"]))
    response = client.post("/api/chat/stream", json={"message": "Sai số cho phép là bao nhiêu?"})
    events = _events(response)
    types = [event["type"] for event in events]
    assert "sources" in types and "delta" in types
    done = events[-1]
    assert done["type"] == "done"
    assert done["branch"] == "text"
    assert done["data"] is None
    assert done["sources"][0]["file_stem"] == "QTKD_1.061"


def test_text_branch_uses_unchanged_retrieve_pipeline(client, monkeypatch):
    """Nhánh text phải gọi đúng phễu retrieve của production (không hồi quy)."""
    captured: dict = {}

    def fake_retrieve(message, *args, **kwargs):
        captured["message"] = message
        captured["kwargs"] = kwargs
        return []

    monkeypatch.setattr(router, "plan_route", lambda *a, **k: intents.text_decision("test"))
    monkeypatch.setattr(api_server, "retrieve", fake_retrieve)
    client.post("/api/chat/stream", json={"message": "Sai số cho phép là bao nhiêu?"})
    assert captured["kwargs"] == {"top_k": 50, "top_n": 5}


def test_data_branch_returns_traceable_table(client, monkeypatch):
    monkeypatch.setattr(
        router,
        "plan_route",
        lambda *a, **k: _decision(
            {
                "branch": "data",
                "intent": "device_history",
                "params": {"serial": "SN-1"},
                "confidence": 0.95,
            }
        ),
    )
    response = client.post("/api/chat/stream", json={"message": "Lịch sử kiểm định SN-1?"})
    events = _events(response)
    data_events = [event for event in events if event["type"] == "data"]
    assert data_events, events
    payload = data_events[0]["data"]
    assert payload["intent"] == "device_history"
    assert payload["branch"] == "data"
    table = payload["tables"][0]
    assert table["rows"]
    for row in table["rows"]:
        for cell in row.values():
            if cell["numeric"]:
                assert cell["provenance"], cell

    done = events[-1]
    assert done["branch"] == "data"
    assert done["sources"] == []
    # Câu trả lời nhánh số liệu KHÔNG nhét số vào văn xuôi.
    assert not any(ch.isdigit() for ch in done["answer"])
    assert payload["citations"]


def test_data_branch_answers_an_extreme_with_the_resolver_sentence(client, monkeypatch):
    sentence = "Biên bản 020/2026 của áp kế píttông tiêu chuẩn: trung bình 154,6 s."
    table = DataTable(
        title="Bảng A.2 – Thời gian quay tự do: nhỏ nhất",
        columns=[Column("cert_no", "Số biên bản")],
        rows=[{"cert_no": Cell(text="020/2026")}],
        total=1,
    )
    monkeypatch.setattr(
        router,
        "plan_route",
        lambda *a, **k: _decision(
            {
                "branch": "data",
                "intent": "records_summary",
                "params": {"measure": "min", "field": "A.2"},
                "confidence": 0.95,
            }
        ),
    )
    monkeypatch.setattr(
        router,
        "build_data_payload",
        lambda *a, **k: make_payload(
            intent="records_summary",
            title="Tổng hợp sổ cái",
            note=LEDGER_NOTE,
            tables=[table],
            citations=[],
            answer=sentence,
        ),
    )
    response = client.post(
        "/api/chat/stream",
        json={"message": "Biên bản nào có thời gian quay tự do trung bình thấp nhất"},
    )
    done = _events(response)[-1]
    assert done["branch"] == "data"
    assert done["answer"] == sentence
    assert [t["title"] for t in done["data"]["tables"]] == [table.title]


def test_mixed_branch_keeps_both_citation_blocks(client, monkeypatch):
    monkeypatch.setattr(
        router,
        "plan_route",
        lambda *a, **k: _decision(
            {
                "branch": "mixed",
                "intent": "standards_for",
                "params": {"procedure_number": "1.061"},
                "confidence": 0.9,
            }
        ),
    )
    monkeypatch.setattr(
        api_server,
        "retrieve",
        lambda *a, **k: [
            {
                "payload": {
                    "file_stem": "QTKD_1.061",
                    "section_path": "4 Phương tiện kiểm định",
                    "kind": "paragraph",
                    "text": "Phải dùng áp kế chuẩn.",
                },
                "parent_payload": None,
                "rerank_score": 0.9,
            }
        ],
    )
    monkeypatch.setattr(api_server, "stream_ollama", lambda messages: iter(["Theo QTKĐ [1]"]))
    response = client.post(
        "/api/chat/stream", json={"message": "Phương tiện kiểm định QTKĐ 1.061?"}
    )
    done = _events(response)[-1]
    assert done["branch"] == "mixed"
    assert done["sources"][0]["file_stem"] == "QTKD_1.061"  # trích dẫn QTKĐ
    assert done["data"]["citations"]  # trích dẫn sổ cái, tách bạch


def test_data_lookup_failure_falls_back_to_text(client, monkeypatch):
    monkeypatch.setattr(
        router,
        "plan_route",
        lambda *a, **k: _decision(
            {
                "branch": "data",
                "intent": "device_history",
                "params": {"serial": "KHÔNG-CÓ"},
                "confidence": 0.9,
            }
        ),
    )
    monkeypatch.setattr(api_server, "retrieve", lambda *a, **k: [])
    response = client.post("/api/chat/stream", json={"message": "Lịch sử KHÔNG-CÓ?"})
    done = _events(response)[-1]
    assert done["branch"] == "text"
    assert done["data"] is None


def test_empty_data_result_falls_back_to_text(client, monkeypatch):
    """Bảng số liệu rỗng (intent đúng nhánh nhưng không có dòng nào) không được
    để người dùng không có câu trả lời: rơi về nhánh văn bản như khi tra cứu lỗi."""
    monkeypatch.setattr(
        router,
        "plan_route",
        lambda *a, **k: _decision(
            {
                "branch": "data",
                "intent": "procedure_params",
                "params": {"procedure_number": "9.999"},
                "confidence": 0.9,
            }
        ),
    )
    monkeypatch.setattr(api_server, "retrieve", lambda *a, **k: [])
    response = client.post("/api/chat/stream", json={"message": "Chuẩn Fluke 7302 số 1274?"})
    done = _events(response)[-1]
    assert done["branch"] == "text"
    assert done["data"] is None


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
    finally:
        session.close()
    return factory


def _piston_hit(file_stem: str, text: str) -> dict:
    return {
        "payload": {
            "file_stem": file_stem,
            "section_path": "1 Phạm vi áp dụng",
            "kind": "paragraph",
            "text": text,
        },
        "parent_payload": None,
        "rerank_score": 0.9,
    }


def test_generic_device_type_never_resolves_to_one_procedure(piston_procedures):
    session = piston_procedures()
    try:
        assert router._find_procedure(session, device_type="áp kế pít tông") is None
        # Nêu rõ loại thì vẫn phân giải đúng một QTKĐ.
        assert router._find_procedure(session, device_type="H3000")["number"] == "1.071"
        assert (
            router._find_procedure(session, device_type="áp kế píttông tiêu chuẩn")["number"]
            == "1.159"
        )
    finally:
        session.close()


def test_generic_device_question_answers_every_type(client, piston_procedures, monkeypatch):
    captured: dict = {}

    def fake_retrieve(message, *args, **kwargs):
        captured["retrieve_query"] = message
        return [
            _piston_hit("QTKD_1.159_2021_ND_FINAL", "phạm vi đo (-0,1 đến 100) MPa"),
            _piston_hit("QTKD_1.071_2022_FINAL", "phạm vi đo từ 10 bar đến 700 bar"),
        ]

    def fake_stream(messages):
        captured["messages"] = messages
        return iter(["- Áp kế píttông tiêu chuẩn: (-0,1 đến 100) MPa [1]"])

    monkeypatch.setattr(router, "plan_route", lambda *a, **k: intents.text_decision("test"))
    monkeypatch.setattr(api_server, "retrieve", fake_retrieve)
    monkeypatch.setattr(api_server, "stream_ollama", fake_stream)

    response = client.post("/api/chat/stream", json={"message": GENERIC_PISTON_QUESTION})
    events = _events(response)
    done = events[-1]

    # Truy hồi nêu đủ số QTKĐ của mọi loại → retriever chạy phễu riêng cho từng file.
    assert "1.071" in captured["retrieve_query"] and "1.159" in captured["retrieve_query"]
    # LLM được dặn trả lời riêng từng loại.
    assert "KHÔNG chọn một loại" in captured["messages"][-1]["content"]
    # Câu trả lời nói rõ câu hỏi chưa nêu loại và liệt kê đủ các loại.
    assert done["branch"] == "text"
    assert done["answer"].startswith("Câu hỏi chưa nêu rõ loại **áp kế píttông** nào.")
    assert "Áp kế píttông kiểu H3000 (QTKĐ 1.071)" in done["answer"]
    assert "Áp kế píttông tiêu chuẩn (QTKĐ 1.159)" in done["answer"]
    assert "(-0,1 đến 100) MPa [1]" in done["answer"]
    assert done["answer"].rstrip().endswith("cho đúng loại cần tra cứu.")
    # Đoạn mở đầu cũng được stream để giao diện hiện ngay.
    first_delta = next(event for event in events if event["type"] == "delta")
    assert first_delta["text"].startswith("Câu hỏi chưa nêu rõ loại")


def test_generic_device_question_skips_single_procedure_data_lookup(
    client, piston_procedures, monkeypatch
):
    """Bộ phân loại có bịa số QTKĐ cho câu hỏi chung chung thì nhánh số liệu vẫn không
    được trả bảng của một QTKĐ: câu hỏi không nêu số nào, nên số đó không đáng tin."""
    monkeypatch.setattr(
        router,
        "plan_route",
        lambda *a, **k: _decision(
            {
                "branch": "data",
                "intent": "procedure_params",
                "params": {"procedure_number": "1.061"},
                "confidence": 0.9,
            }
        ),
    )
    monkeypatch.setattr(api_server, "retrieve", lambda *a, **k: [])

    response = client.post("/api/chat/stream", json={"message": GENERIC_PISTON_QUESTION})
    done = _events(response)[-1]

    assert done["branch"] == "text"
    assert done["data"] is None


def test_specific_device_question_has_no_ambiguity_preface(client, piston_procedures, monkeypatch):
    monkeypatch.setattr(router, "plan_route", lambda *a, **k: intents.text_decision("test"))
    monkeypatch.setattr(
        api_server,
        "retrieve",
        lambda *a, **k: [_piston_hit("QTKD_1.071_2022_FINAL", "phạm vi đo từ 10 bar đến 700 bar")],
    )
    monkeypatch.setattr(
        api_server, "stream_ollama", lambda messages: iter(["10 bar đến 700 bar [1]"])
    )

    response = client.post(
        "/api/chat/stream", json={"message": "Áp kế píttông kiểu H3000 có phạm vi đo bao nhiêu?"}
    )
    done = _events(response)[-1]

    assert done["answer"] == "10 bar đến 700 bar [1]"
