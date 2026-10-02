"""Hiệu năng bảng tra cứu với 10 nghìn hồ sơ dựng giả (spec §9 S8).

Cổng: bảng lọc phải trả trong dưới 500 mili giây với 10 nghìn hồ sơ. Dữ liệu dựng
thẳng bằng SQLAlchemy Core (executemany) để việc seed không chi phối phép đo.
"""

from __future__ import annotations

import os
import time
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base
from db.views import create_all_approved_views
from query import records as qr

N = int(os.environ.get("SPRINT8_PERF_N", "10000"))
DEVICES = max(1, N // 10)
QTKD_STEM = "QTKD_PERF"
RECORD_STEM = "BB_PERF"
TARGET_SECONDS = 0.5


def _seed(engine) -> None:
    tables = Base.metadata.tables
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_all_approved_views(connection)
        connection.execute(
            tables["quantity"].insert(),
            [{"id": 1, "code": "pressure", "name_vi": "Áp suất", "si_unit_code": "Pa"}],
        )
        connection.execute(
            tables["unit"].insert(),
            [
                {
                    "id": 1,
                    "code": "Pa",
                    "name_vi": "Pascal",
                    "quantity_id": 1,
                    "factor_to_si": 1.0,
                    "offset_to_si": 0.0,
                    "aliases": [],
                },
                {
                    "id": 2,
                    "code": "bar",
                    "name_vi": "Bar",
                    "quantity_id": 1,
                    "factor_to_si": 100000.0,
                    "offset_to_si": 0.0,
                    "aliases": [],
                },
            ],
        )
        connection.execute(
            tables["device_type"].insert(),
            [{"id": 1, "name_vi": "Van an toàn", "aliases": [], "quantity_id": 1}],
        )
        connection.execute(
            tables["document"].insert(),
            [
                {
                    "id": QTKD_STEM,
                    "file_stem": QTKD_STEM,
                    "display_name": "QTKD_PERF.docx",
                    "ext": "DOCX",
                    "doc_type": "qtkd",
                    "sha256": "0" * 64,
                    "size_bytes": 1,
                },
                {
                    "id": RECORD_STEM,
                    "file_stem": RECORD_STEM,
                    "display_name": "BB_PERF.docx",
                    "ext": "DOCX",
                    "doc_type": "ho_so_kiem_dinh",
                    "sha256": "1" * 64,
                    "size_bytes": 1,
                },
            ],
        )
        connection.execute(
            tables["procedure"].insert(),
            [
                {
                    "id": 1,
                    "document_id": QTKD_STEM,
                    "number": "1.061",
                    "year": 2021,
                    "title": "Van an toàn",
                    "device_type_id": 1,
                }
            ],
        )
        # Một dữ kiện phạm vi + cấp chính xác đã duyệt cho QTKĐ.
        connection.execute(
            tables["extraction"].insert(),
            [
                {
                    "id": 1,
                    "document_id": QTKD_STEM,
                    "section_path": "1 Phạm vi",
                    "chunk_id": "c-range",
                    "quote": "(0 ÷ 1600) bar",
                    "extractor": "rule:phamvi.v1",
                    "extractor_version": "v1",
                    "confidence": 0.95,
                    "status": "approved",
                },
                {
                    "id": 2,
                    "document_id": QTKD_STEM,
                    "section_path": "6 Tiến hành",
                    "chunk_id": "c-acc",
                    "quote": "± 0,5 %",
                    "extractor": "rule:bang2.v1",
                    "extractor_version": "v1",
                    "confidence": 0.9,
                    "status": "approved",
                },
            ],
        )
        connection.execute(
            tables["procedure_fact"].insert(),
            [
                {
                    "id": 1,
                    "extraction_id": 1,
                    "procedure_id": 1,
                    "fact_kind": "working_range",
                    "label": "Phạm vi",
                    "value_min": 0.0,
                    "value_max": 160000000.0,
                    "unit_id": 1,
                    "value_text": "(0 ÷ 1600) bar",
                },
                {
                    "id": 2,
                    "extraction_id": 2,
                    "procedure_id": 1,
                    "fact_kind": "accuracy_class",
                    "label": "Cấp chính xác",
                    "value_min": None,
                    "value_max": None,
                    "unit_id": None,
                    "value_text": "± 0,5 %",
                },
            ],
        )
        connection.execute(
            tables["device"].insert(),
            [
                {
                    "id": i + 1,
                    "device_type_id": 1,
                    "serial_no": f"SN-{i + 1:05d}",
                    "serial_norm": f"sn-{i + 1:05d}",
                    "model_code": "VA-1",
                    "manufacturer": "Acme",
                    "owner_org": "X",
                    "attrs": {},
                    "needs_identification": 0,
                }
                for i in range(DEVICES)
            ],
        )
        base = 100  # chừa id thấp cho dữ kiện QTKĐ
        connection.execute(
            tables["extraction"].insert(),
            [
                {
                    "id": base + index,
                    "document_id": RECORD_STEM,
                    "section_path": "Phụ lục A",
                    "chunk_id": f"rec-{index}",
                    "quote": f"Số hiệu: SN-{index % DEVICES + 1:05d}",
                    "extractor": "record:docx.v1",
                    "extractor_version": "v1",
                    "confidence": 0.9,
                    "status": "approved",
                }
                for index in range(N)
            ],
        )
        connection.execute(
            tables["calibration_record"].insert(),
            [
                {
                    "id": base + index,
                    "document_id": RECORD_STEM,
                    "extraction_id": base + index,
                    "device_id": index % DEVICES + 1,
                    "procedure_id": 1,
                    "mode": "dinh_ky",
                    "calibrated_at": datetime(2024, 1, 1 + (index % 27)),
                    "expires_at": datetime(2025, 1, 1 + (index % 27)),
                    "verdict": "dat" if index % 4 else "khong_dat",
                    "cert_no": f"C-{index}",
                    "env_temp_c": 20.0 + (index % 5),
                    "env_humidity_pct": 50.0 + (index % 10),
                }
                for index in range(N)
            ],
        )
        connection.execute(
            tables["measurement_point"].insert(),
            [
                {
                    "id": base + index,
                    "record_id": base + index,
                    "ord": 1,
                    "step_code": "6.3.1",
                    "label": "10 bar",
                    "nominal_value": 10.0,
                    "measured_value": 10.0 + (index % 9) / 10,
                    "error_value": (index % 9) / 10,
                    "unit_id": 2,
                    "limit_value": 0.5,
                    "within_limit": 1 if (index % 9) / 10 <= 0.5 else 0,
                    "quote": "row",
                    "nominal_text": "10",
                    "measured_text": "10",
                    "error_text": "0,1",
                    "limit_text": "0,5",
                }
                for index in range(N)
            ],
        )


@pytest.fixture
def perf_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    _seed(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _best_of(action, runs: int = 5) -> float:
    best = float("inf")
    for _ in range(runs):
        start = time.perf_counter()
        action()
        best = min(best, time.perf_counter() - start)
    return best


def test_list_records_10k_under_500ms(perf_session):
    items, total = qr.list_records(perf_session, limit=50)
    assert total == N
    assert len(items) == 50
    elapsed = _best_of(lambda: qr.list_records(perf_session, limit=50))
    assert elapsed < TARGET_SECONDS, f"list_records 10k mất {elapsed * 1000:.0f}ms"


def test_filtered_list_10k_under_500ms(perf_session):
    elapsed = _best_of(
        lambda: qr.list_records(
            perf_session, verdict="dat", date_from="2024-01-01", date_to="2024-12-31", limit=50
        )
    )
    assert elapsed < TARGET_SECONDS, f"list_records lọc mất {elapsed * 1000:.0f}ms"


def test_range_filter_10k_under_500ms(perf_session):
    elapsed = _best_of(
        lambda: qr.list_records(
            perf_session, range_min=0, range_max=100, range_unit="bar", limit=50
        )
    )
    assert elapsed < TARGET_SECONDS, f"list_records lọc phạm vi mất {elapsed * 1000:.0f}ms"


def test_device_history_10k_under_500ms(perf_session):
    elapsed = _best_of(lambda: qr.device_history(perf_session, device_id=1))
    assert elapsed < TARGET_SECONDS, f"device_history mất {elapsed * 1000:.0f}ms"
