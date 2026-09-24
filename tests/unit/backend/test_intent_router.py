"""Chat lai văn bản + số liệu (Sprint 9): intent, định tuyến, bảng dữ liệu, P1/P3.

Bộ test khoá bốn cổng của spec §9 Sprint 9 ở tầng đơn vị:

- chọn intent + tham số qua pydantic (không có text-to-SQL tự do);
- mặc định rơi về nhánh văn bản khi không chắc;
- nhánh số liệu trả về bảng mà MỌI ô số đều có tham chiếu xuất xứ (P1);
- dữ liệu ``pending`` không lộ ra (P3).
"""

from __future__ import annotations

import pytest

from query import intents, router
from query.records import NotFoundError

VALID_CASES = [
    {"intent": "device_history", "params": {"serial": "SN-1"}},
    {"intent": "latest_record", "params": {"serial": "SN-1"}},
    {
        "intent": "records_by_period",
        "params": {"date_from": "01/01/2024", "date_to": "2024-12-31", "verdict": "đạt"},
    },
    {"intent": "procedure_params", "params": {"procedure_number": "1.061"}},
    {"intent": "procedure_params", "params": {"device_type": "van an toàn"}},
    {
        "intent": "devices_by_range",
        "params": {"quantity": "áp suất", "min_value": 0, "max_value": 100, "unit": "bar"},
    },
    {"intent": "standards_for", "params": {"procedure_number": "1.061"}},
    {"intent": "error_trend", "params": {"serial": "SN-1", "step_code": "6.3.1"}},
]

INVALID_CASES = [
    # thiếu tham số bắt buộc
    {"intent": "device_history", "params": {}},
    {"intent": "standards_for", "params": {}},
    {"intent": "procedure_params", "params": {}},
    # khoảng ngày đảo ngược
    {"intent": "records_by_period", "params": {"date_from": "2025-01-01", "date_to": "2024-01-01"}},
    # records_by_period không có mốc thời gian nào
    {"intent": "records_by_period", "params": {"verdict": "dat"}},
    # khoảng giá trị đảo ngược
    {
        "intent": "devices_by_range",
        "params": {"quantity": "áp suất", "min_value": 100, "max_value": 0},
    },
    # serial rỗng
    {"intent": "latest_record", "params": {"serial": "   "}},
    # intent không nằm trong danh mục
    {"intent": "drop_tables", "params": {}},
]


class ScriptedClassifier:
    """Bộ phân loại tất định cho test (thay cho LLM)."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def classify(self, question: str):
        self.calls += 1
        return self.payload


def _request(payload: dict):
    request = intents.parse_intent(payload)
    assert request is not None, payload
    return request


# ── Schema tham số ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("payload", VALID_CASES)
def test_parse_intent_accepts_valid(payload):
    request = intents.parse_intent(payload)
    assert request is not None
    assert request.intent == payload["intent"]


@pytest.mark.parametrize("payload", INVALID_CASES)
def test_parse_intent_rejects_invalid(payload):
    assert intents.parse_intent(payload) is None


def test_verdict_and_date_are_normalized():
    request = intents.parse_intent(
        {
            "intent": "records_by_period",
            "params": {"tu_ngay": "01/02/2024", "den_ngay": "2024-03-01", "ket_luan": "Không đạt"},
        }
    )
    assert request is not None
    assert request.params.verdict == "khong_dat"
    assert request.params.date_from.isoformat() == "2024-02-01"


# ── Quyết định định tuyến: mặc định rơi về text ───────────────────────────────


def test_decide_defaults_to_text():
    assert intents.decide(None).branch == "text"
    assert intents.decide(None).reason == "classifier_unavailable"
    assert intents.decide("không phải json").branch == "text"
    assert intents.decide({"branch": "text"}).branch == "text"
    # branch data nhưng thiếu tham số hợp lệ → text
    decision = intents.decide(
        {"branch": "data", "intent": "device_history", "params": {}, "confidence": 0.9}
    )
    assert decision.branch == "text"
    assert decision.reason == "invalid_params"


def test_decide_accepts_valid_data():
    decision = intents.decide(
        {
            "branch": "data",
            "intent": "device_history",
            "params": {"so_hieu": "SN-1"},
            "confidence": 0.9,
        }
    )
    assert decision.branch == "data"
    assert decision.request.params.serial == "SN-1"


def test_decide_mixed_branch():
    decision = intents.decide(
        {
            "branch": "mixed",
            "intent": "procedure_params",
            "params": {"procedure_number": "1.061"},
            "confidence": 0.8,
        }
    )
    assert decision.branch == "mixed"
    assert decision.request.intent == "procedure_params"


def test_plan_route_uses_classifier_and_defaults_to_text():
    text = router.plan_route(
        "Sai số cho phép là bao nhiêu?", ScriptedClassifier({"branch": "text"})
    )
    assert text.branch == "text"
    assert text.request is None

    data = router.plan_route(
        "Lần kiểm định gần nhất của SN-1?",
        ScriptedClassifier(
            {
                "branch": "data",
                "intent": "latest_record",
                "params": {"serial": "SN-1"},
                "confidence": 0.9,
            }
        ),
    )
    assert data.branch == "data"
    assert data.request.intent == "latest_record"


def test_plan_route_classifier_failure_falls_back_to_text():
    class Broken:
        def classify(self, question):
            raise RuntimeError("ollama sập")

    assert router.plan_route("...", Broken()).branch == "text"


def test_data_signal_gate_is_conservative():
    """Cổng tín hiệu thô chỉ mở cho câu hỏi số liệu rõ; câu quy định đi thẳng text."""
    assert (
        intents.looks_like_data_question("Sai số cho phép khi kiểm tra van an toàn là bao nhiêu?")
        is False
    )
    assert (
        intents.looks_like_data_question("Điều kiện môi trường khi tiến hành kiểm định áp suất?")
        is False
    )
    assert intents.looks_like_data_question("Công thức hiệu chỉnh nhiệt độ?") is False
    assert intents.looks_like_data_question("Lịch sử kiểm định của thiết bị SN-1?") is True
    assert intents.looks_like_data_question("Hồ sơ kiểm định trong năm 2024?") is True
    assert intents.looks_like_data_question("Phương tiện kiểm định của QTKĐ 1.061?") is True


# ── Bảng dữ liệu + xuất xứ (P1) ───────────────────────────────────────────────


def test_device_history_table_is_traceable(data_db):
    session, _ = data_db
    payload = router.build_data_payload(
        session, _request({"intent": "device_history", "params": {"serial": "SN-1"}})
    )
    assert payload.intent == "device_history"
    assert not payload.empty
    assert router.untraceable_cells(payload) == []
    assert payload.citations
    assert payload.tables[0].total == 2


def test_latest_record_picks_most_recent(data_db):
    session, ids = data_db
    payload = router.build_data_payload(
        session, _request({"intent": "latest_record", "params": {"serial": "SN-1"}})
    )
    row = payload.tables[0].rows[0]
    assert row["verdict"].text == "Không đạt"
    assert row["calibrated_at"].text == "15/01/2025"
    assert row["calibrated_at"].provenance["id"] == ids["record_b_id"]
    assert router.untraceable_cells(payload) == []


def test_records_by_period_filters_and_traces(data_db):
    session, _ = data_db
    payload = router.build_data_payload(
        session,
        _request(
            {
                "intent": "records_by_period",
                "params": {"date_from": "2024-01-01", "date_to": "2024-12-31"},
            }
        ),
    )
    assert payload.tables[0].total == 1
    assert payload.tables[0].rows[0]["calibrated_at"].text == "15/01/2024"
    assert router.untraceable_cells(payload) == []


def test_procedure_params_returns_approved_facts(data_db):
    session, _ = data_db
    payload = router.build_data_payload(
        session, _request({"intent": "procedure_params", "params": {"procedure_number": "1.061"}})
    )
    assert not payload.empty
    kinds = {row["fact_kind"].text for row in payload.tables[0].rows}
    assert "Phạm vi đo" in kinds
    assert router.untraceable_cells(payload) == []


def test_standards_for_returns_table_two(data_db):
    session, _ = data_db
    payload = router.build_data_payload(
        session, _request({"intent": "standards_for", "params": {"procedure_number": "1.061"}})
    )
    assert not payload.empty
    assert payload.tables[0].rows[0]["name_vi"].text == "Áp kế píttông tiêu chuẩn"
    assert router.untraceable_cells(payload) == []


def test_devices_by_range_links_devices(data_db):
    session, ids = data_db
    payload = router.build_data_payload(
        session,
        _request(
            {
                "intent": "devices_by_range",
                "params": {"quantity": "áp suất", "min_value": 0, "max_value": 100, "unit": "bar"},
            }
        ),
    )
    assert not payload.empty
    row = payload.tables[0].rows[0]
    assert row["serial_no"].text == "SN-1"
    assert row["range"].numeric and row["range"].provenance
    assert router.untraceable_cells(payload) == []


def test_error_trend_series_traces_each_point(data_db):
    session, _ = data_db
    payload = router.build_data_payload(
        session, _request({"intent": "error_trend", "params": {"serial": "SN-1"}})
    )
    assert not payload.empty
    errors = [row["error"].text for row in payload.tables[0].rows]
    assert errors == ["0.1", "0.8"]
    assert router.untraceable_cells(payload) == []


def test_unknown_serial_raises_not_found(data_db):
    session, _ = data_db
    with pytest.raises(NotFoundError):
        router.build_data_payload(
            session, _request({"intent": "device_history", "params": {"serial": "KHÔNG-CÓ"}})
        )


def test_pending_device_hidden_from_data_branch(data_db):
    """P3: hồ sơ chưa duyệt không lộ ra qua chat số liệu."""
    session, _ = data_db
    with pytest.raises(NotFoundError):
        router.build_data_payload(
            session, _request({"intent": "device_history", "params": {"serial": "SN-PENDING"}})
        )


def test_payload_serializes_for_sse(data_db):
    session, _ = data_db
    payload = router.build_data_payload(
        session, _request({"intent": "latest_record", "params": {"serial": "SN-1"}})
    )
    body = router.payload_to_dict(payload)
    assert body["branch"] == "data"
    assert body["tables"][0]["columns"][0]["key"] == "calibrated_at"
    assert body["tables"][0]["rows"][0]["calibrated_at"]["provenance"]["kind"] == "record"
