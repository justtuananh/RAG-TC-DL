#!/usr/bin/env python
"""Seed bộ dữ liệu kiểm định tổng hợp cho thử hiệu năng/bề mặt tra cứu (Sprint 8).

Tạo N hồ sơ ĐÃ DUYỆT (``extraction`` ``approved``) cùng điểm đo, gắn một QTKĐ tổng
hợp riêng ("SYN.8") để không lẫn với dữ liệu thật. Mặc định chỉ in kế hoạch; thêm
``--apply`` mới ghi. Chạy lại sẽ gỡ đúng dữ liệu tổng hợp cũ rồi dựng lại (idempotent).

Ví dụ:
    python scripts/seed_synthetic_records.py --count 10000 --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, func, select  # noqa: E402

from db import SessionLocal  # noqa: E402
from db.models import (  # noqa: E402
    CalibrationRecord,
    Device,
    DeviceType,
    Document,
    DocumentType,
    Extraction,
    MeasurementPoint,
    Procedure,
    ProcedureFact,
    Quantity,
    Unit,
)

SYNTHETIC_DOC_ID = "SYNTHETIC_RECORDS_SPRINT8"
QTKD_DOC_ID = "SYNTHETIC_QTKD_SPRINT8"
PROCEDURE_NUMBER = "SYN.8"
DEVICE_TYPE_NAME = "Thiết bị tổng hợp (Sprint 8)"
SERIAL_PREFIX = "SYN-"


def _ensure_reference(session) -> tuple[int, int]:
    """Tạo (hoặc lấy) loại thiết bị/QTKĐ tổng hợp; trả ``(device_type_id, procedure_id)``."""
    quantity = session.execute(
        select(Quantity).where(Quantity.code == "synthetic_pressure")
    ).scalar_one_or_none()
    if quantity is None:
        quantity = Quantity(
            code="synthetic_pressure", name_vi="Áp suất (tổng hợp)", si_unit_code="Pa"
        )
        session.add(quantity)
        session.flush()
    for code, name, factor in (
        ("synthetic_pa", "Pa (tổng hợp)", 1.0),
        ("synthetic_bar", "Bar (tổng hợp)", 100000.0),
    ):
        if session.execute(select(Unit).where(Unit.code == code)).scalar_one_or_none() is None:
            session.add(
                Unit(
                    code=code,
                    name_vi=name,
                    quantity_id=quantity.id,
                    factor_to_si=factor,
                    offset_to_si=0.0,
                    aliases=[],
                )
            )
    device_type = session.execute(
        select(DeviceType).where(DeviceType.name_vi == DEVICE_TYPE_NAME)
    ).scalar_one_or_none()
    if device_type is None:
        device_type = DeviceType(name_vi=DEVICE_TYPE_NAME, aliases=[], quantity_id=quantity.id)
        session.add(device_type)
        session.flush()
    for doc_id, stem, doc_type in (
        (QTKD_DOC_ID, "QTKD_SYN.8", DocumentType.QTKD),
        (SYNTHETIC_DOC_ID, "BB_SYN.8", DocumentType.HO_SO_KIEM_DINH),
    ):
        if session.get(Document, doc_id) is None:
            session.add(
                Document(
                    id=doc_id,
                    file_stem=stem,
                    display_name=f"{stem}.docx",
                    ext="DOCX",
                    doc_type=doc_type,
                    sha256=doc_id.lower().ljust(64, "0"),
                    size_bytes=1,
                )
            )
    session.flush()
    procedure = session.execute(
        select(Procedure).where(Procedure.number == PROCEDURE_NUMBER)
    ).scalar_one_or_none()
    if procedure is None:
        procedure = Procedure(
            number=PROCEDURE_NUMBER,
            year=2026,
            title="QTKĐ tổng hợp (Sprint 8)",
            document_id=QTKD_DOC_ID,
            device_type_id=device_type.id,
        )
        session.add(procedure)
        session.flush()
    session.flush()
    return device_type.id, procedure.id


def _clear_synthetic(session, procedure_id: int) -> None:
    """Gỡ đúng dữ liệu tổng hợp của lần chạy trước (theo thứ tự khóa ngoại)."""
    record_ids = select(CalibrationRecord.id).where(
        CalibrationRecord.document_id == SYNTHETIC_DOC_ID
    )
    session.execute(delete(MeasurementPoint).where(MeasurementPoint.record_id.in_(record_ids)))
    session.execute(
        delete(CalibrationRecord).where(CalibrationRecord.document_id == SYNTHETIC_DOC_ID)
    )
    session.execute(delete(ProcedureFact).where(ProcedureFact.procedure_id == procedure_id))
    session.execute(delete(Extraction).where(Extraction.document_id == SYNTHETIC_DOC_ID))
    session.execute(delete(Extraction).where(Extraction.document_id == QTKD_DOC_ID))
    session.execute(delete(Device).where(Device.serial_norm.like("syn-%")))
    session.flush()


def _seed(session, count: int, devices: int, procedure_id: int, device_type_id: int) -> dict:
    devices = max(1, min(devices, count))
    unit_bar_id = session.execute(select(Unit.id).where(Unit.code == "synthetic_bar")).scalar_one()

    range_extraction = Extraction(
        document_id=QTKD_DOC_ID,
        section_path="1 Phạm vi áp dụng",
        chunk_id="syn-range",
        quote="Phạm vi đo (0 ÷ 1600) bar",
        extractor="rule:phamvi.v1",
        extractor_version="v1",
        confidence=0.95,
        status="approved",
    )
    accuracy_extraction = Extraction(
        document_id=QTKD_DOC_ID,
        section_path="6 Tiến hành",
        chunk_id="syn-accuracy",
        quote="Sai số cho phép ± 0,5 %",
        extractor="rule:bang2.v1",
        extractor_version="v1",
        confidence=0.9,
        status="approved",
    )
    session.add_all([range_extraction, accuracy_extraction])
    session.flush()
    session.add_all(
        [
            ProcedureFact(
                extraction_id=range_extraction.id,
                procedure_id=procedure_id,
                fact_kind="working_range",
                label="Phạm vi",
                value_min=0.0,
                value_max=160000000.0,
                value_text="(0 ÷ 1600) bar",
            ),
            ProcedureFact(
                extraction_id=accuracy_extraction.id,
                procedure_id=procedure_id,
                fact_kind="accuracy_class",
                label="Cấp chính xác",
                value_text="± 0,5 %",
            ),
        ]
    )
    session.flush()

    extraction_start = (session.execute(select(func.max(Extraction.id))).scalar() or 0) + 1
    device_start = (session.execute(select(func.max(Device.id))).scalar() or 0) + 1
    record_start = (session.execute(select(func.max(CalibrationRecord.id))).scalar() or 0) + 1
    point_start = (session.execute(select(func.max(MeasurementPoint.id))).scalar() or 0) + 1

    session.execute(
        Device.__table__.insert(),
        [
            {
                "id": device_start + index,
                "device_type_id": device_type_id,
                "serial_no": f"{SERIAL_PREFIX}{index + 1:05d}",
                "serial_norm": f"{SERIAL_PREFIX.lower()}{index + 1:05d}",
                "model_code": "MODEL-SYN",
                "manufacturer": "Nhà sản xuất tổng hợp",
                "owner_org": "Đơn vị tổng hợp",
                "attrs": {},
                "needs_identification": 0,
            }
            for index in range(devices)
        ],
    )
    session.execute(
        Extraction.__table__.insert(),
        [
            {
                "id": extraction_start + index,
                "document_id": SYNTHETIC_DOC_ID,
                "section_path": "Phụ lục A",
                "chunk_id": f"syn-rec-{index}",
                "quote": f"Số hiệu: {SERIAL_PREFIX}{index % devices + 1:05d}",
                "extractor": "record:synthetic.v1",
                "extractor_version": "v1",
                "confidence": 0.9,
                "status": "approved",
            }
            for index in range(count)
        ],
    )
    base_date = datetime(2022, 1, 1)
    session.execute(
        CalibrationRecord.__table__.insert(),
        [
            {
                "id": record_start + index,
                "document_id": SYNTHETIC_DOC_ID,
                "extraction_id": extraction_start + index,
                "device_id": device_start + (index % devices),
                "procedure_id": procedure_id,
                "mode": "dinh_ky" if index % 3 else "ban_dau",
                "calibrated_at": base_date + timedelta(days=index % 1000),
                "expires_at": base_date + timedelta(days=index % 1000 + 365),
                "verdict": "dat" if index % 4 else "khong_dat",
                "cert_no": f"SYN-C-{index:06d}",
                "env_temp_c": 20.0 + (index % 5),
                "env_humidity_pct": 50.0 + (index % 10),
                "lab_name": "Phòng tổng hợp",
            }
            for index in range(count)
        ],
    )
    session.execute(
        MeasurementPoint.__table__.insert(),
        [
            {
                "id": point_start + index,
                "record_id": record_start + index,
                "ord": 1,
                "step_code": "6.3.1",
                "label": "Mốc 10 bar",
                "nominal_value": 10.0,
                "measured_value": 10.0 + (index % 9) / 10,
                "error_value": (index % 9) / 10,
                "unit_id": unit_bar_id,
                "limit_value": 0.5,
                "within_limit": 1 if (index % 9) / 10 <= 0.5 else 0,
                "quote": "1 | 10 | 10 | 0,1 | 0,5",
                "nominal_text": "10",
                "measured_text": "10",
                "error_text": "0,1",
                "limit_text": "0,5",
            }
            for index in range(count)
        ],
    )
    session.flush()
    return {"devices": devices, "records": count, "measurements": count}


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed dữ liệu kiểm định tổng hợp (Sprint 8)")
    parser.add_argument("--count", type=int, default=10000, help="số hồ sơ")
    parser.add_argument("--devices", type=int, default=1000, help="số thiết bị")
    parser.add_argument("--apply", action="store_true", help="ghi vào CSDL (mặc định chỉ in)")
    args = parser.parse_args()

    if not args.apply:
        print(f"[dry-run] sẽ tạo {args.count} hồ sơ đã duyệt / {args.devices} thiết bị.")
        print("Thêm --apply để ghi.")
        return 0

    session = SessionLocal()
    try:
        device_type_id, procedure_id = _ensure_reference(session)
        _clear_synthetic(session, procedure_id)
        counts = _seed(session, args.count, args.devices, procedure_id, device_type_id)
        session.commit()
        print(
            "Đã seed {records} hồ sơ, {devices} thiết bị, {measurements} điểm đo "
            "(đã duyệt).".format(**counts)
        )
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
