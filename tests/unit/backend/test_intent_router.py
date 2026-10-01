"""Chat lai văn bản + số liệu (Sprint 9): intent, định tuyến, bảng dữ liệu, P1/P3.

Bộ test khoá bốn cổng của spec §9 Sprint 9 ở tầng đơn vị:

- chọn intent + tham số qua pydantic (không có text-to-SQL tự do);
- mặc định rơi về nhánh văn bản khi không chắc;
- nhánh số liệu trả về bảng mà MỌI ô số đều có tham chiếu xuất xứ (P1);
- dữ liệu ``pending`` không lộ ra (P3).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

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


@pytest.mark.parametrize(
    "question, expected",
    [
        ("Phương tiện kiểm định theo quy trình 1.061 là gì, đối chiếu sổ cái?", "standards_for"),
        ("Bảng 2 của QTKĐ 1.159 gồm những gì?", "standards_for"),
        ("Thông số của QTKĐ 1.061 và các lần kiểm trong sổ cái?", "procedure_params"),
    ],
)
def test_branch_name_in_the_intent_slot_is_repaired_from_the_question(question, expected):
    number = re.search(r"\d\.\d{3}", question).group(0)
    payload = {"branch": "mixed", "intent": "mixed", "params": {"procedure_number": number}}
    assert intents.sanitize_classification(payload, question)["intent"] == expected


def test_branch_name_without_a_procedure_stays_invalid():
    payload = {"branch": "data", "intent": "data", "params": {}}
    assert intents.sanitize_classification(payload, "Cho tôi xem dữ liệu")["intent"] == "data"


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
    assert [column.key for column in payload.tables[0].columns][:2] == ["calibrated_at", "cert_no"]
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
    # Kèm đơn vị sai số: error_unit_code nếu có, không thì unit_code của giá trị đo.
    assert errors == ["0.1 %", "0.8 bar"]
    assert router.untraceable_cells(payload) == []


def test_error_trend_shows_units_and_readable_record_label(data_db):
    """Cột Sai số/Giới hạn có đơn vị; cột Hồ sơ hiện số GCN thay vì id nội bộ."""
    session, _ = data_db
    payload = router.build_data_payload(
        session, _request({"intent": "error_trend", "params": {"serial": "SN-1"}})
    )
    table = payload.tables[0]
    assert [row["limit"].text for row in table.rows] == ["0.5 %", "0.5 bar"]
    assert [row["record_id"].text for row in table.rows] == ["C-1", "C-2"]
    # Ô Hồ sơ vẫn bấm được để mở nguồn (P1).
    assert all(row["record_id"].provenance["kind"] == "record" for row in table.rows)
    assert router.untraceable_cells(payload) == []


def test_timeline_shows_document_display_name(data_db):
    """Cột Hồ sơ gốc hiện ``display_name`` của tài liệu, không phải file_stem."""
    session, _ = data_db
    payload = router.build_data_payload(
        session, _request({"intent": "device_history", "params": {"serial": "SN-1"}})
    )
    labels = [row["file_stem"].text for row in payload.tables[0].rows]
    assert labels == ["BB_2024_001.docx", "BB_2024_001.docx"]


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


def test_procedure_params_range_is_shown_in_fact_unit_not_si(data_db):
    """``value_min``/``value_max`` lưu theo SI (Pa); khoảng hiển thị phải đổi về
    đơn vị của dữ kiện, không gắn nhãn "bar" cho con số Pa (lệch 10^5 lần)."""
    from db.models import ProcedureFact, Unit

    session, _ = data_db
    bar = session.query(Unit).filter(Unit.code == "bar").one()
    fact = session.query(ProcedureFact).filter(ProcedureFact.fact_kind == "working_range").one()
    fact.unit_id = bar.id
    session.commit()
    payload = router.build_data_payload(
        session, _request({"intent": "procedure_params", "params": {"procedure_number": "1.061"}})
    )
    ranges = [
        row["value_range"].text for row in payload.tables[0].rows if row["value_range"].numeric
    ]
    assert ranges == ["0 – 1600 bar"]


# ── Cổng tín hiệu mở rộng + chuẩn hoá tham số tất định ────────────────────────


def test_data_signal_gate_covers_real_phrasings():
    """Cổng tín hiệu mở cho câu số liệu thật, kể cả số hiệu chữ-số và số 0 đầu."""
    for question in (
        "Thiết bị 1046 kiểm định lần cuối khi nào",
        "Lần gần đây nhất thiết bị 6112 được kiểm định là khi nào",
        "1A0043219 khi nào hết hạn kiểm định",
        "B280-7702 đã kiểm mấy lần",
        "0391 có biên bản nào không đạt",
        "Các biên bản không đạt năm 2024",
        "Hồ sơ kiểm định trong tháng 5/2026",
        "Danh sách hồ sơ từ 2023 đến 2024",
        "Xu hướng sai số quả cân của áp kế 6112",
        "Thông số tham chiếu của QTKĐ 1.159",
    ):
        assert intents.looks_like_data_question(question) is True, question


def test_data_signal_gate_keeps_text_questions_closed():
    """Câu quy định/công thức về áp kế pittông vẫn đi thẳng nhánh văn bản."""
    for question in (
        "Chu kỳ kiểm định áp kế píttông theo quy định là bao lâu?",
        "Công thức tính diện tích hiệu dụng của píttông áp kế?",
        "Sai số cho phép của áp kế píttông tiêu chuẩn là bao nhiêu?",
        "Cách hiệu chỉnh áp suất khi nhiệt độ thay đổi?",
    ):
        assert intents.looks_like_data_question(question) is False, question


def test_ground_params_keeps_grounded_identifiers():
    grounded = intents.ground_params(
        {"serial": "SN-1", "verdict": "khong_dat"}, "Hồ sơ không đạt của thiết bị SN-1"
    )
    assert grounded == {"serial": "SN-1", "verdict": "khong_dat"}


def test_ground_params_drops_invented_identifiers():
    """Số hiệu/số QTKĐ không có trong câu hỏi (do LLM bịa) bị loại bỏ."""
    assert intents.ground_params({"serial": "SN-1"}, "Lịch sử kiểm định của thiết bị?") == {}
    assert intents.ground_params({"procedure_number": "1.061"}, "Bảng phương tiện?") == {}


def test_ground_params_drops_verdict_without_cue():
    assert intents.ground_params(
        {"date_from": "2024-01-01", "date_to": "2024-12-31", "verdict": "dat_khoang"},
        "Hồ sơ kiểm định trong năm 2024?",
    ) == {"date_from": "2024-01-01", "date_to": "2024-12-31"}


def test_sanitize_classification_enforces_grounding():
    payload = {
        "branch": "data",
        "intent": "device_history",
        "params": {"so_hieu": "SN-1"},
        "confidence": 0.9,
    }
    sanitized = intents.sanitize_classification(payload, "Lịch sử kiểm định của thiết bị?")
    assert sanitized["params"] == {}


def _normalize_question(text: str) -> str:
    return re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE).lower()


def test_prompt_does_not_leak_golden_questions():
    """Không câu hỏi vàng nào (đã bỏ dấu câu, hạ chữ thường) được nhúng vào prompt."""
    golden_path = Path(__file__).resolve().parents[3] / "eval" / "intent_golden.jsonl"
    prompt = _normalize_question(intents.build_classifier_prompt("câu thăm dò ngoài tập vàng"))
    for line in golden_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        question = _normalize_question(json.loads(line)["question"]).strip()
        assert question and question not in prompt, question


def test_extract_json_takes_first_valid_object():
    raw = '{"branch":"data","intent":"latest_record","params":{"serial":"A1"}}\n{"branch":"text"}'
    payload = intents.extract_json(raw)
    assert payload == {
        "branch": "data",
        "intent": "latest_record",
        "params": {"serial": "A1"},
    }


def test_data_signal_uses_device_context_serial():
    for question in (
        "Áp kế 2218 kiểm mấy lần rồi",
        "Thiết bị 4471 lần kiểm mới nhất ra sao",
        "Máy 58-3312 đã kiểm mấy lần",
        "Phương tiện YS600-19087 thay đổi thế nào qua các năm",
    ):
        assert intents.looks_like_data_question(question) is True, question


def test_data_signal_stays_closed_for_device_words_without_serial():
    for question in (
        "Thiết bị chuẩn cần thiết để kiểm định đồng hồ áp suất?",
        "Áp kế píttông hoạt động thế nào?",
        "Máy móc cần bảo trì ra sao?",
    ):
        assert intents.looks_like_data_question(question) is False, question


def test_data_signal_uses_approved_ledger_serials(data_db):
    from datetime import datetime

    from db.models import CalibrationRecord, Device

    session, ids = data_db
    device = Device(device_type_id=ids["device_type_id"], serial_no="4471", serial_norm="4471")
    session.add(device)
    session.flush()
    session.add(
        CalibrationRecord(
            document_id="BB_2024_001",
            extraction_id=ids["record_a_extraction_id"],
            device_id=device.id,
            procedure_id=ids["procedure_id"],
            calibrated_at=datetime(2024, 1, 1),
            verdict="dat",
        )
    )
    session.commit()
    question = "xem 4471 biến thiên ra sao"
    assert intents.looks_like_data_question(question) is False
    assert intents.looks_like_data_question(question, session=session) is True


def test_ground_params_recovers_serial_with_device_prefix():
    grounded = intents.ground_params({"serial": "AP-0391"}, "Áp kế 0391 lần kiểm mới nhất khi nào")
    assert grounded == {"serial": "0391"}
    assert intents.ground_params({"serial": "Máy 58-3312"}, "Máy 58-3312 đã kiểm mấy lần rồi") == {
        "serial": "58-3312"
    }
    assert intents.ground_params({"serial": "SN-1"}, "Lịch sử kiểm định của thiết bị SN-1?") == {
        "serial": "SN-1"
    }


def test_extract_date_range_patterns():
    assert intents.extract_date_range("Hồ sơ trong năm 2024") == {
        "date_from": "2024-01-01",
        "date_to": "2024-12-31",
    }
    assert intents.extract_date_range("Hồ sơ trong tháng 5/2026") == {
        "date_from": "2026-05-01",
        "date_to": "2026-05-31",
    }
    assert intents.extract_date_range("Hồ sơ từ 2023 đến 2024") == {
        "date_from": "2023-01-01",
        "date_to": "2024-12-31",
    }
    assert intents.extract_date_range("Hồ sơ từ 2025 đến 2024") == {
        "date_from": "2025-01-01",
        "date_to": "2024-12-31",
    }


def test_sanitize_classification_normalizes_period_dates():
    payload = {
        "branch": "data",
        "intent": "records_by_period",
        "params": {"date_from": "2024-01-01", "date_to": "2025-12-31"},
    }
    out = intents.sanitize_classification(payload, "Hồ sơ kiểm định từ 2025 đến 2024")
    assert out["params"] == {"date_from": "2025-01-01", "date_to": "2024-12-31"}


def test_procedure_params_answers_only_the_asked_fact(data_db):
    session, _ = data_db
    payload = router.build_data_payload(
        session,
        _request(
            {
                "intent": "procedure_params",
                "params": {"procedure_number": "1.061", "asked_kinds": ["calibration_interval"]},
            }
        ),
    )
    assert payload.answer == "Theo QTKĐ 1.061: chu kỳ kiểm định 12 tháng."
    assert [row["fact_kind"].text for row in payload.tables[0].rows] == ["Chu kỳ kiểm định"]
    assert router.untraceable_cells(payload) == []


def test_procedure_params_without_the_asked_fact_is_empty(data_db):
    """Không có dữ kiện cho điều được hỏi: bảng rỗng để chat rơi về văn bản QTKĐ."""
    session, _ = data_db
    payload = router.build_data_payload(
        session,
        _request(
            {
                "intent": "procedure_params",
                "params": {
                    "procedure_number": "1.061",
                    "asked_kinds": ["env_condition"],
                    "asked_labels": ["nhiet do"],
                },
            }
        ),
    )
    assert payload.empty
