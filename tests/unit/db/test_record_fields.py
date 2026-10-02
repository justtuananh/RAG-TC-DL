"""Trường đầu mục biên bản + nguyên văn từng ô + phạm vi đo của thiết bị (Pha R).

Kiểm bốn lớp: phân tích giá trị trường, ghi ``record_field``/``cells``, view
``v_record_field``/``v_record_detail`` (P3 + phạm vi đo của CHÍNH thiết bị), và đọc
một biên bản áp kế pít tông thật trong ``TC_DL/`` từ đầu tới view.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import (
    Base,
    CalibrationRecord,
    DeviceType,
    Document,
    DocumentType,
    Extraction,
    ExtractionStatus,
    MeasurementPoint,
    Procedure,
    ProcedureFact,
    RecordField,
)
from db.views import create_all_approved_views
from knowledge import seed_data
from knowledge.rules import phuluc_a
from records.backfill import backfill_record
from records.field_values import parse_field_value
from records.store import store_record_draft
from records.template import HeaderField, MappingConfig, ResultTable, _load_table_value, slugify
from records.types import FieldDraft, MeasurementDraft, RecordDraft
from records.xlsx_reader import read_xlsx

ROOT = Path(__file__).resolve().parents[3]
QTKD_1159 = ROOT / "build" / "spike_a" / "QTKD_1.159_2021_ND_FINAL.md"
RECORD_0391 = ROOT / "TC_DL" / "Biên_bản_kiểm_định_áp_kế_pittông_SN_0391_2024-11-19.xlsx"
QTKD_STEM = "QTKD_1.159_2021_ND_FINAL"
RECORD_STEM = "BB_PITTONG_0391"
KGF_CM2 = 98066.5


# ── Phân tích giá trị ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw, rel_op, low, high, unit",
    [
        ("(50 đến 2 500) kgf/cm2;", "range", 50.0, 2500.0, "kgf/cm2"),
        ("(-1 đến 2) bar;", "range", -1.0, 2.0, "bar"),
        ("A0 = 0,59878 × 10-5 , m2", "=", 0.59878e-5, 0.59878e-5, "m2"),
        ("uCmax = 787,500 × 10-3 (kG/cm2) tại p = 1 750,0 kG/cm2", "=", 0.7875, 0.7875, "kG/cm2"),
        ("1 575,000 × 10-3 (kG/cm2) (với k = 2)", "=", 1.575, 1.575, "kG/cm2"),
        ("0,05", "=", 0.05, 0.05, None),
    ],
)
def test_parse_field_value_reads_only_the_source_string(raw, rel_op, low, high, unit):
    parsed = parse_field_value(raw)
    assert parsed.rel_op == rel_op
    assert parsed.value_min == pytest.approx(low)
    assert parsed.value_max == pytest.approx(high)
    assert parsed.unit_text == unit


@pytest.mark.parametrize(
    "raw",
    ["Áp kế píttông PG7302", "QTKĐ 1.159 : 2021", "19/11/2024", "013/2024", "Nga", ""],
)
def test_parse_field_value_ignores_text_dates_and_certificate_numbers(raw):
    assert parse_field_value(raw).value_min is None


def test_parse_field_value_keeps_tolerance_verbatim_without_bounds():
    parsed = parse_field_value("(20 ± 2) ºC")
    assert (parsed.rel_op, parsed.value_min, parsed.value_max) == ("±", None, None)


# ── Ghi + view ────────────────────────────────────────────────────────────────


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_all_approved_views(connection)
    db = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    seed_data.seed_reference_data(db)
    for stem, kind in ((QTKD_STEM, DocumentType.QTKD), (RECORD_STEM, DocumentType.PHIEU_DO)):
        db.add(
            Document(
                id=stem,
                file_stem=stem,
                display_name=f"{stem}.xlsx",
                ext="XLSX",
                doc_type=kind,
                sha256=stem[:1] * 64,
                size_bytes=1,
            )
        )
    db.commit()
    # Seed tham chiếu đã có loại thiết bị của QTKĐ 1.159.
    device_type = (
        db.query(DeviceType).filter(DeviceType.name_vi == "Áp kế píttông tiêu chuẩn").one()
    )
    db.add(Procedure(number="1.159", document_id=QTKD_STEM, device_type_id=device_type.id))
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _procedure(db) -> Procedure:
    return db.query(Procedure).filter(Procedure.number == "1.159").one()


def _document(db) -> Document:
    return db.query(Document).filter(Document.id == RECORD_STEM).one()


def _approve(db, extraction_id: int) -> None:
    db.get(Extraction, extraction_id).status = ExtractionStatus.APPROVED
    db.commit()


def _store(db, draft: RecordDraft, *, approve: bool = True):
    result = store_record_draft(db, document=_document(db), draft=draft, procedure=_procedure(db))
    db.commit()
    if approve:
        _approve(db, result.extraction_id)
    return result


def _detail(db, record_id: int):
    return (
        db.execute(text("SELECT * FROM v_record_detail WHERE id = :id"), {"id": record_id})
        .mappings()
        .one()
    )


def _cells(value) -> list[dict]:
    return value if isinstance(value, list) else json.loads(value)


def _draft(fields: list[FieldDraft]) -> RecordDraft:
    return RecordDraft(
        extractor="record:xlsx.v1",
        source_text="\n".join(f"{item.label}: {item.value}" for item in fields),
        fields=fields,
        measurements=[
            MeasurementDraft(
                step_code="A.2",
                measured_text="205,05",
                measured_value=205.05,
                limit_text="≥ 180",
                quote="212,0 | 198,1 | 205,05 | ≥ 180",
                cells=[
                    {"column": "Kết quả, s Cùng chiều kim đồng hồ", "text": "212,0"},
                    {"column": "Kết quả, s Ngược chiều kim đồng hồ", "text": "198,1"},
                    {"column": "Giá trị trung bình, s", "text": "205,05"},
                    {"column": "Giá trị cho phép, s", "text": "≥ 180"},
                ],
            )
        ],
    )


FIELDS = [
    FieldDraft("Số hiệu", "0391", quote="Số hiệu: | 0391"),
    FieldDraft(
        "Phạm vi đo", "(50 đến 2 500) kgf/cm2;", quote="Phạm vi đo: (50 đến 2 500) kgf/cm2;"
    ),
    FieldDraft("Cấp chính xác", "0,05", quote="Cấp chính xác: 0,05"),
    FieldDraft("Đặc trưng kỹ thuật đo lường", "", quote="Đặc trưng kỹ thuật đo lường:"),
    FieldDraft(
        "U(p)", "1 575,000 × 10-3 (kG/cm2) (với k = 2)", quote="U(p) = | ...", source="record"
    ),
]


def _add_working_ranges(db) -> int:
    """Ba dữ kiện phạm vi đo như QTKĐ 1.159 thật; trả id của dữ kiện rộng nhất."""
    extraction = Extraction(
        document_id=QTKD_STEM,
        section_path="1 Phạm vi áp dụng",
        quote="Phạm vi đo",
        extractor="rule:phamvi.v1",
        extractor_version="v1",
        confidence=0.95,
        status=ExtractionStatus.APPROVED,
    )
    db.add(extraction)
    db.flush()
    ids = []
    for low, high, value_text in (
        (1500.0, 7000000.0, "(0,001 5 đến 7) MPa"),
        (-100000.0, 100000000.0, "(-0,1 đến 100) MPa"),
        (-100000.0, 500000000.0, "(- 0,1 đến 500) MPa"),
    ):
        fact = ProcedureFact(
            extraction_id=extraction.id,
            procedure_id=_procedure(db).id,
            fact_kind="working_range",
            label="Phạm vi đo",
            value_min=low,
            value_max=high,
            value_text=value_text,
        )
        db.add(fact)
        db.flush()
        ids.append(fact.id)
    db.commit()
    return ids[-1]


def test_store_writes_every_non_empty_header_field_with_si_values(session):
    result = _store(session, _draft(FIELDS))
    rows = {
        row["field_key"]: row
        for row in session.execute(
            text("SELECT * FROM v_record_field WHERE record_id = :id"), {"id": result.record_id}
        ).mappings()
    }
    # Trường mẫu để trống không ghi.
    assert set(rows) == {"so_hieu", "pham_vi_do", "cap_chinh_xac", "u_p"}
    assert rows["pham_vi_do"]["value_text"] == "(50 đến 2 500) kgf/cm2;"
    assert rows["pham_vi_do"]["value_min"] == pytest.approx(50 * KGF_CM2)
    assert rows["pham_vi_do"]["value_max"] == pytest.approx(2500 * KGF_CM2)
    assert rows["pham_vi_do"]["unit_code"] == "kgf/cm2"
    assert rows["u_p"]["source"] == "record"
    assert rows["u_p"]["value_min"] == pytest.approx(1.575 * KGF_CM2)
    assert rows["cap_chinh_xac"]["unit_id"] is None
    assert rows["cap_chinh_xac"]["value_min"] == pytest.approx(0.05)


def test_record_fields_and_cells_hidden_until_approved(session):
    result = _store(session, _draft(FIELDS), approve=False)
    count = session.execute(
        text("SELECT COUNT(*) FROM v_record_field WHERE record_id = :id"), {"id": result.record_id}
    ).scalar_one()
    assert count == 0
    _approve(session, result.extraction_id)
    cells = session.execute(
        text("SELECT cells FROM v_measurement_detail WHERE record_id = :id"),
        {"id": result.record_id},
    ).scalar_one()
    assert _cells(cells)[0] == {"column": "Kết quả, s Cùng chiều kim đồng hồ", "text": "212,0"}


def test_record_detail_uses_the_device_range_not_the_procedure_scope(session):
    _add_working_ranges(session)
    result = _store(session, _draft(FIELDS))
    row = _detail(session, result.record_id)
    assert row["range_source"] == "record"
    assert row["range_text"] == "(50 đến 2 500) kgf/cm2;"
    assert row["range_min"] == pytest.approx(50 * KGF_CM2)
    assert row["range_unit_code"] == "kgf/cm2"
    assert row["range_fact_id"] is None
    assert row["range_field_id"] is not None
    assert row["accuracy_text"] == "0,05"
    assert row["accuracy_field_id"] is not None


def test_procedure_fallback_takes_one_fact_never_mixed_bounds(session):
    widest = _add_working_ranges(session)
    result = _store(session, _draft([FieldDraft("Số hiệu", "0391")]))
    row = _detail(session, result.record_id)
    assert row["range_source"] == "procedure"
    assert row["range_fact_id"] == widest
    # Cả hai cận đến từ CÙNG một dữ kiện "(- 0,1 đến 500) MPa".
    assert (row["range_min"], row["range_max"]) == (-100000.0, 500000000.0)
    assert row["range_text"] == "(- 0,1 đến 500) MPa"


# ── Biên bản thật ─────────────────────────────────────────────────────────────


def _config_from_appendix() -> MappingConfig:
    """Cấu hình như ``derive_mapping_config`` dựng từ Phụ lục A thật của QTKĐ 1.159."""
    headers: list[HeaderField] = []
    tables: list[ResultTable] = []
    seen: set[str] = set()
    for index, hit in enumerate(phuluc_a.extract(QTKD_1159.read_text(encoding="utf-8"))):
        key = slugify(hit.label)
        if key in seen:
            continue
        seen.add(key)
        if hit.condition_text == "table":
            columns, _ = _load_table_value(hit.value_text, hit.label)
            tables.append(ResultTable(key=key, title=hit.label, columns=columns, fact_id=index))
        else:
            headers.append(HeaderField(key=key, label=hit.label, fact_id=index))
    return MappingConfig(1, "1.159", headers, tables)


@pytest.mark.skipif(not QTKD_1159.exists(), reason="cần build/spike_a (make ingest)")
def test_real_piston_record_exposes_fields_and_run_cells(session):
    result = _store(session, read_xlsx(RECORD_0391, _config_from_appendix()))
    fields = {
        row["field_key"]: row["value_text"]
        for row in session.execute(
            text("SELECT field_key, value_text FROM v_record_field WHERE record_id = :id"),
            {"id": result.record_id},
        ).mappings()
    }
    assert fields["phuong_tien_kiem_dinh"] == "Áp kế píttông PG7302"
    assert fields["dien_tich_hieu_dung_cua_pittong"] == "A0 = 0,59878 × 10-5 , m2"
    assert fields["u_p"] == "1 575,000 × 10-3 (kG/cm2) (với k = 2)"
    assert _detail(session, result.record_id)["range_text"] == "(50 đến 2 500) kgf/cm2;"

    runs = session.execute(
        text("SELECT cells FROM v_measurement_detail WHERE record_id = :id AND step_code = 'A.2'"),
        {"id": result.record_id},
    ).scalar_one()
    assert [cell["text"] for cell in _cells(runs)][:3] == ["212,0", "198,1", "205,05"]


@pytest.mark.skipif(not QTKD_1159.exists(), reason="cần build/spike_a (make ingest)")
def test_backfill_restores_fields_of_a_pre_phase_r_record(session, monkeypatch):
    config = _config_from_appendix()
    result = _store(session, read_xlsx(RECORD_0391, config))
    # Giả lập hồ sơ nạp trước Pha R: không có trường, không có ô.
    session.query(RecordField).delete()
    session.query(MeasurementPoint).update({MeasurementPoint.cells: None})
    session.commit()

    monkeypatch.setattr("records.backfill.derive_mapping_config", lambda *a, **k: config)
    record = session.get(CalibrationRecord, result.record_id)
    outcome = backfill_record(session, record, RECORD_0391)
    session.commit()

    assert outcome.skipped == []
    keys = {
        row[0]
        for row in session.execute(
            text("SELECT field_key FROM v_record_field WHERE record_id = :id"),
            {"id": result.record_id},
        )
    }
    assert {"pham_vi_do", "do_khong_dam_bao_do", "u_p"} <= keys
    assert outcome.cells > 0
    # Chạy lại không nhân đôi trường.
    backfill_record(session, record, RECORD_0391)
    session.commit()
    again = session.execute(
        text("SELECT COUNT(*) FROM record_field WHERE record_id = :id"), {"id": result.record_id}
    ).scalar_one()
    assert again == outcome.fields


@pytest.mark.skipif(not QTKD_1159.exists(), reason="cần build/spike_a (make ingest)")
def test_backfill_drops_values_missing_from_the_approved_source(session, monkeypatch):
    config = _config_from_appendix()
    result = _store(session, read_xlsx(RECORD_0391, config))
    record = session.get(CalibrationRecord, result.record_id)
    # Nguồn đã duyệt bị cắt mất dòng U(p): giá trị đó không được ghi.
    record.source_text = "\n".join(
        line for line in record.source_text.splitlines() if not line.startswith("U(p)")
    )
    session.commit()
    monkeypatch.setattr("records.backfill.derive_mapping_config", lambda *a, **k: config)
    outcome = backfill_record(session, record, RECORD_0391)
    assert "trường 'U(p)'" in outcome.skipped
