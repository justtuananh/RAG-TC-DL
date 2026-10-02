"""Hàng đợi duyệt hiển thị extraction danh mục NAS (Pha D1).

Một extraction ``catalog:*`` mang nhiều dòng: hàng đợi phải cho biết loại, số dòng
và vài dòng mẫu, và duyệt/từ chối/duyệt hàng loạt theo ``extractor`` như hiện có.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from catalogs.readers import read_catalog
from catalogs.store import store_catalog_draft
from db.models import Base, Document, DocumentType
from db.views import create_all_approved_views
from review import queue as review

NAS = Path(__file__).resolve().parents[2] / "data" / "nas"


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
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _store_inspectors(db) -> int:
    document = Document(
        id="bieu7_kdv",
        file_stem="bieu7_kdv",
        display_name="bieu7_kdv.docx",
        ext="DOCX",
        doc_type=DocumentType.DANH_MUC,
        sha256="0" * 64,
        size_bytes=1,
    )
    db.add(document)
    db.flush()
    summary = store_catalog_draft(db, document=document, draft=read_catalog(NAS / "bieu7_kdv.docx"))
    db.commit()
    return summary["extraction_id"]


def test_queue_serializes_catalog_summary(session):
    extraction_id = _store_inspectors(session)
    items, total = review.list_queue(session)
    assert total == 1
    item = items[0]
    assert item["id"] == extraction_id
    assert item["kind"] == "catalog"
    assert item["data"]["catalog_kind"] == "inspector"
    assert item["data"]["catalog_label"] == "Danh sách kiểm định viên"
    assert item["data"]["row_count"] == 8
    assert len(item["data"]["sample"]) == 5
    assert item["data"]["sample"][0]["name"]
    # P1: nguyên văn cả tài liệu được giữ ở quote của extraction.
    assert item["quote"]
    assert item["extractor"] == "catalog:inspector.v1"


def test_queue_details_exposes_label_for_each_kind(session):
    for name, _ in (
        ("bieu3_chuan_mau.xlsx", 84),
        ("bieu4_danh_muc_qt.docx", 70),
        ("bieu1_linh_vuc.docx", 39),
    ):
        stem = name.rsplit(".", 1)[0]
        document = Document(
            id=stem,
            file_stem=stem,
            display_name=name,
            ext=name.rsplit(".", 1)[1].upper(),
            doc_type=DocumentType.DANH_MUC,
            sha256=stem[0] * 64,
            size_bytes=1,
        )
        session.add(document)
        session.flush()
        store_catalog_draft(session, document=document, draft=read_catalog(NAS / name))
        session.commit()

    items, total = review.list_queue(session, limit=10)
    assert total == 3
    counts = {item["data"]["catalog_kind"]: item["data"]["row_count"] for item in items}
    assert counts == {"lab_standard": 84, "procedure_catalog": 70, "capability": 39}


def test_approve_catalog_reveals_rows_in_view(session):
    extraction_id = _store_inspectors(session)
    assert session.execute(text("SELECT COUNT(*) FROM v_inspector")).scalar_one() == 0

    review.approve(session, extraction_id, None)
    assert session.execute(text("SELECT COUNT(*) FROM v_inspector")).scalar_one() == 8


def test_bulk_approve_by_extractor(session):
    extraction_id = _store_inspectors(session)
    result = review.bulk_approve(session, None, extractor="catalog:inspector.v1")
    assert result["approved_count"] == 1
    assert result["ids"] == [extraction_id]
    assert session.execute(text("SELECT COUNT(*) FROM v_inspector")).scalar_one() == 8


def test_reject_catalog_keeps_rows_hidden(session):
    extraction_id = _store_inspectors(session)
    result = review.reject(session, extraction_id, None, "trùng hồ sơ cũ")
    assert result["status"] == "rejected"
    assert session.execute(text("SELECT COUNT(*) FROM v_inspector")).scalar_one() == 0


def test_catalog_is_not_editable_field_by_field(session):
    extraction_id = _store_inspectors(session)
    with pytest.raises(review.ValidationError):
        review.edit_and_approve(session, extraction_id, None, {"name": "Sai"})
