"""Resolver bốn intent danh mục NAS (Pha D2) trên SQLite + fixture thật.

Dựng sổ cái từ ``tests/data/nas`` bằng ``read_catalog`` + ``store_catalog_draft``
rồi duyệt, để kiểm: lọc không dấu, khớp một phần tên nhóm, lĩnh vực KĐV là chuỗi
con, mọi ô số có xuất xứ (P1), và dữ liệu chưa duyệt không lộ (P3).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from catalogs.readers import read_catalog
from catalogs.store import store_catalog_draft
from db.models import Base, Document, DocumentType, Extraction, ExtractionStatus
from db.views import create_all_approved_views
from query import intents, router

NAS = Path(__file__).resolve().parents[2] / "data" / "nas"
FIXTURES = (
    ("bieu3_chuan_mau.xlsx", "lab_standard"),
    ("bieu7_kdv.docx", "inspector"),
    ("bieu4_danh_muc_qt.docx", "procedure_catalog"),
    ("bieu1_linh_vuc.docx", "capability"),
)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_all_approved_views(connection)
    factory = sessionmaker(bind=engine, autoflush=False)
    db = factory()
    for index, (name, _kind) in enumerate(FIXTURES):
        stem = name.rsplit(".", 1)[0]
        document = Document(
            id=stem,
            file_stem=stem,
            display_name=name,
            ext=name.rsplit(".", 1)[1].upper(),
            doc_type=DocumentType.DANH_MUC,
            sha256=str(index) * 64,
            size_bytes=1,
        )
        db.add(document)
        db.flush()
        store_catalog_draft(db, document=document, draft=read_catalog(NAS / name))
    db.commit()
    for row in db.query(Extraction).all():
        row.status = ExtractionStatus.APPROVED
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _payload(session, payload: dict):
    request = intents.parse_intent(payload)
    assert request is not None, payload
    result = router.build_data_payload(session, request)
    assert router.untraceable_cells(result) == []
    return result


def test_lab_standard_by_serial_has_cycle_and_last_cal(session):
    result = _payload(session, {"intent": "lab_standard_lookup", "params": {"query": "5393"}})
    assert not result.empty
    assert len(result.tables[0].rows) == 1
    row = result.tables[0].rows[0]
    assert row["model"].text == "MΠ-6"
    assert row["interval_text"].text == "1 năm"
    assert row["last_cal_text"].text == "6/2021 TTĐL"
    assert row["next_due_text"].text == "06/2022 (ước tính)"
    assert result.citations and result.citations[0]["quote"]


def test_lab_standard_by_usage_ref(session):
    result = _payload(session, {"intent": "lab_standard_lookup", "params": {"usage_ref": "IV.1"}})
    assert not result.empty
    serials = {row["serial"].text for row in result.tables[0].rows}
    assert "1274" in serials  # Fluke 7302 dùng IV.1


def test_inspector_by_field_matches_substring_without_diacritics(session):
    result = _payload(session, {"intent": "inspector_lookup", "params": {"field": "nhiệt độ"}})
    names = [row["name"].text for row in result.tables[0].rows]
    assert names == [
        "Nguyễn Đăng Vinh",
        "Luyện Thanh Tùng",
        "Nguyễn Lê Hạnh",
        "Vũ Đức Tuấn",
    ]
    assert "Nguyễn Hoàng Lam" not in names


def test_inspector_by_name_returns_card(session):
    result = _payload(session, {"intent": "inspector_lookup", "params": {"name": "Phạm Văn Hà"}})
    assert len(result.tables[0].rows) == 1
    assert result.tables[0].rows[0]["card_no"].text == "043/A1"


def test_procedure_catalog_by_code(session):
    result = _payload(
        session,
        {"intent": "procedure_catalog_lookup", "params": {"code": "QTKĐ 1.019 : 2014"}},
    )
    assert len(result.tables[0].rows) == 1
    row = result.tables[0].rows[0]
    assert row["issuer"].text == "Cục TC - ĐL - CL"
    assert row["year_issued"].text == "2015"
    assert "Áp kế píttông" in row["title"].text


def test_procedure_catalog_by_partial_group_title(session):
    result = _payload(
        session,
        {"intent": "procedure_catalog_lookup", "params": {"group": "dung tích, lưu lượng"}},
    )
    assert len(result.tables[0].rows) == 12
    groups = {row["group_title"].text for row in result.tables[0].rows}
    assert groups == {"Lĩnh vực dung tích, lưu lượng"}


def test_procedure_catalog_by_device_keyword(session):
    result = _payload(
        session,
        {
            "intent": "procedure_catalog_lookup",
            "params": {"keyword": "nhiệt kế thủy tinh chất lỏng"},
        },
    )
    codes = {row["code_text"].text for row in result.tables[0].rows}
    assert codes == {"ĐLVN 20 : 2017", "QTKĐ 1.106 : 2018"}


def test_capability_by_keyword_counts_inspectors(session):
    result = _payload(
        session, {"intent": "capability_lookup", "params": {"keyword": "van an toàn"}}
    )
    assert len(result.tables[0].rows) == 1
    row = result.tables[0].rows[0]
    assert row["inspector_count"].text == "3"
    assert "QTKĐ 1.023:2021" in row["procedure_codes"].text


def test_empty_result_is_clear_not_error(session):
    result = _payload(
        session, {"intent": "capability_lookup", "params": {"keyword": "không tồn tại xyz"}}
    )
    assert result.empty and result.tables == []
    assert "Không tìm thấy" in result.note


def test_pending_catalog_hidden_until_approved():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_all_approved_views(connection)
    factory = sessionmaker(bind=engine, autoflush=False)
    db = factory()
    try:
        document = Document(
            id="bieu7",
            file_stem="bieu7",
            display_name="bieu7_kdv.docx",
            ext="DOCX",
            doc_type=DocumentType.DANH_MUC,
            sha256="f" * 64,
            size_bytes=1,
        )
        db.add(document)
        db.flush()
        store_catalog_draft(db, document=document, draft=read_catalog(NAS / "bieu7_kdv.docx"))
        db.commit()
        # P3: extraction còn pending → resolver không thấy gì.
        result = _payload(session=db, payload={"intent": "inspector_lookup", "params": {}})
        assert result.empty
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
