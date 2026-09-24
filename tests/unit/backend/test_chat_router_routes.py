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
