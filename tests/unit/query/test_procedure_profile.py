"""Hồ sơ QTKĐ (trang tri thức): ghép dữ kiện ĐÃ DUYỆT của một QTKĐ thành một trang.

Dựa trên bộ seed dùng chung (QTKĐ 1.061 có phạm vi đo, cấp chính xác, chu kỳ, một
chuẩn, hai biên bản đã duyệt) và bổ sung bước kiểm định, điều kiện môi trường,
công thức, thuật ngữ, kèm một dòng ``pending`` cho mỗi loại để khóa P3.
"""

from __future__ import annotations

import pytest

from db.models import Extraction, ExtractionStatus, Procedure, ProcedureFact, Term
from query import procedure_profile as profile
from tests.unit.conftest import QTKD_STEM

PENDING = ExtractionStatus.PENDING


def _add_fact(session, procedure_id, kind, label, value_text, *, condition=None, status=None):
    extraction = Extraction(
        document_id=QTKD_STEM,
        section_path="3 Các phép kiểm định",
        quote=f"{label} | {value_text}",
        extractor="rule:test.v1",
        confidence=0.95,
        status=status or ExtractionStatus.APPROVED,
    )
    session.add(extraction)
    session.flush()
    fact = ProcedureFact(
        extraction_id=extraction.id,
        procedure_id=procedure_id,
        fact_kind=kind,
        label=label,
        value_text=value_text,
        condition_text=condition,
    )
    session.add(fact)
    session.flush()
    return fact


def _add_term(session, procedure_id, term_vi, term_en, definition, *, status=None):
    extraction = Extraction(
        document_id=QTKD_STEM,
        section_path="2 Thuật ngữ và định nghĩa",
        quote=f"{term_vi} ({term_en}): {definition}",
        extractor="rule:thuatngu.v1",
        confidence=0.95,
        status=status or ExtractionStatus.APPROVED,
    )
    session.add(extraction)
    session.flush()
    term = Term(
        extraction_id=extraction.id,
        procedure_id=procedure_id,
        term_vi=term_vi,
        term_en=term_en,
        definition=definition,
    )
    session.add(term)
    session.flush()
    return term


ALL_MODES = "Chế độ: Ban đầu, Định kỳ, Sau sửa chữa"


@pytest.fixture
def db(data_db):
    session, ids = data_db
    pid = ids["procedure_id"]
    _add_fact(session, pid, "inspection_step", "Kiểm tra bên ngoài", "6.1", condition=ALL_MODES)
    _add_fact(
        session,
        pid,
        "inspection_step",
        "Kiểm tra kỹ thuật",
        "6.2",
        condition="Chế độ: Ban đầu, Sau sửa chữa",
    )
    _add_fact(
        session,
        pid,
        "inspection_step",
        "Kiểm tra đo lường / - Xác định sai số của áp suất chỉnh đặt / - Xác định độ chênh áp",
        "6.3 / 6.3.1 / 6.3.2",
        condition=ALL_MODES,
    )
    _add_fact(session, pid, "inspection_step", "Bước chưa duyệt", "6.9", status=PENDING)
    _add_fact(
        session,
        pid,
        "env_condition",
        "Nhiệt độ môi trường",
        "(20 ± 5) oC",
        condition="sự thay đổi nhiệt độ không lớn hơn 2 oC/h",
    )
    _add_fact(session, pid, "formula", "Sai số áp suất chỉnh đặt", r"$\delta = \frac{p_s - p}{p}$")
    _add_term(session, pid, "Độ chênh áp", "blowdown", "là độ chênh lệch giữa áp suất chỉnh đặt")
    _add_term(session, pid, "Áp suất xả", "relieving pressure", "là áp suất", status=PENDING)
    session.add(Procedure(number="1.190", year=2023, title="THIẾT BỊ HIỆU CHUẨN ÁP SUẤT DPI 610"))
    session.commit()
    return session, ids


# ── Danh sách QTKĐ ────────────────────────────────────────────────────────────


def test_list_procedures_counts_only_approved_knowledge(db):
    session, ids = db
    items, total = profile.list_procedures(session)
    assert total == 2
    by_number = {item["number"]: item for item in items}
    first = by_number["1.061"]
    assert first["id"] == ids["procedure_id"]
    assert first["device_type_name"] == "Van an toàn"
    # 3 dữ kiện seed + 3 bước + 1 điều kiện + 1 công thức; dòng pending không tính.
    assert first["counts"] == {"facts": 8, "standards": 1, "terms": 1, "records": 2}
    assert by_number["1.190"]["counts"] == {"facts": 0, "standards": 0, "terms": 0, "records": 0}


def test_list_procedures_sorted_by_number(db):
    session, _ = db
    items, _ = profile.list_procedures(session)
    assert [item["number"] for item in items] == ["1.061", "1.190"]


@pytest.mark.parametrize("query", ["1.190", "dpi", "hieu chuan", "HIỆU CHUẨN"])
def test_list_procedures_search_is_accent_insensitive(db, query):
    session, _ = db
    items, total = profile.list_procedures(session, q=query)
    assert total == 1
    assert items[0]["number"] == "1.190"


def test_list_procedures_searches_device_type(db):
    session, _ = db
    items, _ = profile.list_procedures(session, q="van an toan")
    assert [item["number"] for item in items] == ["1.061"]


def test_list_procedures_paginates(db):
    session, _ = db
    items, total = profile.list_procedures(session, limit=1, offset=1)
    assert total == 2
    assert [item["number"] for item in items] == ["1.190"]


# ── Hồ sơ một QTKĐ ────────────────────────────────────────────────────────────


def test_profile_header_and_document(db):
    session, ids = db
    result = profile.procedure_profile(session, ids["procedure_id"])
    assert result["procedure"]["number"] == "1.061"
    assert result["procedure"]["year"] == 2021
    assert result["procedure"]["device_type_name"] == "Van an toàn"
    assert result["procedure"]["quantity_name"] == "Áp suất"
    assert result["document"] == {
        "id": QTKD_STEM,
        "file_stem": QTKD_STEM,
        "display_name": f"{QTKD_STEM}.docx",
    }


def test_profile_parameters_always_list_every_kind(db):
    session, ids = db
    parameters = profile.procedure_profile(session, ids["procedure_id"])["parameters"]
    assert [group["kind"] for group in parameters] == [
        "working_range",
        "accuracy_class",
        "max_permissible_error",
        "calibration_interval",
    ]
    by_kind = {group["kind"]: group for group in parameters}
    assert by_kind["working_range"]["label"] == "Phạm vi đo"
    assert [fact["value_text"] for fact in by_kind["working_range"]["items"]] == ["(0 ÷ 1600) bar"]
    assert by_kind["working_range"]["items"][0]["id"] == ids["range_fact_id"]
    assert by_kind["max_permissible_error"]["items"] == []


def test_profile_fact_carries_unit_and_section(db):
    session, ids = db
    parameters = profile.procedure_profile(session, ids["procedure_id"])["parameters"]
    fact = parameters[0]["items"][0]
    assert fact["unit_code"] == "Pa"
    assert fact["value_min"] == 0.0
    assert fact["section_path"] == "1 Phạm vi áp dụng"


def test_profile_steps_matrix_and_sub_steps(db):
    session, ids = db
    steps = profile.procedure_profile(session, ids["procedure_id"])["steps"]
    assert [(step["label"], step["section_ref"], step["depth"]) for step in steps] == [
        ("Kiểm tra bên ngoài", "6.1", 0),
        ("Kiểm tra kỹ thuật", "6.2", 0),
        ("Kiểm tra đo lường", "6.3", 0),
        ("Xác định sai số của áp suất chỉnh đặt", "6.3.1", 1),
        ("Xác định độ chênh áp", "6.3.2", 1),
    ]
    assert steps[1]["modes"] == {"ban_dau": True, "dinh_ky": False, "sau_sua_chua": True}
    assert steps[4]["modes"] == {"ban_dau": True, "dinh_ky": True, "sau_sua_chua": True}
    # Dòng con bóc từ cùng một ô gộp vẫn trỏ về dữ kiện gốc để mở nguyên văn.
    assert steps[2]["fact_id"] == steps[3]["fact_id"] == steps[4]["fact_id"]


def test_profile_step_kept_whole_when_parts_do_not_line_up(db):
    session, ids = db
    _add_fact(
        session,
        ids["procedure_id"],
        "inspection_step",
        "Kiểm tra độ kín / ở áp suất làm việc",
        "6.4",
        condition=ALL_MODES,
    )
    session.commit()
    steps = profile.procedure_profile(session, ids["procedure_id"])["steps"]
    assert steps[-1]["label"] == "Kiểm tra độ kín / ở áp suất làm việc"
    assert steps[-1]["section_ref"] == "6.4"


def test_profile_step_drops_list_bullet_of_its_own_row(db):
    session, ids = db
    _add_fact(
        session,
        ids["procedure_id"],
        "inspection_step",
        "- Kiểm tra độ kín của hệ thống tạo môi trường áp suất",
        "6.2.2",
        condition=ALL_MODES,
    )
    session.commit()
    step = profile.procedure_profile(session, ids["procedure_id"])["steps"][-1]
    assert step["label"] == "Kiểm tra độ kín của hệ thống tạo môi trường áp suất"
    assert step["depth"] == 1


def test_profile_step_without_modes(db):
    session, ids = db
    _add_fact(session, ids["procedure_id"], "inspection_step", "Kiểm tra phụ", None)
    session.commit()
    step = profile.procedure_profile(session, ids["procedure_id"])["steps"][-1]
    assert step["section_ref"] is None
    assert step["modes"] == {"ban_dau": False, "dinh_ky": False, "sau_sua_chua": False}
    assert step["depth"] == 0


def test_profile_modes_order(db):
    session, ids = db
    modes = profile.procedure_profile(session, ids["procedure_id"])["modes"]
    assert modes == [
        {"key": "ban_dau", "label": "Ban đầu"},
        {"key": "dinh_ky", "label": "Định kỳ"},
        {"key": "sau_sua_chua", "label": "Sau sửa chữa"},
    ]


def test_profile_conditions_formulas_standards_terms(db):
    session, ids = db
    result = profile.procedure_profile(session, ids["procedure_id"])
    assert [(c["label"], c["value_text"]) for c in result["conditions"]] == [
        ("Nhiệt độ môi trường", "(20 ± 5) oC")
    ]
    assert result["conditions"][0]["condition_text"].startswith("sự thay đổi")
    assert [f["value_text"] for f in result["formulas"]] == [r"$\delta = \frac{p_s - p}{p}$"]
    standard = result["standards"][0]
    assert standard["name_vi"] == "Áp kế píttông tiêu chuẩn"
    assert standard["extraction_id"] == ids["standard_extraction_id"]
    assert [(t["term_vi"], t["term_en"]) for t in result["terms"]] == [("Độ chênh áp", "blowdown")]
    assert result["terms"][0]["extraction_id"] is not None


def test_profile_records_summary(db):
    session, ids = db
    records = profile.procedure_profile(session, ids["procedure_id"])["records"]
    assert records["total"] == 2
    assert records["verdicts"] == {"dat": 1, "khong_dat": 1}
    assert records["devices"] == 1
    assert records["latest_at"].startswith("2025-01-15")
    assert [r["id"] for r in records["recent"]] == [ids["record_b_id"], ids["record_a_id"]]
    assert records["recent"][0]["serial_no"] == "SN-1"
    assert records["recent"][0]["verdict"] == "khong_dat"


def test_profile_recent_records_put_undated_last(db):
    from db.models import CalibrationRecord

    session, ids = db
    extraction = Extraction(
        document_id="BB_2024_001",
        section_path="Phụ lục A",
        quote="Số hiệu: SN-1 (không ghi ngày)",
        extractor="record:docx.v1",
        confidence=0.9,
        status=ExtractionStatus.APPROVED,
    )
    session.add(extraction)
    session.flush()
    undated = CalibrationRecord(
        document_id="BB_2024_001",
        extraction_id=extraction.id,
        device_id=ids["device_id"],
        procedure_id=ids["procedure_id"],
        verdict="dat",
    )
    session.add(undated)
    session.commit()
    recent = profile.procedure_profile(session, ids["procedure_id"])["records"]["recent"]
    assert [r["id"] for r in recent] == [ids["record_b_id"], ids["record_a_id"], undated.id]


def test_list_procedures_counts_only_the_page(db, monkeypatch):
    session, _ = db
    seen: list[str] = []
    original = session.execute

    def spy(statement, *args, **kwargs):
        seen.append(str(statement))
        return original(statement, *args, **kwargs)

    monkeypatch.setattr(session, "execute", spy)
    profile.list_procedures(session, limit=1)
    count_sql = [sql for sql in seen if "COUNT(*)" in sql]
    assert count_sql and all("procedure_id IN" in sql for sql in count_sql)


def test_profile_never_exposes_pending_rows(db):
    session, ids = db
    result = profile.procedure_profile(session, ids["procedure_id"])
    labels = [step["label"] for step in result["steps"]]
    assert "Bước chưa duyệt" not in labels
    assert "Áp suất xả" not in [t["term_vi"] for t in result["terms"]]
    assert all(r["serial_no"] != "SN-PENDING" for r in result["records"]["recent"])


def test_profile_of_empty_procedure(db):
    session, _ = db
    items, _ = profile.list_procedures(session, q="1.190")
    result = profile.procedure_profile(session, items[0]["id"])
    assert result["document"] is None
    assert all(group["items"] == [] for group in result["parameters"])
    assert result["steps"] == []
    assert result["records"]["total"] == 0
    assert result["records"]["latest_at"] is None


def test_profile_unknown_procedure(db):
    session, _ = db
    with pytest.raises(profile.NotFoundError):
        profile.procedure_profile(session, 999_999)


def test_module_reads_only_views():
    from pathlib import Path

    from db.views import scan_query_source

    assert scan_query_source(Path(profile.__file__)) == []
