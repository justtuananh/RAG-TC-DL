"""Tính trong chat bằng công thức đã duyệt."""

import json

import pytest

from formula_lab.engine import Invalid
from llm import generator
from query import chat_calc


def _formula(fid="F-1", title="Sai số áp suất chỉnh đặt", expression="pm-pcd", unit="Pa"):
    return {
        "id": fid,
        "revision": 3,
        "status": "approved",
        "source": {"file": "QTKD_1.061_2021_ND_V2.docx", "section": "6.3"},
        "proposal": {
            "title": title,
            "expression": expression,
            "unit": unit,
            "variables": [
                {"key": "pm", "label": "Áp suất mở van", "unit": "Pa", "min": 0},
                {"key": "pcd", "label": "Áp suất chỉnh đặt", "unit": "Pa", "min": 0},
            ],
            "conditions": [{"key": "applicability", "label": "Van thuộc phạm vi QTKĐ 1.061."}],
        },
    }


class FakeRegistry:
    def __init__(self, formulas, fail=None):
        self.formulas, self.fail, self.calls = formulas, fail, []

    def approved(self):
        return self.formulas

    def compute(self, fid, revision, inputs, confirmations):
        self.calls.append((fid, revision, inputs, confirmations))
        if self.fail:
            raise self.fail
        pm = float(inputs["pm"]["value"]) * {"bar": 1e5, "Pa": 1}[inputs["pm"]["unit"]]
        pcd = float(inputs["pcd"]["value"]) * {"bar": 1e5, "Pa": 1}[inputs["pcd"]["unit"]]
        return {"status": "ok", "value": str(round(pm - pcd)), "unit": "Pa"}


def _llm(monkeypatch, payload):
    monkeypatch.setattr(generator, "chat_once", lambda *a, **k: json.dumps(payload))


Q = "Van an toàn có áp suất chỉnh đặt Pcd = 40 bar, áp suất mở van Pm = 42 bar. Tính sai số áp suất chỉnh đặt."


def test_no_calculation_intent_returns_none(monkeypatch):
    assert chat_calc.try_calc("Sai số cho phép của áp suất chỉnh đặt là bao nhiêu?", registry=FakeRegistry([_formula()])) is None


def test_no_approved_formula_returns_none(monkeypatch):
    assert chat_calc.try_calc(Q, registry=FakeRegistry([])) is None


def test_computes_with_approved_formula(monkeypatch):
    _llm(monkeypatch, {"F1": {"pm": {"value": "42", "unit": "bar"}, "pcd": {"value": "40", "unit": "bar"}}})
    reg = FakeRegistry([_formula()])
    out = chat_calc.try_calc(Q, registry=reg)
    assert out.kind == "answer"
    assert "kết quả = 200000 Pa (= 2 bar = 0,2 MPa)" in out.block
    assert reg.calls[0][3] == {"applicability": True}
    assert "Van thuộc phạm vi QTKĐ 1.061." in out.block


def test_value_not_in_question_is_discarded_then_asks(monkeypatch):
    _llm(monkeypatch, {"F1": {"pm": {"value": "99", "unit": "bar"}, "pcd": {"value": "40", "unit": "bar"}}})
    out = chat_calc.try_calc(Q, registry=FakeRegistry([_formula()]))
    assert out.kind == "ask" and "Áp suất mở van" in out.text and "Áp suất chỉnh đặt" not in out.text.split("Còn thiếu")[1]


def test_missing_variable_asks(monkeypatch):
    _llm(monkeypatch, {"F1": {"pcd": {"value": "40", "unit": "bar"}, "pm": None}})
    out = chat_calc.try_calc("Áp suất chỉnh đặt 40 bar, hãy tính sai số áp suất chỉnh đặt.", registry=FakeRegistry([_formula()]))
    assert out.kind == "ask" and "pm" in out.text


def test_engine_rejection_is_reported(monkeypatch):
    _llm(monkeypatch, {"F1": {"pm": {"value": "42", "unit": "bar"}, "pcd": {"value": "40", "unit": "bar"}}})
    out = chat_calc.try_calc(Q, registry=FakeRegistry([_formula()], fail=Invalid("Đơn vị không tương thích: pm")))
    assert out.kind == "invalid" and "không hợp lệ" in out.text


def test_llm_failure_means_fallback(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(generator, "chat_once", boom)
    assert chat_calc.try_calc(Q, registry=FakeRegistry([_formula()])) is None


def test_unrelated_formula_is_not_selected(monkeypatch):
    other = _formula(fid="F-2", title="Dung tích bình", expression="500-vd")
    other["proposal"]["variables"] = [{"key": "vd", "label": "Nước còn lại trong ống đong", "unit": "mL"}]
    called = []
    monkeypatch.setattr(generator, "chat_once", lambda *a, **k: called.append(1) or "{}")
    assert chat_calc.try_calc(Q, registry=FakeRegistry([other])) is None
    assert called == []
