"""Fixture dùng chung cho bề mặt tra cứu dữ liệu (Sprint 8).

Dựng một CSDL SQLite in-memory đã có view đã duyệt + một bộ dữ liệu nhỏ nhưng đủ
để kiểm: một thiết bị có hai lần kiểm định đã duyệt (một đạt, một không đạt, cùng
một mốc đo), dữ kiện QTKĐ đã duyệt (phạm vi đo + cấp chính xác + chu kỳ), và một
hồ sơ ``pending`` phải luôn bị ẩn khỏi mọi bề mặt tra cứu (P3).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
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
    ProcedureStandard,
    Quantity,
    Unit,
)
from db.views import create_all_approved_views

QTKD_STEM = "QTKD_1.061_2021_ND_V2"
RECORD_STEM = "BB_2024_001"


def _extraction(
    document_id: str,
    *,
    section: str,
    chunk: str,
    quote: str,
    extractor: str,
    status: ExtractionStatus = ExtractionStatus.APPROVED,
    confidence: float = 0.9,
) -> Extraction:
    return Extraction(
        document_id=document_id,
        section_path=section,
        chunk_id=chunk,
        quote=quote,
        extractor=extractor,
        extractor_version="v1",
        confidence=confidence,
        status=status,
    )


def seed_dataset(session) -> dict:
    """Seed một bộ dữ liệu đã duyệt nhỏ; trả dict id để test bám vào."""
    quantity = Quantity(code="pressure", name_vi="Áp suất", si_unit_code="Pa")
    session.add(quantity)
    session.flush()
    unit_pa = Unit(
        code="Pa", name_vi="Pascal", quantity_id=quantity.id, factor_to_si=1.0, offset_to_si=0.0
    )
    unit_bar = Unit(
        code="bar", name_vi="Bar", quantity_id=quantity.id, factor_to_si=100000.0, offset_to_si=0.0
    )
    device_type = DeviceType(name_vi="Van an toàn", quantity_id=quantity.id)
    session.add_all([unit_pa, unit_bar, device_type])
    session.flush()

    session.add_all(
        [
            Document(
                id=QTKD_STEM,
                file_stem=QTKD_STEM,
                display_name=f"{QTKD_STEM}.docx",
                ext="DOCX",
                doc_type=DocumentType.QTKD,
                sha256="0" * 64,
                size_bytes=1,
            ),
            Document(
                id=RECORD_STEM,
                file_stem=RECORD_STEM,
                display_name=f"{RECORD_STEM}.docx",
                ext="DOCX",
                doc_type=DocumentType.HO_SO_KIEM_DINH,
                sha256="1" * 64,
                size_bytes=1,
            ),
        ]
    )
    session.flush()
    procedure = Procedure(
        number="1.061",
        year=2021,
        title="Van an toàn",
        document_id=QTKD_STEM,
        device_type_id=device_type.id,
    )
    session.add(procedure)
    session.flush()

    range_extraction = _extraction(
        QTKD_STEM,
        section="1 Phạm vi áp dụng",
        chunk="chunk-range",
        quote="Phạm vi đo (0 ÷ 1600) bar",
        extractor="rule:phamvi.v1",
        confidence=0.95,
    )
    accuracy_extraction = _extraction(
        QTKD_STEM,
        section="6 Tiến hành",
        chunk="chunk-accuracy",
        quote="Sai số cho phép ± 0,5 % áp suất chỉnh đặt",
        extractor="rule:bang2.v1",
    )
    interval_extraction = _extraction(
        QTKD_STEM,
        section="7 Xử lý chung",
        chunk="chunk-interval",
        quote="Chu kỳ kiểm định là 12 tháng",
        extractor="rule:chuky.v1",
        confidence=0.98,
    )
    session.add_all([range_extraction, accuracy_extraction, interval_extraction])
    session.flush()
    range_fact = ProcedureFact(
        extraction_id=range_extraction.id,
        procedure_id=procedure.id,
        fact_kind="working_range",
        label="Phạm vi",
        value_min=0.0,
        value_max=160000000.0,
        unit_id=unit_pa.id,
        value_text="(0 ÷ 1600) bar",
    )
    accuracy_fact = ProcedureFact(
        extraction_id=accuracy_extraction.id,
        procedure_id=procedure.id,
        fact_kind="accuracy_class",
        label="Cấp chính xác",
        value_text="± 0,5 %",
    )
    interval_fact = ProcedureFact(
        extraction_id=interval_extraction.id,
        procedure_id=procedure.id,
        fact_kind="calibration_interval",
        label="Chu kỳ kiểm định",
        value_text="12 tháng",
    )
    session.add_all([range_fact, accuracy_fact, interval_fact])
    session.flush()

    standard_extraction = _extraction(
        QTKD_STEM,
        section="4 Phương tiện kiểm định",
        chunk="chunk-standard",
        quote="Áp kế píttông tiêu chuẩn | (0 ÷ 1600) bar | 0,05 %",
        extractor="rule:bang2.v1",
    )
    session.add(standard_extraction)
    session.flush()
    standard = ProcedureStandard(
        extraction_id=standard_extraction.id,
        procedure_id=procedure.id,
        ord=1,
        name_vi="Áp kế píttông tiêu chuẩn",
        range_text="(0 ÷ 1600) bar",
        accuracy_text="0,05 %",
    )
    session.add(standard)
    session.flush()

    device = Device(
        device_type_id=device_type.id,
        serial_no="SN-1",
        serial_norm="sn-1",
        model_code="VA-1",
        manufacturer="Acme",
        owner_org="Nhà máy X",
        needs_identification=0,
    )
    session.add(device)
    session.flush()

    record_a_extraction = _extraction(
        RECORD_STEM,
        section="Phụ lục A",
        chunk="chunk-record-a",
        quote="Số hiệu: SN-1\nNgày kiểm định: 15/01/2024\nKết luận: Đạt",
        extractor="record:docx.v1",
    )
    record_b_extraction = _extraction(
        RECORD_STEM,
        section="Phụ lục A",
        chunk="chunk-record-b",
        quote="Số hiệu: SN-1\nNgày kiểm định: 15/01/2025\nKết luận: Không đạt",
        extractor="record:docx.v1",
    )
    session.add_all([record_a_extraction, record_b_extraction])
    session.flush()
    record_a = CalibrationRecord(
        document_id=RECORD_STEM,
        extraction_id=record_a_extraction.id,
        device_id=device.id,
        procedure_id=procedure.id,
        mode="dinh_ky",
        calibrated_at=datetime(2024, 1, 15),
        expires_at=datetime(2025, 1, 15),
        expires_from_fact_id=interval_fact.id,
        verdict="dat",
        env_temp_c=20.0,
        env_humidity_pct=55.0,
        cert_no="C-1",
        lab_name="Phòng đo",
        source_text="Số hiệu: SN-1",
    )
    record_b = CalibrationRecord(
        document_id=RECORD_STEM,
        extraction_id=record_b_extraction.id,
        device_id=device.id,
        procedure_id=procedure.id,
        mode="dinh_ky",
        calibrated_at=datetime(2025, 1, 15),
        expires_at=datetime(2026, 1, 15),
        expires_from_fact_id=interval_fact.id,
        verdict="khong_dat",
        env_temp_c=22.0,
        env_humidity_pct=60.0,
        cert_no="C-2",
        lab_name="Phòng đo",
        source_text="Số hiệu: SN-1",
    )
    session.add_all([record_a, record_b])
    session.flush()
    session.add_all(
        [
            MeasurementPoint(
                record_id=record_a.id,
                ord=1,
                step_code="6.3.1",
                label="10 bar",
                nominal_value=10.0,
                measured_value=10.1,
                error_value=0.1,
                unit_id=unit_bar.id,
                limit_value=0.5,
                within_limit=1,
                quote="1 | 10 | 10,1 | 0,1 | 0,5",
                nominal_text="10",
                measured_text="10,1",
                error_text="0,1",
                limit_text="0,5",
            ),
            MeasurementPoint(
                record_id=record_b.id,
                ord=1,
                step_code="6.3.1",
                label="10 bar",
                nominal_value=10.0,
                measured_value=10.8,
                error_value=0.8,
                unit_id=unit_bar.id,
                limit_value=0.5,
                within_limit=0,
                quote="1 | 10 | 10,8 | 0,8 | 0,5",
                nominal_text="10",
                measured_text="10,8",
                error_text="0,8",
                limit_text="0,5",
            ),
        ]
    )

    # Hồ sơ CHƯA duyệt — phải luôn vắng mặt trên mọi bề mặt tra cứu (P3).
    pending_extraction = _extraction(
        RECORD_STEM,
        section="Phụ lục A",
        chunk="chunk-record-pending",
        quote="Số hiệu: SN-PENDING",
        extractor="record:docx.v1",
        status=ExtractionStatus.PENDING,
    )
    session.add(pending_extraction)
    session.flush()
    pending_device = Device(
        device_type_id=device_type.id, serial_no="SN-PENDING", serial_norm="sn-pending"
    )
    session.add(pending_device)
    session.flush()
    session.add(
        CalibrationRecord(
            document_id=RECORD_STEM,
            extraction_id=pending_extraction.id,
            device_id=pending_device.id,
            procedure_id=procedure.id,
            calibrated_at=datetime(2024, 6, 1),
            verdict="dat",
        )
    )
    session.commit()

    return {
        "quantity_id": quantity.id,
        "device_type_id": device_type.id,
        "unit_pa_id": unit_pa.id,
        "unit_bar_id": unit_bar.id,
        "procedure_id": procedure.id,
        "device_id": device.id,
        "pending_device_id": pending_device.id,
        "record_a_id": record_a.id,
        "record_b_id": record_b.id,
        "range_fact_id": range_fact.id,
        "accuracy_fact_id": accuracy_fact.id,
        "interval_fact_id": interval_fact.id,
        "standard_id": standard.id,
        "standard_extraction_id": standard_extraction.id,
        "range_extraction_id": range_extraction.id,
        "record_a_extraction_id": record_a_extraction.id,
    }


def _new_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_all_approved_views(connection)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return engine, factory


@pytest.fixture
def data_factory():
    """Trả ``(sessionmaker, ids)`` cho CSDL tra cứu đã seed — dùng cho cả route test."""
    engine, factory = _new_session()
    bootstrap = factory()
    try:
        ids = seed_dataset(bootstrap)
    finally:
        bootstrap.close()
    try:
        yield factory, ids
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def data_db(data_factory):
    """Trả ``(session, ids)`` cho một CSDL tra cứu đã seed, đã có view đã duyệt."""
    factory, ids = data_factory
    session = factory()
    try:
        yield session, ids
    finally:
        session.close()
