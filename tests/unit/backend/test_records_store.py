"""Ghi hồ sơ + số liệu đo qua hàng đợi duyệt, hạn hiệu lực có xuất xứ (Sprint 7)."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import (
    Base,
    CalibrationRecord,
    Device,
    DeviceType,
    Document,
    DocumentType,
    Extraction,
    ExtractionStatus,
    MeasurementPoint,
    Procedure,
    ProcedureFact,
)
from db.views import create_all_approved_views
from records.store import (
    _parse_mode,
    _parse_verdict,
    derive_expiry,
    store_record_draft,
)
from records.types import FieldDraft, MeasurementDraft, RecordDraft

QTKD_STEM = "QTKD_1.061_2021_ND_V2"
RECORD_STEM = "BB_2024_001"


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_all_approved_views(connection)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = factory()
    db.add(
        Document(
            id=QTKD_STEM,
            file_stem=QTKD_STEM,
            display_name=f"{QTKD_STEM}.docx",
            ext="DOCX",
            doc_type=DocumentType.QTKD,
            sha256="0" * 64,
            size_bytes=1,
        )
    )
    db.add(
        Document(
            id=RECORD_STEM,
            file_stem=RECORD_STEM,
            display_name=f"{RECORD_STEM}.docx",
            ext="DOCX",
            doc_type=DocumentType.HO_SO_KIEM_DINH,
            sha256="1" * 64,
            size_bytes=1,
        )
    )
    db.add(DeviceType(name_vi="Van an toàn"))
    db.commit()
    db.add(Procedure(number="1.061", document_id=QTKD_STEM))
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _document(session) -> Document:
    return session.query(Document).filter(Document.id == RECORD_STEM).one()


def _procedure(session) -> Procedure:
    return session.query(Procedure).filter(Procedure.number == "1.061").one()


def _add_interval_fact(
    session,
    *,
    value_text: str,
    status: ExtractionStatus = ExtractionStatus.APPROVED,
) -> int:
    procedure = _procedure(session)
    extraction = Extraction(
        document_id=QTKD_STEM,
        section_path="7 Xử lý chung",
        quote=f"Chu kỳ kiểm định là {value_text}",
        extractor="rule:chuky.v1",
        extractor_version="v1",
        confidence=0.95,
        status=status,
    )
    session.add(extraction)
    session.flush()
    fact = ProcedureFact(
        extraction_id=extraction.id,
        procedure_id=procedure.id,
        fact_kind="calibration_interval",
        label="Chu kỳ kiểm định",
        value_text=value_text,
    )
    session.add(fact)
    session.commit()
    return fact.id


def _draft() -> RecordDraft:
    return RecordDraft(
        extractor="record:docx.v1",
        source_text="BIÊN BẢN KIỂM ĐỊNH\nSố hiệu: SN-1\nNgày kiểm định: 15/01/2024",
        section_path="Phụ lục A",
        fields=[
            FieldDraft("Số hiệu", "SN-1"),
            FieldDraft("Ký hiệu", "VA-1"),
            FieldDraft("Ngày kiểm định", "15/01/2024"),
            FieldDraft("Chế độ kiểm định", "Định kỳ"),
            FieldDraft("Kết luận", "Đạt"),
            FieldDraft("Nhiệt độ", "20"),
            FieldDraft("Độ ẩm", "55"),
        ],
        measurements=[
            MeasurementDraft(
                ord=1,
                measured_text="10,5",
                measured_value=10.5,
                error_text="0,2",
                error_value=0.2,
                quote="1 | 10,5 | 0,2",
            )
        ],
    )


def test_store_creates_pending_record_and_measurement(session):
    fact_id = _add_interval_fact(session, value_text="12 tháng")
    result = store_record_draft(
        session, document=_document(session), draft=_draft(), procedure=_procedure(session)
    )
    session.commit()

    extraction = session.get(Extraction, result.extraction_id)
    assert extraction.status == ExtractionStatus.PENDING
    assert extraction.extractor == "record:docx.v1"

    record = session.get(CalibrationRecord, result.record_id)
    assert record.verdict == "dat"
    assert record.mode == "dinh_ky"
    assert record.env_temp_c == 20
    assert record.env_humidity_pct == 55
    assert record.cert_no is None

    device = session.get(Device, result.device_id)
    assert device.serial_no == "SN-1"
    assert device.needs_identification == 0

    point = session.query(MeasurementPoint).one()
    assert point.error_value == 0.2
    assert point.quote == "1 | 10,5 | 0,2"

    # Ngoại lệ P2: hạn hiệu lực dẫn xuất từ dữ kiện chu kỳ đã duyệt, có xuất xứ.
    assert record.expires_at == datetime(2025, 1, 15)
    assert record.expires_from_fact_id == fact_id


def test_expiry_only_from_approved_interval(session):
    _add_interval_fact(session, value_text="12 tháng", status=ExtractionStatus.PENDING)
    procedure = _procedure(session)
    expires_at, fact_id = derive_expiry(
        session, procedure_id=procedure.id, calibrated_at=datetime(2024, 1, 15)
    )
    assert expires_at is None
    assert fact_id is None


def test_expiry_from_approved_year_interval(session):
    fact_id = _add_interval_fact(session, value_text="01 năm")
    procedure = _procedure(session)
    expires_at, from_fact = derive_expiry(
        session, procedure_id=procedure.id, calibrated_at=datetime(2024, 2, 29)
    )
    # 2024-02-29 + 1 năm → 2025-02-28 (kẹp ngày cuối tháng).
    assert expires_at == datetime(2025, 2, 28)
    assert from_fact == fact_id


def test_pending_records_hidden_until_approved(session):
    _add_interval_fact(session, value_text="12 tháng")
    result = store_record_draft(
        session, document=_document(session), draft=_draft(), procedure=_procedure(session)
    )
    session.commit()

    def count(view: str) -> int:
        return session.execute(text(f"SELECT COUNT(*) FROM {view}")).scalar_one()

    assert count("v_calibration_record") == 0
    assert count("v_measurement_point") == 0

    extraction = session.get(Extraction, result.extraction_id)
    extraction.status = ExtractionStatus.APPROVED
    session.commit()
    assert count("v_calibration_record") == 1
    assert count("v_measurement_point") == 1


def test_reingest_supersedes_previous_record(session):
    _add_interval_fact(session, value_text="12 tháng")
    first = store_record_draft(
        session, document=_document(session), draft=_draft(), procedure=_procedure(session)
    )
    session.commit()
    second = store_record_draft(
        session, document=_document(session), draft=_draft(), procedure=_procedure(session)
    )
    session.commit()

    assert second.superseded == 1
    assert session.query(CalibrationRecord).count() == 2  # giữ lịch sử
    assert session.get(Extraction, first.extraction_id).status == ExtractionStatus.SUPERSEDED


def test_parse_mode_and_verdict_aliases():
    assert _parse_mode("Định kỳ") == "dinh_ky"
    assert _parse_mode("Sau sửa chữa") == "sau_sua_chua"
    assert _parse_verdict("Đạt") == "dat"
    # "Không đạt" không bị "đạt" cắt mất.
    assert _parse_verdict("Không đạt") == "khong_dat"
    assert _parse_verdict("Kết luận: Không đạt yêu cầu") == "khong_dat"
    assert _parse_verdict("") is None


def test_missing_serial_flags_device(session):
    draft = _draft()
    draft.fields = [f for f in draft.fields if f.label != "Số hiệu"]
    result = store_record_draft(
        session, document=_document(session), draft=draft, procedure=_procedure(session)
    )
    session.commit()
    assert result.needs_identification is True
    assert session.get(Device, result.device_id).needs_identification == 1
