"""Tra cứu biên bản có cấu trúc: nhận diện trường, định tuyến tất định, resolver (Pha R).

Fixture đi đúng đường sản phẩm trên SQLite: Phụ lục A thật của QTKĐ 1.159 qua
luật ``phuluc_a`` → duyệt → ``ingest_record_path`` cho 8 biên bản áp kế pít tông
thật trong ``TC_DL/`` → duyệt. Câu hỏi lấy từ bộ ``Bo_20_cau``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import (
    Base,
    DeviceType,
    Document,
    DocumentType,
    Extraction,
    ExtractionStatus,
    Procedure,
)
from db.views import create_all_approved_views
from knowledge import seed_data
from knowledge.extract import extract_appendix_and_store
from query import intents
from query.record_fields import detect_targets, field_catalog
from query.record_intents import RecordLookupParams, RecordsSummaryParams
from query.record_query import (
    _rank_tables,
    extreme_answer,
    resolve_record_lookup,
    resolve_records_summary,
    summary_records,
)
from query.record_signals import disambiguate_records
from query.table_model import untraceable_cells
from records.ingest import ingest_record_path

ROOT = Path(__file__).resolve().parents[3]
QTKD_1159 = ROOT / "build" / "spike_a" / "QTKD_1.159_2021_ND_FINAL.md"
QTKD_STEM = "QTKD_1.159_2021_ND_FINAL"
RECORDS = (
    "SN_1045_2023-06-20",
    "SN_1045_2024-06-25",
    "SN_1045_2024-07-10",
    "SN_1A0043219_2025-05-21",
    "SN_1A0043219_2026-05-19",
    "SN_0391_2024-11-19",
    "SN_1520_2026-04-22",
    "SN_T23-0512_2026-01-13",
)
TEXT = {"branch": "text", "intent": "text", "params": {}}

pytestmark = pytest.mark.skipif(not QTKD_1159.exists(), reason="cần build/spike_a (make ingest)")


def _approve_all(db) -> None:
    db.query(Extraction).filter(Extraction.status == ExtractionStatus.PENDING).update(
        {Extraction.status: ExtractionStatus.APPROVED}
    )
    db.commit()


def _document(stem: str, kind: DocumentType, digest: str) -> Document:
    return Document(
        id=stem,
        file_stem=stem,
        display_name=stem,
        ext="XLSX",
        doc_type=kind,
        sha256=digest,
        size_bytes=1,
    )


@pytest.fixture(scope="module")
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_all_approved_views(connection)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    seed_data.seed_reference_data(session)
    qtkd = _document(QTKD_STEM, DocumentType.QTKD, "a" * 64)
    session.add(qtkd)
    session.commit()
    # Như sổ cái thật: thiết bị mang loại của QTKĐ (câu trả lời nêu "áp kế píttông...").
    device_type = session.query(DeviceType).filter_by(name_vi="Áp kế píttông tiêu chuẩn").one()
    procedure = Procedure(
        number="1.159", year=2021, document_id=QTKD_STEM, device_type_id=device_type.id
    )
    session.add(procedure)
    session.commit()
    extract_appendix_and_store(
        session, qtkd, QTKD_1159.read_text(encoding="utf-8"), procedure=procedure
    )
    _approve_all(session)
    for index, suffix in enumerate(RECORDS):
        stem = f"Biên_bản_kiểm_định_áp_kế_pittông_{suffix}"
        document = _document(stem, DocumentType.PHIEU_DO, f"{index:064d}")
        session.add(document)
        session.commit()
        ingest_record_path(
            session,
            document=document,
            source_path=ROOT / "TC_DL" / f"{stem}.xlsx",
            procedure=procedure,
        )
        session.commit()
    _approve_all(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _texts(payload) -> str:
    return " ".join(
        cell.text for table in payload.tables for row in table.rows for cell in row.values()
    )


def _table(payload, prefix: str):
    return next(table for table in payload.tables if table.title.startswith(prefix))


# ── Nhận diện trường ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "question, fields, steps",
    [
        (
            "Diện tích hiệu dụng pít tông A0 của áp kế МП-60 số hiệu 1045 là bao nhiêu?",
            {"dien_tich_hieu_dung_cua_pittong"},
            set(),
        ),
        ("uCmax và U(p) của áp kế 0391 là bao nhiêu?", {"do_khong_dam_bao_do", "u_p"}, set()),
        ("Phạm vi đo và cấp chính xác của áp kế 0391?", {"pham_vi_do", "cap_chinh_xac"}, set()),
        ("Thời gian quay tự do của áp kế 1045 có đạt không?", {"ket_luan"}, {"A.2"}),
        ("Tốc độ hạ của pít tông của áp kế 1045", set(), {"A.3"}),
        ("Áp suất khí quyển tại điểm 2 500 của biên bản 013/2024", set(), {"A.5"}),
        ("Điều kiện môi trường khi kiểm định áp kế 1045", {"nhiet_do", "do_am"}, set()),
        # Diễn đạt khác bộ câu gốc: thiếu vài từ của tiêu đề bảng, viết tắt.
        ("Kết quả quay tự do trong biên bản 007/2023", set(), {"A.2"}),
        ("Áp kế nào có tốc độ hạ trung bình lớn nhất", set(), {"A.3"}),
        ("Cho tôi dải đo với CCX của áp kế 4471", {"pham_vi_do", "cap_chinh_xac"}, set()),
    ],
)
def test_detect_targets_from_approved_labels(db, question, fields, steps):
    targets = detect_targets(question, field_catalog(db))
    assert fields <= set(targets.fields)
    assert set(targets.steps) == steps


def test_accuracy_class_is_not_confused_with_accuracy_d(db):
    # "đo" (phạm vi đo) không phải "độ" (độ chính xác d).
    targets = detect_targets("Phạm vi đo và cấp chính xác của áp kế 0391?", field_catalog(db))
    assert "do_chinh_xac" not in targets.fields


def test_pressure_words_alone_do_not_pick_the_pressure_balance_table(db):
    targets = detect_targets("Áp suất làm việc của áp kế 1045?", field_catalog(db))
    assert "A.5" not in targets.steps


def test_device_meaning_of_phuong_tien_is_not_the_standard_used(db):
    targets = detect_targets(
        "Phương tiện YS600-19087 lần kiểm mới nhất đạt không", field_catalog(db)
    )
    assert "phuong_tien_kiem_dinh" not in targets.fields


def test_standard_asked_brings_its_method(db):
    question = "Phương tiện (chuẩn) dùng để kiểm định áp kế 1045?"
    targets = detect_targets(question, field_catalog(db))
    assert {"phuong_tien_kiem_dinh", "phuong_phap_kiem_dinh"} <= set(targets.fields)


# ── Định tuyến tất định ───────────────────────────────────────────────────────


def test_specific_record_opens_lookup_even_when_llm_says_text(db):
    question = "Điều kiện môi trường khi kiểm định áp kế pít tông số hiệu 1045 ngày 20/06/2023?"
    routed = disambiguate_records(TEXT, question, db)
    assert routed["intent"] == "record_lookup"
    assert routed["params"]["serial"] == "1045"
    assert routed["params"]["calibrated_on"] == "2023-06-20"


def test_dated_question_overrides_latest_record(db):
    question = "Vì sao biên bản áp kế số hiệu 1045 ngày 25/06/2024 bị kết luận không đạt?"
    llm = {"branch": "data", "intent": "latest_record", "params": {"serial": "1045"}}
    routed = disambiguate_records(llm, question, db)
    assert routed["intent"] == "record_lookup"
    assert routed["params"]["calibrated_on"] == "2024-06-25"


def test_certificate_number_is_not_a_procedure_number(db):
    question = "Phương tiện (chuẩn) dùng để kiểm định áp kế số hiệu 1045 trong biên bản 011/2024?"
    llm = {"branch": "data", "intent": "standards_for", "params": {"procedure_number": "011/2024"}}
    routed = disambiguate_records(llm, question, db)
    assert routed["intent"] == "record_lookup"
    assert routed["params"]["cert_no"] == "011/2024"


def test_times_question_lists_the_devices_records(db):
    """Bo_20_cau câu 6: "mấy lần, lần nào không đạt" là đếm + liệt kê biên bản của thiết bị."""
    question = "Áp kế pít tông số hiệu 1045 được kiểm định mấy lần và lần nào không đạt?"
    llm = {"branch": "data", "intent": "device_history", "params": {"serial": "1045"}}
    routed = disambiguate_records(llm, question, db)
    assert routed["intent"] == "records_summary"
    assert routed["params"] == {"serial": "1045"}


def test_times_question_in_a_mixed_question_keeps_the_regulation_half(db):
    question = (
        "Phạm vi đo theo QTKĐ của áp kế pít tông là bao nhiêu và thiết bị số hiệu 1045 được "
        "kiểm định mấy lần, lần nào không đạt?"
    )
    llm = {"branch": "mixed", "intent": "device_history", "params": {"serial": "1045"}}
    assert disambiguate_records(llm, question, db) == llm


def test_latest_time_question_is_not_a_count(db):
    question = "Áp kế pít tông số hiệu 1045 được kiểm định lần nào gần đây nhất?"
    llm = {"branch": "data", "intent": "latest_record", "params": {"serial": "1045"}}
    assert disambiguate_records(llm, question, db) == llm


def test_history_question_keeps_device_history(db):
    question = "Lịch sử kiểm định của áp kế pít tông số hiệu 1045"
    llm = {"branch": "data", "intent": "device_history", "params": {"serial": "1045"}}
    assert disambiguate_records(llm, question, db) == llm


def test_mixed_regulation_and_history_question_keeps_history(db):
    question = "Quy định phạm vi đo của QTKĐ 1.159 và lịch sử kiểm định thực tế của áp kế 0391"
    llm = {"branch": "mixed", "intent": "device_history", "params": {"serial": "0391"}}
    assert disambiguate_records(llm, question, db) == llm


def test_history_question_repairs_a_made_up_serial(db):
    question = "Áp kế pít tông số hiệu 1045 được kiểm định mấy lần?"
    llm = {"branch": "data", "intent": "device_history", "params": {"serial": "pít tông"}}
    assert disambiguate_records(llm, question, db)["params"]["serial"] == "1045"


def test_inspector_name_from_ledger_routes_to_summary(db):
    question = "Kiểm định viên Phạm Văn Hà đã thực hiện bao nhiêu biên bản áp kế pít tông?"
    llm = {"branch": "data", "intent": "inspector_lookup", "params": {"name": "Phạm Văn H"}}
    routed = disambiguate_records(llm, question, db)
    assert routed["intent"] == "records_summary"
    assert routed["params"]["inspector"] == "Phạm Văn Hà"


def test_owner_org_from_ledger_routes_to_summary(db):
    question = (
        "Các biên bản kiểm định cho Công ty TNHH Khí công nghiệp Đông Phương gồm những số nào?"
    )
    llm = {
        "branch": "data",
        "intent": "lab_standard_lookup",
        "params": {"usage_ref": "Công ty TNHH Khí công nghiệp Đông Phương"},
    }
    routed = disambiguate_records(llm, question, db)
    assert routed["intent"] == "records_summary"
    assert routed["params"] == {"owner_org": "Công ty TNHH Khí công nghiệp Đông Phương"}


def test_owner_org_count_question_replaces_a_made_up_unit(db):
    question = "Nhà máy Nhiệt điện Sông Lam có bao nhiêu biên bản kiểm định?"
    llm = {"branch": "data", "intent": "records_summary", "params": {"range_unit": "Sông Lam"}}
    routed = disambiguate_records(llm, question, db)
    assert routed["params"] == {"owner_org": "Nhà máy Nhiệt điện Sông Lam", "measure": "count"}


def test_distinctive_tail_of_an_owner_name_is_enough(db):
    routed = disambiguate_records(TEXT, "Liệt kê các biên bản của Đông Phương", db)
    assert routed["params"]["owner_org"] == "Công ty TNHH Khí công nghiệp Đông Phương"


def test_generic_words_of_an_owner_name_do_not_filter(db):
    question = "Toàn bộ hồ sơ có bao nhiêu biên bản của phòng đo lường?"
    routed = disambiguate_records(TEXT, question, db)
    assert routed["intent"] == "records_summary"
    assert "owner_org" not in routed["params"]


def test_owner_question_about_one_record_stays_a_lookup(db):
    llm = {"branch": "data", "intent": "latest_record", "params": {"serial": "1045"}}
    routed = disambiguate_records(llm, "Biên bản 011/2024 dùng cho đơn vị nào?", db)
    assert routed["intent"] == "record_lookup"


@pytest.mark.parametrize(
    "question, verdict",
    [
        ("Liệt kê các biên bản không đạt", "khong_dat"),
        (
            "Trong toàn bộ hồ sơ, biên bản nào bị kết luận không đạt và đơn vị sử dụng là gì?",
            "khong_dat",
        ),
        ("Những biên bản nào đạt trong năm 2024?", "dat"),
    ],
)
def test_verdict_as_the_selection_filters_the_records(db, question, verdict):
    routed = disambiguate_records(TEXT, question, db)
    assert routed["intent"] == "records_summary"
    assert routed["params"]["verdict"] == verdict


def test_dated_verdict_question_keeps_records_by_period(db):
    llm = {
        "branch": "data",
        "intent": "records_by_period",
        "params": {"date_from": "2024-01-01", "date_to": "2025-12-31", "verdict": "khong_dat"},
    }
    question = "Các biên bản không đạt trong khoảng 2024 đến 2025"
    assert disambiguate_records(llm, question, db) == llm


@pytest.mark.parametrize(
    "question", ["Có bao nhiêu biên bản không đạt?", "Hồ sơ có mấy biên bản không đạt?"]
)
def test_counting_only_the_failures_filters_the_verdict(db, question):
    routed = disambiguate_records(TEXT, question, db)
    assert routed["params"]["verdict"] == "khong_dat"


def test_dated_period_question_gains_the_verdict_the_llm_left_out(db):
    llm = {
        "branch": "data",
        "intent": "records_by_period",
        "params": {"date_from": "2024-01-01", "date_to": "2024-12-31"},
    }
    routed = disambiguate_records(llm, "Trong năm 2024 có mấy biên bản không đạt?", db)
    assert routed["intent"] == "records_by_period"
    assert routed["params"]["verdict"] == "khong_dat"


def test_counting_failures_next_to_totals_keeps_every_record(db):
    question = (
        "Toàn bộ hồ sơ có bao nhiêu biên bản, bao nhiêu thiết bị (theo số hiệu) và bao nhiêu "
        "biên bản không đạt?"
    )
    routed = disambiguate_records(TEXT, question, db)
    assert routed["intent"] == "records_summary"
    assert "verdict" not in routed["params"]


def test_inspector_card_question_stays_in_the_catalog(db):
    question = "Số thẻ của kiểm định viên Phạm Văn Hà trong hồ sơ là gì?"
    llm = {"branch": "data", "intent": "inspector_lookup", "params": {"name": "Phạm Văn Hà"}}
    assert disambiguate_records(llm, question, db) == llm


def test_extreme_question_routes_to_summary_with_the_compared_field(db):
    question = "Biên bản nào có thời gian quay tự do trung bình thấp nhất, giá trị là bao nhiêu?"
    llm = {"branch": "data", "intent": "error_trend", "params": {"serial": "biên bản"}}
    routed = disambiguate_records(llm, question, db)
    assert routed["intent"] == "records_summary"
    procedure_id = db.query(Procedure).filter(Procedure.number == "1.159").one().id
    assert routed["params"] == {"measure": "min", "field": "A.2", "procedure_ids": [procedure_id]}


def test_unit_filter_routes_to_summary(db):
    question = "Có bao nhiêu áp kế pít tông có phạm vi đo ghi theo đơn vị bar?"
    llm = {"branch": "data", "intent": "devices_by_range", "params": {"unit": "bar"}}
    assert disambiguate_records(llm, question, db)["params"] == {
        "range_unit": "bar",
        "measure": "count",
        "subject": "devices",
    }


def test_listing_by_range_unit_opens_the_summary_even_when_llm_says_text(db):
    routed = disambiguate_records(TEXT, "Liệt kê các áp kế có phạm vi đo theo đơn vị bar", db)
    assert routed["intent"] == "records_summary"
    assert routed["params"] == {"range_unit": "bar", "subject": "devices"}


def test_number_equal_to_a_serial_in_a_regulation_question_stays_text(db):
    question = "Áp kế có phạm vi đo đến 1045 kgf/cm2 thì sai số cho phép là bao nhiêu?"
    assert disambiguate_records(TEXT, question, db) == TEXT


def test_bare_serial_after_a_device_word_is_accepted(db):
    routed = disambiguate_records(TEXT, "Thiết bị 1045 ngày 25/06/2024 kết luận gì?", db)
    assert routed["params"]["serial"] == "1045"


def test_unit_word_in_a_regulation_question_stays_text(db):
    question = "Sai số cho phép tính theo bar là bao nhiêu đối với áp kế píttông?"
    assert disambiguate_records(TEXT, question, db) == TEXT


def test_regulation_question_is_never_opened(db):
    assert disambiguate_records(TEXT, "Chu kỳ kiểm định áp kế píttông là bao lâu?", db) == TEXT


def test_full_classifier_pipeline_uses_record_routing(db, monkeypatch):
    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": '{"branch": "text", "intent": "text", "params": {}}'}}

    monkeypatch.setattr("requests.post", lambda *args, **kwargs: _Response())
    classifier = intents.OllamaIntentClassifier(session_factory=lambda: db)
    decision = intents.decide(
        classifier.classify("A0 của áp kế pít tông số hiệu 1045 biên bản 011/2024?")
    )
    assert decision.branch == "data"
    assert decision.request.intent == "record_lookup"
    assert decision.request.params.cert_no == "011/2024"


# ── Resolver ──────────────────────────────────────────────────────────────────


def test_lookup_returns_verbatim_fields_with_provenance(db):
    payload = resolve_record_lookup(
        db, RecordLookupParams(serial="1045", fields=["dien_tich_hieu_dung_cua_pittong"])
    )
    table = _table(payload, "Thông tin biên bản")
    assert table.total == 3
    assert {row["dien_tich_hieu_dung_cua_pittong"].text for row in table.rows} == {
        "A0 = 0,99796 × 10-4 , m2"
    }
    assert untraceable_cells(payload) == []


def test_failed_record_lists_the_rows_its_verdict_names(db):
    payload = resolve_record_lookup(
        db, RecordLookupParams(serial="1045", calibrated_on="2024-06-25", fields=["ket_luan"])
    )
    basis = _table(payload, "Căn cứ kết luận không đạt")
    assert [(row["measured"].text, row["limit"].text) for row in basis.rows] == [("37,6", "≤ 30")]


def test_nominal_point_filters_the_pressure_balance_table(db):
    payload = resolve_record_lookup(
        db, RecordLookupParams(cert_no="013/2024", steps=["A.5"], nominal=2500)
    )
    table = _table(payload, "Bảng A.5")
    assert table.total == 1
    assert {"1015,99", "60,8", "20,6"} <= {cell.text for cell in table.rows[0].values()}


def test_asked_columns_come_first_after_the_point(db):
    payload = resolve_record_lookup(
        db,
        RecordLookupParams(
            cert_no="013/2024",
            steps=["A.5"],
            nominal=2500,
            focus_words=["áp", "suất", "khí", "quyển", "nhiệt", "độ", "ẩm", "môi", "trường"],
        ),
    )
    labels = [column.label for column in _table(payload, "Bảng A.5").columns]
    assert labels[0] == "TT"
    assert labels[1].startswith("Áp suất danh nghĩa")
    assert set(labels[2:5]) == {
        "Áp suất khí quyển, hPa",
        "Độ ẩm môi trường, %RH",
        "Nhiệt độ môi trường, °C",
    }


def test_run_cells_keep_every_turn(db):
    payload = resolve_record_lookup(
        db, RecordLookupParams(serial="1045", calibrated_on="2024-07-10", steps=["A.3"])
    )
    texts = [cell.text for cell in _table(payload, "Bảng A.3").rows[0].values()]
    assert len(texts) == 5
    assert texts[-1] == "≤ 0,4"


def test_unknown_date_lists_the_devices_records(db):
    payload = resolve_record_lookup(
        db, RecordLookupParams(serial="1045", calibrated_on="2020-01-01")
    )
    assert not payload.empty
    assert payload.tables[0].total == 3


def test_summary_counts_records_devices_and_failures(db):
    """Bo_20_cau câu 20: đếm toàn bộ hồ sơ, nêu rõ biên bản không đạt (không kèm cả sổ cái)."""
    payload = resolve_records_summary(db, RecordsSummaryParams(measure="count"))
    row = _table(payload, "Tổng hợp").rows[0]
    assert (row["records"].text, row["devices"].text, row["failed"].text) == ("8", "5", "2")
    assert row["failed_list"].text == "010/2024, 020/2026"
    assert [table.title for table in payload.tables] == ["Tổng hợp", "Biên bản không đạt"]
    assert payload.answer == (
        "Sổ cái có 8 biên bản đã duyệt của 5 thiết bị (theo số hiệu); 2 biên bản không đạt: "
        "010/2024 (МП-60 SN 1045, độ kín: độ giảm áp sau 5 min vượt 30 kPa) và "
        "020/2026 (CPB5800 SN 1A0043219, thời gian quay tự do dưới 180 s)."
    )


def test_listing_by_inspector_answers_with_each_record(db):
    """Bo_20_cau câu 10: số biên bản + từng biên bản (số, ký hiệu, số hiệu)."""
    payload = resolve_records_summary(db, RecordsSummaryParams(inspector="Phạm Văn Hà"))
    assert payload.answer.splitlines() == [
        "2 biên bản do kiểm định viên Phạm Văn Hà thực hiện:",
        "",
        "- 005/2023 (МП-60, SN 1045), ngày 20/06/2023: đạt",
        "- 013/2024 (МП-2500, SN 0391), ngày 19/11/2024: đạt",
    ]
    assert [table.title for table in payload.tables] == ["Danh sách biên bản"]


def test_one_device_listing_states_each_verdict(db):
    """Bo_20_cau câu 6: mấy lần, lần nào không đạt (kèm lý do nguyên văn kết luận)."""
    payload = resolve_records_summary(db, RecordsSummaryParams(serial="1045"))
    assert payload.answer.splitlines() == [
        "Áp kế píttông tiêu chuẩn МП-60 số hiệu 1045 có 3 biên bản đã duyệt:",
        "",
        "- 005/2023 ngày 20/06/2023: đạt",
        "- 010/2024 ngày 25/06/2024: không đạt (độ kín: độ giảm áp sau 5 min vượt 30 kPa)",
        "- 011/2024 ngày 10/07/2024: đạt",
    ]


def test_minimum_free_rotation_time_is_ranked_verbatim(db):
    payload = resolve_records_summary(db, RecordsSummaryParams(measure="min", field="A.2"))
    top = payload.tables[0].rows[0]
    assert top["cert_no"].text == "020/2026"
    assert top["value"].text == "154,6"
    assert untraceable_cells(payload) == []


def test_extreme_answers_with_the_winning_record_only(db):
    """Bo_20_cau câu 9: một câu trả lời, không kèm danh sách cả sổ cái."""
    payload = resolve_records_summary(db, RecordsSummaryParams(measure="min", field="A.2"))
    assert payload.answer == (
        "Biên bản 020/2026 của áp kế píttông tiêu chuẩn CPB5800 số hiệu 1A0043219, "
        "ngày 19/05/2026: trung bình 154,6 s (cùng chiều kim đồng hồ 157,3 s; "
        "ngược chiều kim đồng hồ 151,9 s), thấp hơn mức cho phép ≥ 180 s nên không đạt."
    )
    assert [table.title for table in payload.tables] == [
        "Bảng A.2 – Thời gian quay tự do: nhỏ nhất"
    ]
    assert [row["cert_no"].text for row in payload.tables[0].rows] == ["020/2026"]
    assert payload.tables[0].total == 1
    assert untraceable_cells(payload) == []


def test_extreme_within_limit_does_not_claim_a_failure(db):
    payload = resolve_records_summary(db, RecordsSummaryParams(measure="max", field="A.2"))
    assert payload.answer is not None
    assert payload.answer.endswith(", trong mức cho phép ≥ 180 s nên đạt.")
    assert "không đạt" not in payload.answer


def test_extreme_answer_lists_procedures_separately(db):
    params = RecordsSummaryParams(measure="min", field="A.2")
    records = summary_records(db, params)
    # Biên bản 020/2026 thuộc một QTKĐ giả lập khác dùng lại mã bảng A.2.
    other = [
        {**record, "procedure_id": 999, "procedure_number": "9.999"}
        if record["cert_no"] == "020/2026"
        else record
        for record in records
    ]
    answer = extreme_answer(_rank_tables(db, other, params, field_catalog(db)))
    lines = answer.splitlines()
    assert lines[0] == "Mỗi QTKĐ so riêng, không so chéo quy trình:"
    assert {line.split(":")[0] for line in lines[2:]} == {"- **QTKĐ 1.159**", "- **QTKĐ 9.999**"}
    assert any(line.startswith("- **QTKĐ 9.999**: Biên bản 020/2026 ") for line in lines)


def test_uncertainty_ranking_compares_across_units_and_shows_expanded_uncertainty(db):
    payload = resolve_records_summary(
        db, RecordsSummaryParams(measure="min", field="do_khong_dam_bao_do")
    )
    top = payload.tables[0].rows[0]
    # 0,025 × 10-3 MPa (25 Pa) < 0,252 × 10-3 bar (25,2 Pa): so sau khi quy đổi SI.
    assert top["serial_no"].text == "1520"
    assert top["related0"].text == "0,050 × 10-3 (MPa) (với k = 2)"
    assert "số hiệu 1520" in payload.answer
    assert "0,050 × 10-3 (MPa) (với k = 2)" in payload.answer


def test_ranking_never_compares_records_of_two_procedures(db):
    params = RecordsSummaryParams(measure="min", field="A.2")
    records = summary_records(db, params)
    # Giả lập nửa sổ cái thuộc một QTKĐ khác dùng lại mã bảng A.2.
    other = [
        {**record, "procedure_id": 999, "procedure_number": "9.999"} if index % 2 else record
        for index, record in enumerate(records)
    ]
    groups = _rank_tables(db, other, params, field_catalog(db))
    assert len(groups) == 2
    assert all("QTKĐ" in group.table.title for group in groups)
    for table in (group.table for group in groups):
        certs = {row["cert_no"].text for row in table.rows}
        procedures = {r["procedure_id"] for r in other if r["cert_no"] in certs}
        assert len(procedures) == 1


def test_range_unit_filter_uses_the_device_range(db):
    """Bo_20_cau câu 11: đếm THIẾT BỊ theo đơn vị phạm vi đo, kèm ký hiệu và dải đo."""
    payload = resolve_records_summary(db, RecordsSummaryParams(range_unit="bar", subject="devices"))
    devices = _table(payload, "Thiết bị")
    assert {row["serial_no"].text for row in devices.rows} == {"1A0043219", "T23-0512"}
    assert "(-1 đến 2) bar;" in _texts(payload)
    assert [table.title for table in payload.tables] == ["Thiết bị"]
    assert payload.answer.splitlines() == [
        "2 thiết bị có phạm vi đo ghi theo đơn vị bar:",
        "",
        "- CPB5800 SN 1A0043219 (1 đến 1 200) bar",
        "- T2300 SN T23-0512 (-1 đến 2) bar",
    ]


def test_inspector_filter(db):
    payload = resolve_records_summary(db, RecordsSummaryParams(inspector="phạm văn hà"))
    certs = {row["cert_no"].text for row in _table(payload, "Danh sách biên bản").rows}
    assert certs == {"005/2023", "013/2024"}


def test_owner_filter_lists_only_that_owners_records(db):
    payload = resolve_records_summary(
        db, RecordsSummaryParams(owner_org="Công ty TNHH Khí công nghiệp Đông Phương")
    )
    certs = {row["cert_no"].text for row in _table(payload, "Danh sách biên bản").rows}
    assert certs == {"015/2025", "020/2026"}


# ── Tham số ───────────────────────────────────────────────────────────────────


def test_lookup_needs_an_identifier():
    with pytest.raises(ValidationError):
        RecordLookupParams(fields=["pham_vi_do"])


@pytest.mark.parametrize("number", ["1.159", "1.061:2021", "QTKĐ 1.190"])
def test_procedure_number_is_not_a_certificate_number(number):
    with pytest.raises(ValidationError):
        RecordLookupParams(cert_no=number)


def test_certificate_number_is_accepted():
    assert RecordLookupParams(cert_no="011/2024").cert_no == "011/2024"


def test_extreme_needs_a_field():
    with pytest.raises(ValidationError):
        RecordsSummaryParams(measure="min")


# ── Câu trả lời tất định cho Bo_20_cau ────────────────────────────────────────


def test_counting_failures_beside_other_counts_is_not_a_filter(db):
    """Câu 20: "bao nhiêu biên bản, … bao nhiêu biên bản không đạt? Nêu rõ biên bản không
    đạt" đếm cả sổ cái; trước đây câu cuối lọc sổ cái còn 2 biên bản."""
    question = (
        "Toàn bộ hồ sơ có bao nhiêu biên bản, bao nhiêu thiết bị (theo số hiệu) và bao "
        "nhiêu biên bản không đạt? Nêu rõ biên bản không đạt."
    )
    routed = disambiguate_records(TEXT, question, db)
    assert routed["intent"] == "records_summary"
    assert routed["params"] == {"measure": "count"}


def test_filter_field_is_not_repeated_on_every_line(db):
    """Câu 10: "kiểm định viên Phạm Văn Hà" là bộ lọc, không phải trường hỏi kèm."""
    question = (
        "Kiểm định viên Phạm Văn Hà đã thực hiện bao nhiêu biên bản áp kế pít tông và đó "
        "là những biên bản nào?"
    )
    routed = disambiguate_records(TEXT, question, db)
    assert routed["params"] == {"inspector": "Phạm Văn Hà"}


def test_fields_follow_the_order_of_the_question(db):
    """Câu 17: kiểm định viên trước người kiểm soát, đúng thứ tự câu hỏi."""
    question = "Kiểm định viên và người kiểm soát của biên bản áp kế PG7601 số hiệu 1520 là ai?"
    fields = detect_targets(question, field_catalog(db)).fields
    assert fields.index("kiem_dinh_vien") < fields.index("nguoi_kiem_soat")


def test_certificate_number_question_answers_with_the_number(db):
    """Câu 1: chỉ hỏi số biên bản: trả số biên bản kèm định danh, không cả phiếu 21 trường."""
    question = (
        "Biên bản kiểm định áp kế pít tông МП-60, số hiệu 1045, ngày 10/07/2024 có số biên "
        "bản là bao nhiêu?"
    )
    routed = disambiguate_records(TEXT, question, db)
    payload = resolve_record_lookup(db, RecordLookupParams(**routed["params"]))
    assert payload.answer == (
        "Số biên bản là 011/2024 (áp kế píttông tiêu chuẩn МП-60 số hiệu 1045, ngày "
        "10/07/2024; đơn vị sử dụng: Công ty CP Cơ khí Thủy lực Hải An)."
    )
    assert [(table.title, len(table.rows)) for table in payload.tables] == [
        ("Thông tin biên bản", 1)
    ]


def test_failure_question_answers_with_the_reason_and_its_basis(db):
    """Câu 7: kết luận nguyên văn + dòng số liệu mà kết luận viện dẫn."""
    payload = resolve_record_lookup(
        db, RecordLookupParams(serial="1045", calibrated_on="2024-06-25", fields=["ket_luan"])
    )
    assert payload.answer == (
        "Biên bản 010/2024 của áp kế píttông tiêu chuẩn МП-60 số hiệu 1045, ngày 25/06/2024: "
        "kết luận không đạt yêu cầu kỹ thuật đo lường (độ kín: độ giảm áp sau 5 min vượt "
        "30 kPa); căn cứ: độ giảm áp suất sau 5 min tại 600 kPa 37,6 kPa, vượt mức cho "
        "phép ≤ 30 kPa."
    )


def test_point_question_answers_the_row_not_the_header_conditions(db):
    """Câu 15: nhiệt độ / độ ẩm TẠI điểm đo là ô của dòng đó, không phải điều kiện ở đầu
    biên bản ("(20 ± 2) ºC")."""
    question = (
        "Tại điểm đo 2 500 kG/cm² của biên bản МП-2500 số hiệu 0391 (013/2024), áp suất khí "
        "quyển, nhiệt độ và độ ẩm môi trường ghi nhận là bao nhiêu?"
    )
    routed = disambiguate_records(TEXT, question, db)
    payload = resolve_record_lookup(db, RecordLookupParams(**routed["params"]))
    assert [table.title.split(" · ")[0] for table in payload.tables] == [
        "Bảng A.5 - Kết quả cân bằng áp suất"
    ]
    assert payload.answer.endswith(
        ": kết quả cân bằng áp suất tại áp suất danh nghĩa 2500,0 kG/cm2: áp suất khí quyển "
        "1015,99 hPa; độ ẩm môi trường 60,8 %RH; nhiệt độ môi trường 20,6 °C."
    )


def test_table_question_across_records_counts_rows_of_every_record(db):
    """Câu 14: "các biên bản có bao nhiêu điểm" đếm dòng Bảng A.5 trên mọi biên bản; dải
    điểm danh nghĩa của biên bản được hỏi là dòng đầu và dòng cuối (không tính bước)."""
    question = (
        "Bảng 3 “Kết quả cân bằng áp suất” của các biên bản có bao nhiêu điểm áp suất danh "
        "nghĩa? Của biên bản 011/2024 là từ bao nhiêu đến bao nhiêu?"
    )
    routed = disambiguate_records(TEXT, question, db)
    assert routed["params"]["across_records"] is True
    payload = resolve_record_lookup(db, RecordLookupParams(**routed["params"]))
    lines = payload.answer.splitlines()
    assert lines[0] == "Bảng A.5 - Kết quả cân bằng áp suất có 10 điểm ở cả 8 biên bản đã duyệt."
    assert lines[2].endswith(
        ": kết quả cân bằng áp suất: 10 điểm, áp suất danh nghĩa từ 6,0 đến 60,0 kG/cm2."
    )


def test_same_value_in_every_record_is_stated_once(db):
    """Câu 4: A0 giống nhau ở cả 3 biên bản của thiết bị 1045: nêu một lần."""
    payload = resolve_record_lookup(
        db, RecordLookupParams(serial="1045", fields=["dien_tich_hieu_dung_cua_pittong"])
    )
    assert payload.answer == (
        "Áp kế píttông tiêu chuẩn МП-60 số hiệu 1045 có 3 biên bản đã duyệt (005/2023 ngày "
        "20/06/2023; 010/2024 ngày 25/06/2024; 011/2024 ngày 10/07/2024), cùng ghi diện tích "
        "hiệu dụng của píttông A0 = 0,99796 × 10-4 , m2."
    )


def test_identity_field_asked_without_being_a_selector_gets_a_direct_answer(db):
    """ "Biên bản 011/2024 kiểm định ngày nào?" hỏi ngày (không phải bộ chọn): trả định danh
    của biên bản, không phải cả phiếu 21 trường."""
    payload = resolve_record_lookup(
        db, RecordLookupParams(cert_no="011/2024", fields=["ngay_kiem_dinh"])
    )
    assert payload.answer == (
        "Biên bản 011/2024 của áp kế píttông tiêu chuẩn МП-60 số hiệu 1045, ngày 10/07/2024 "
        "(đơn vị sử dụng: Công ty CP Cơ khí Thủy lực Hải An)."
    )
    assert [(table.title, len(table.rows)) for table in payload.tables] == [
        ("Thông tin biên bản", 1)
    ]


def test_record_without_asked_field_still_shows_the_card(db):
    """ "Cho xem biên bản 011/2024": không hỏi trường nào → phiếu đầy đủ như trước."""
    payload = resolve_record_lookup(db, RecordLookupParams(cert_no="011/2024"))
    assert payload.tables[0].title.startswith("Biên bản 011/2024")


def test_device_name_question_answers_the_field(db):
    """ "Tên trang bị" là trường định danh không bao giờ là bộ chọn: trả như trường thường."""
    payload = resolve_record_lookup(
        db, RecordLookupParams(cert_no="011/2024", fields=["ten_trang_bi_dl_tn"])
    )
    assert payload.answer == (
        "Biên bản 011/2024 của áp kế píttông tiêu chuẩn МП-60 số hiệu 1045, ngày 10/07/2024: "
        "tên trang bị ĐL-TN Áp kế pít tông."
    )
