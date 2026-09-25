"""T7: kiểm tra đọc hồ sơ calibration từ biên bản (.docx)/phiếu đo (.xlsx).

Pipeline thật trên SQLite, MỘT CSDL RIÊNG cho mỗi hồ sơ (``_load_record``, cache
theo ``manifest_id``): với QTKĐ nguồn, ``extract_appendix_and_store`` rồi duyệt
hết extraction ``appendix_field``, ``derive_mapping_config``; rồi ``read_docx``/
``read_xlsx`` theo config và ``store_record_draft``. Cô lập từng hồ sơ (không dùng
chung một CSDL như T8) để so từng trường với ``records_golden`` không bị ảnh
hưởng bởi việc gộp thiết bị giữa các hồ sơ khác — D04/D05 CỐ Ý trỏ cùng một thiết
bị (khác hoa/thường của serial); xem T8 cho hành vi gộp đó.

File mang mã K thì đúng (các) trường bị ảnh hưởng mang xfail strict; trường khác
của CÙNG file phải đạt bình thường, chứng minh lỗi chỉ cục bộ.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import (
    Base,
    CalibrationRecord,
    Device,
    Document,
    DocumentType,
    Extraction,
    ExtractionStatus,
    MeasurementPoint,
)
from db.views import create_all_approved_views
from knowledge.extract import extract_and_store, extract_appendix_and_store
from knowledge.rules.phuluc_a import extract as extract_appendix_fields
from knowledge.seed_data import seed_reference_data
from records.docx_reader import read_docx
from records.store import store_record_draft
from records.xlsx_reader import read_xlsx
from tests.unit.knowledge_corpus.conftest import (
    CORPUS_ROOT,
    PROC_SOURCE,
    _build_qtkd_config,
    load_manifest,
    xfail_for,
)

_MANIFEST = load_manifest()
_GOLD_FILE = CORPUS_ROOT / "gold" / "records_golden.jsonl"


def _load_gold() -> dict[str, dict]:
    rows = {}
    with open(_GOLD_FILE, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                rows[row["file"]] = row
    return rows


_GOLD_RECORDS = _load_gold()
_FILE_TO_ID = {obj["file"]: mid for mid, obj in _MANIFEST.items()}
_GOLD_BY_ID = {_FILE_TO_ID[file]: row for file, row in _GOLD_RECORDS.items() if file in _FILE_TO_ID}

_HEADER_FIELDS = (
    "serial",
    "model",
    "manufacturer",
    "owner",
    "certificate_no",
    "inspector",
    "reviewer",
    "lab",
    "date",
    "mode",
    "verdict",
    "temperature",
    "humidity",
)

# (manifest_id, trường) bị ảnh hưởng bởi một mã K -> mã đó (đo thật, xem
# scratchpad self-check). Mọi cặp còn lại (kể cả trường khác của CÙNG các file
# này) phải khớp gold bình thường.
_HEADER_XFAIL: dict[tuple[str, str], str] = {}

# File mà TOÀN BỘ danh sách điểm đo bị ảnh hưởng bởi một mã K.
_POINTS_XFAIL: dict[str, str] = {}


def _actual_field(record: CalibrationRecord, device: Device | None, field: str):
    if field == "serial":
        return device.serial_no if device else None
    if field == "model":
        return device.model_code if device else None
    if field == "manufacturer":
        return device.manufacturer if device else None
    if field == "owner":
        return device.owner_org if device else None
    if field == "certificate_no":
        return record.cert_no
    if field == "inspector":
        return record.inspector_name
    if field == "reviewer":
        return record.reviewer_name
    if field == "lab":
        return record.lab_name
    if field == "date":
        return record.calibrated_at.date().isoformat() if record.calibrated_at else None
    if field == "mode":
        return record.mode
    if field == "verdict":
        return record.verdict
    if field == "temperature":
        return record.env_temp_c
    if field == "humidity":
        return record.env_humidity_pct
    raise AssertionError(f"Trường không xác định: {field}")  # pragma: no cover


def _point_as_dict(point: MeasurementPoint) -> dict:
    return {
        "ordinal": point.ord,
        "nominal": point.nominal_value,
        "measured": point.measured_value,
        "error": point.error_value,
        "limit": point.limit_value,
        "note": point.note or "",
    }


_RECORD_CACHE: dict[str, dict] = {}


def _fresh_session():
    """Dựng engine + session SQLite in-memory RIÊNG, đã seed dữ liệu tham chiếu."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_all_approved_views(connection)
    session = sessionmaker(bind=engine)()
    seed_reference_data(session)
    return engine, session


def _store_one_record(session, corpus_manifest, corpus_file_paths, manifest_id, procedure, config):
    """Đọc file D/E theo ``config`` rồi ghi qua ``store_record_draft``; trả kết quả."""
    obj = corpus_manifest[manifest_id]
    file_path = corpus_file_paths[obj["file"]]
    reader = read_docx if file_path.suffix.lower() == ".docx" else read_xlsx
    draft = reader(file_path, config)

    doc_type = DocumentType.HO_SO_KIEM_DINH if obj["group"] == "D" else DocumentType.PHIEU_DO
    document = Document(
        id=manifest_id,
        file_stem=manifest_id,
        display_name=obj["file"],
        ext=file_path.suffix.lstrip(".").upper(),
        doc_type=doc_type,
        sha256=hashlib.sha256(manifest_id.encode()).hexdigest(),
        size_bytes=1,
    )
    session.add(document)
    session.flush()
    return store_record_draft(session, document=document, draft=draft, procedure=procedure)


def _load_record(manifest_id: str, corpus_manifest, corpus_markdown, corpus_file_paths) -> dict:
    """Đọc + ghi MỘT hồ sơ D/E trên một CSDL SQLite in-memory RIÊNG; cache theo id.

    Cô lập tránh việc gộp thiết bị giữa các hồ sơ khác nhau làm lệch giá trị
    ``serial``/``model``/... của MỘT hồ sơ cụ thể (đó là hành vi ĐÚNG của
    ``find_or_create_device`` khi hai hồ sơ trỏ cùng thiết bị — T8 kiểm việc đó).
    """
    if manifest_id in _RECORD_CACHE:
        return _RECORD_CACHE[manifest_id]

    engine, session = _fresh_session()
    obj = corpus_manifest[manifest_id]
    source_id = PROC_SOURCE[obj["procedure_number"]]
    procedure, config = _build_qtkd_config(session, corpus_manifest, corpus_markdown, source_id)
    session.commit()

    result = _store_one_record(
        session, corpus_manifest, corpus_file_paths, manifest_id, procedure, config
    )
    session.commit()

    record = session.get(CalibrationRecord, result.record_id)
    device = session.get(Device, result.device_id) if result.device_id else None
    points = (
        session.query(MeasurementPoint)
        .filter(MeasurementPoint.record_id == result.record_id)
        .order_by(MeasurementPoint.ord)
        .all()
    )
    data = {
        "fields": {field: _actual_field(record, device, field) for field in _HEADER_FIELDS},
        "points": [_point_as_dict(point) for point in points],
    }
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()
    _RECORD_CACHE[manifest_id] = data
    return data


def _header_params():
    params = []
    for manifest_id in sorted(_GOLD_BY_ID):
        for field in _HEADER_FIELDS:
            code = _HEADER_XFAIL.get((manifest_id, field))
            marks = [xfail_for(_MANIFEST, code, manifest_id=manifest_id)] if code else []
            params.append(
                pytest.param(manifest_id, field, marks=marks, id=f"{manifest_id}-{field}")
            )
    return params


@pytest.mark.parametrize("manifest_id,field", _header_params())
def test_record_header_field_matches_gold(
    manifest_id, field, corpus_manifest, corpus_markdown, corpus_file_paths
):
    """Từng trường đầu mục của từng hồ sơ D/E khớp ``records_golden``."""
    data = _load_record(manifest_id, corpus_manifest, corpus_markdown, corpus_file_paths)
    expected = _GOLD_BY_ID[manifest_id]["fields"][field]
    actual = data["fields"][field]
    assert actual == expected, f"{manifest_id}.{field}: {actual!r} (kỳ vọng {expected!r})"


def _points_params():
    params = []
    for manifest_id in sorted(_GOLD_BY_ID):
        code = _POINTS_XFAIL.get(manifest_id)
        marks = [xfail_for(_MANIFEST, code, manifest_id=manifest_id)] if code else []
        params.append(pytest.param(manifest_id, marks=marks, id=manifest_id))
    return params


@pytest.mark.parametrize("manifest_id", _points_params())
def test_record_points_match_gold(manifest_id, corpus_manifest, corpus_markdown, corpus_file_paths):
    """Toàn bộ danh sách điểm đo (thứ tự, danh nghĩa, đo, sai số, giới hạn, ghi
    chú) của một hồ sơ khớp ``records_golden``."""
    data = _load_record(manifest_id, corpus_manifest, corpus_markdown, corpus_file_paths)
    expected = [
        {
            "ordinal": item["ordinal"],
            "nominal": item["nominal"],
            "measured": item["measured"],
            "error": item["error"],
            "limit": item["limit"],
            "note": item["note"],
        }
        for item in _GOLD_BY_ID[manifest_id]["points"]
    ]
    assert data["points"] == expected


def test_record_points_have_unit_id(corpus_manifest, corpus_markdown, corpus_file_paths):
    """K09: mọi điểm đo phải có ``unit_id`` đúng đơn vị của QTKĐ (áp dụng mọi hồ
    sơ D/E). Dùng D01 (hồ sơ chuẩn, không chạm mã K nào khác) làm đại diện: tiêu
    đề cột không ghi đơn vị nên lấy đơn vị từ dữ kiện ``working_range`` đã duyệt."""
    engine, session = _fresh_session()
    obj = corpus_manifest["D01"]
    source_id = PROC_SOURCE[obj["procedure_number"]]
    procedure, config = _build_qtkd_config(session, corpus_manifest, corpus_markdown, source_id)
    # Cấp dữ kiện working_range đã duyệt cho QTKĐ nguồn (đơn vị mặc định K09).
    source_doc = session.get(Document, source_id)
    extract_and_store(
        session, source_doc, corpus_markdown[source_id], procedure=procedure, supersede=False
    )
    session.flush()
    for extraction in session.query(Extraction).filter(Extraction.document_id == source_id).all():
        extraction.status = ExtractionStatus.APPROVED
    session.commit()

    result = _store_one_record(
        session, corpus_manifest, corpus_file_paths, "D01", procedure, config
    )
    session.commit()

    points = (
        session.query(MeasurementPoint).filter(MeasurementPoint.record_id == result.record_id).all()
    )
    assert points
    assert all(point.unit_id is not None for point in points), "unit_id luôn None (K09 chưa sửa)"
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_appendix_extraction_b02_heading_style_paragraph(session, corpus_markdown):
    """K12: đoạn "(Quy định)" trong Phụ lục A của B02 bị gán style heading; thân
    mục Phụ lục A phải kéo dài qua heading con đó tới hết tài liệu (hoặc "Phụ lục"
    kế tiếp), nên ``extract_appendix_and_store`` trích được >= 12 trường đầu mục."""
    document = Document(
        id="B02",
        file_stem="B02",
        display_name=_MANIFEST["B02"]["file"],
        ext="DOCX",
        doc_type=DocumentType.QTKD,
        sha256=hashlib.sha256(b"B02").hexdigest(),
        size_bytes=1,
    )
    session.add(document)
    session.flush()
    summary = extract_appendix_and_store(session, document, corpus_markdown["B02"])
    session.commit()
    assert summary.facts >= 12, f"Chỉ trích được {summary.facts} trường (K12 chưa sửa)"


def test_appendix_date_field_missing_colon_recognized():
    """K06: dòng Phụ lục A "Ngày kiểm định tháng năm 2026" (không có ':', nguyên
    văn lấy từ D14) phải được ``phuluc_a`` nhận diện là trường đầu mục."""
    md = "# Phụ lục A\nNgày kiểm định tháng năm 2026\n"
    hits = extract_appendix_fields(md)
    labels = [hit.label for hit in hits]
    assert "Ngày kiểm định" in labels, f"Không nhận diện được trường ngày (K06): {labels}"


def test_e05_multi_sheet_only_first_sheet_read(corpus_manifest, corpus_markdown, corpus_file_paths):
    """E05 (phiếu đo nhiều sheet): chỉ dữ liệu sheet đầu được đọc — số liệu đo
    khớp gold (vốn chỉ tính từ sheet đầu); giá trị riêng của sheet 2 không lọt vào."""
    data = _load_record("E05", corpus_manifest, corpus_markdown, corpus_file_paths)
    expected = _GOLD_BY_ID["E05"]["points"]
    assert len(data["points"]) == len(expected)
    for point, item in zip(data["points"], expected, strict=True):
        assert point["measured"] == item["measured"]
        assert point["error"] == item["error"]
