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
    parse_date,
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


def test_parse_date_k05_accepts_iso_year_first():
    """K05: ``YYYY-MM-DD`` phải được đọc là năm-tháng-ngày, không phải D/M/Y."""
    assert parse_date("2026-04-10") == datetime(2026, 4, 10)
    assert parse_date("Ngày kiểm định: 2026-04-10") == datetime(2026, 4, 10)


def test_parse_date_k05_keeps_vietnamese_formats():
    assert parse_date("15/01/2026") == datetime(2026, 1, 15)
    assert parse_date("5.2.2026") == datetime(2026, 2, 5)
    assert parse_date("ngày 20 tháng 3 năm 2026") == datetime(2026, 3, 20)


def test_missing_serial_flags_device(session):
    draft = _draft()
    draft.fields = [f for f in draft.fields if f.label != "Số hiệu"]
    result = store_record_draft(
        session, document=_document(session), draft=draft, procedure=_procedure(session)
    )
    session.commit()
    assert result.needs_identification is True
    assert session.get(Device, result.device_id).needs_identification == 1


def test_record_only_alias_maps_cert_no(session):
    """B6: "Số" (số biên bản) chỉ dùng khi ghi hồ sơ, không vào ``HEADER_ALIASES``."""
    draft = _draft()
    draft.fields.append(FieldDraft("Số", "012/BBKĐ-ĐLAS/2024"))
    result = store_record_draft(
        session, document=_document(session), draft=draft, procedure=_procedure(session)
    )
    session.commit()
    assert session.get(CalibrationRecord, result.record_id).cert_no == "012/BBKĐ-ĐLAS/2024"


def test_header_alias_variants_map_manufacturer_reviewer_cert(session):
    """B6: biến thể nhãn biên bản pittông ánh xạ đúng trường."""
    draft = _draft()
    draft.fields += [
        FieldDraft("Nước (hãng) sản xuất", "Budenberg"),
        FieldDraft("Người kiểm soát", "Nguyễn Văn B"),
        FieldDraft("Số biên bản", "012/BBKĐ"),
    ]
    result = store_record_draft(
        session, document=_document(session), draft=draft, procedure=_procedure(session)
    )
    session.commit()
    record = session.get(CalibrationRecord, result.record_id)
    assert record.reviewer_name == "Nguyễn Văn B"
    assert record.cert_no == "012/BBKĐ"
    assert session.get(Device, result.device_id).manufacturer == "Budenberg"


def _add_working_range_fact(session) -> int:
    """Dữ kiện phạm vi đo ĐÃ DUYỆT mang đơn vị MPa (nguồn đơn vị mặc định K09)."""
    from db.models import Quantity, Unit

    quantity = Quantity(code="pressure_test", name_vi="Áp suất", si_unit_code="Pa")
    session.add(quantity)
    session.flush()
    unit = Unit(code="MPa_test", name_vi="MPa", quantity_id=quantity.id, factor_to_si=1e6)
    session.add(unit)
    session.flush()
    extraction = Extraction(
        document_id=QTKD_STEM,
        section_path="1 Phạm vi áp dụng",
        quote="Phạm vi đo (0 đến 100) MPa",
        extractor="rule:phamvi.v1",
        extractor_version="v1",
        confidence=0.95,
        status=ExtractionStatus.APPROVED,
    )
    session.add(extraction)
    session.flush()
    session.add(
        ProcedureFact(
            extraction_id=extraction.id,
            procedure_id=_procedure(session).id,
            fact_kind="working_range",
            label="Phạm vi đo",
            value_text="(0 đến 100) MPa",
            unit_id=unit.id,
        )
    )
    session.commit()
    return unit.id


def test_point_without_unit_inherits_range_unit_only_when_allowed(session):
    unit_id = _add_working_range_fact(session)
    draft = RecordDraft(
        extractor="record:xlsx.v1",
        source_text="Số hiệu: SN-1",
        fields=[FieldDraft(label="Số hiệu", value="SN-1")],
        measurements=[
            MeasurementDraft(ord=1, measured_text="10", measured_value=10.0),
            # Bảng đã neo (ví dụ góc "2'" của bảng 2.1): không được gán MPa.
            MeasurementDraft(ord=2, measured_text="2'", measured_value=2.0, inherit_unit=False),
        ],
    )
    result = store_record_draft(
        session, document=_document(session), draft=draft, procedure=_procedure(session)
    )
    points = (
        session.query(MeasurementPoint)
        .filter(MeasurementPoint.record_id == result.record_id)
        .order_by(MeasurementPoint.ord)
        .all()
    )
    assert [point.unit_id for point in points] == [unit_id, None]


def _add_mass_and_percent_units(session) -> tuple[int, int]:
    """Thêm đơn vị khối lượng ``g`` và đơn vị tương đối ``%``; trả (g_id, percent_id)."""
    from db.models import Quantity, Unit

    mass = Quantity(code="mass_test", name_vi="Khối lượng", si_unit_code="kg")
    ratio = Quantity(code="ratio_test", name_vi="Tỉ lệ", si_unit_code="%")
    session.add_all([mass, ratio])
    session.flush()
    gram = Unit(code="g", name_vi="gam", quantity_id=mass.id, factor_to_si=0.001)
    percent = Unit(code="%", name_vi="phần trăm", quantity_id=ratio.id, factor_to_si=1.0)
    session.add_all([gram, percent])
    session.commit()
    return gram.id, percent.id


def test_measurement_error_unit_never_inherits_value_unit(session):
    """Sprint M: bảng A.4 đo theo ``g`` nhưng sai số theo ``%``; điểm không có cột
    sai số thì ``error_unit_id`` để trống, KHÔNG kế thừa đơn vị giá trị đo (P2)."""
    gram_id, percent_id = _add_mass_and_percent_units(session)
    draft = RecordDraft(
        extractor="record:xlsx.v1",
        source_text="Số hiệu: SN-1",
        fields=[FieldDraft(label="Số hiệu", value="SN-1")],
        measurements=[
            MeasurementDraft(
                ord=1,
                measured_text="100",
                measured_value=100.0,
                unit_text="g",
                error_text="0,017",
                error_value=0.017,
                error_unit_text="%",
                inherit_unit=False,
            ),
            MeasurementDraft(
                ord=2,
                measured_text="200",
                measured_value=200.0,
                unit_text="g",
                error_text="0,02",
                error_value=0.02,
                inherit_unit=False,
            ),
        ],
    )
    result = store_record_draft(
        session, document=_document(session), draft=draft, procedure=_procedure(session)
    )
    points = (
        session.query(MeasurementPoint)
        .filter(MeasurementPoint.record_id == result.record_id)
        .order_by(MeasurementPoint.ord)
        .all()
    )
    assert [point.unit_id for point in points] == [gram_id, gram_id]
    assert [point.error_unit_id for point in points] == [percent_id, None]
    # P2: giá trị sai số giữ nguyên trạng từ tài liệu.
    assert [point.error_value for point in points] == [0.017, 0.02]
