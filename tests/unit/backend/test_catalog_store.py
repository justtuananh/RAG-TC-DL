"""Ghi danh mục NAS vào sổ cái ở trạng thái ``pending`` (Pha D1).

Chạy trên SQLite in-memory với view đã duyệt dựng bằng ``db.views``; dùng chính
bốn fixture thật trong ``tests/data/nas`` để số dòng khớp bộ đọc (84, 8, 70, 39).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from catalogs.readers import read_catalog
from catalogs.store import store_catalog_draft
from db.models import Base, Document, DocumentType, Extraction, ExtractionStatus, LabStandard
from db.views import create_all_approved_views

NAS = Path(__file__).resolve().parents[2] / "data" / "nas"
FIXTURES = (
    ("bieu3_chuan_mau.xlsx", "lab_standard", 84),
    ("bieu7_kdv.docx", "inspector", 8),
    ("bieu4_danh_muc_qt.docx", "procedure_catalog", 70),
    ("bieu1_linh_vuc.docx", "capability", 39),
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
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _document(db, name: str, index: int = 0) -> Document:
    stem = name.rsplit(".", 1)[0]
    existing = db.query(Document).filter(Document.id == stem).one_or_none()
    if existing is not None:
        return existing
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
    return document


def _counts(db) -> dict[str, int]:
    views = {
        "lab_standard": "v_lab_standard",
        "inspector": "v_inspector",
        "procedure_catalog": "v_procedure_catalog",
        "capability": "v_capability",
    }
    return {
        kind: db.execute(text(f"SELECT COUNT(*) FROM {view}")).scalar_one()
        for kind, view in views.items()
    }


def _approve_all(db) -> None:
    for row in db.query(Extraction).all():
        row.status = ExtractionStatus.APPROVED
    db.commit()


def test_store_four_kinds_pending_then_visible_after_approve(session):
    for index, (name, kind, rows) in enumerate(FIXTURES):
        document = _document(session, name, index)
        summary = store_catalog_draft(session, document=document, draft=read_catalog(NAS / name))
        assert (summary["kind"], summary["rows"]) == (kind, rows)
        assert summary["extraction_id"] is not None
    session.commit()

    extraction = session.query(Extraction).filter(Extraction.id == 1).one()
    assert extraction.status == ExtractionStatus.PENDING
    assert extraction.extractor == "catalog:lab_standard.v1"
    # P3: chưa duyệt thì view không lộ dòng nào.
    assert _counts(session) == {kind: 0 for _, kind, _ in FIXTURES}

    _approve_all(session)
    assert {kind: count for _, kind, count in FIXTURES} == _counts(session)


def test_store_second_read_supersedes_previous_and_keeps_rows(session):
    document = _document(session, "bieu3_chuan_mau.xlsx")
    first = store_catalog_draft(
        session, document=document, draft=read_catalog(NAS / "bieu3_chuan_mau.xlsx")
    )
    session.commit()
    second = store_catalog_draft(
        session, document=document, draft=read_catalog(NAS / "bieu3_chuan_mau.xlsx")
    )
    session.commit()

    old = session.get(Extraction, first["extraction_id"])
    new = session.get(Extraction, second["extraction_id"])
    assert old.status == ExtractionStatus.SUPERSEDED
    assert new.status == ExtractionStatus.PENDING
    assert new.supersedes_id == old.id
    assert second["superseded"] == 1
    # Dòng cũ không bị xóa: lịch sử duyệt là dữ liệu nghiệp vụ.
    assert session.query(LabStandard).count() == 168


def test_next_due_is_derived_only_when_enough_parts(session):
    document = _document(session, "bieu3_chuan_mau.xlsx")
    store_catalog_draft(
        session, document=document, draft=read_catalog(NAS / "bieu3_chuan_mau.xlsx")
    )
    session.commit()

    explicit = session.query(LabStandard).filter(LabStandard.ord == 1).one()
    assert (explicit.last_cal_year, explicit.last_cal_month) == (2020, 9)
    assert (explicit.interval_months, explicit.next_due_year, explicit.next_due_month) == (
        60,
        2025,
        9,
    )
    assert explicit.next_due_derived == 1
    # TT 76 ghi chu kỳ "1" không rõ đơn vị: không suy ra số tháng, không có hạn.
    probe = session.query(LabStandard).filter(LabStandard.ord == 76).one()
    assert probe.interval_months is None
    assert (probe.next_due_year, probe.next_due_month, probe.next_due_derived) == (None, None, 0)


def test_store_keeps_quote_and_json_lists(session):
    document = _document(session, "bieu3_chuan_mau.xlsx")
    store_catalog_draft(
        session, document=document, draft=read_catalog(NAS / "bieu3_chuan_mau.xlsx")
    )
    session.commit()

    piston = session.query(LabStandard).filter(LabStandard.ord == 3).one()
    assert piston.quote
    assert "nt" in piston.quote
    assert piston.usage_refs == [
        ["Biểu 1/CN", "IV.2"],
        ["Biểu 1/CN", "IV.3"],
        ["Biểu 1/CN", "IV.8"],
    ]
    assert set(piston.inherited) == {"interval", "last_calibration", "usage"}
    assert piston.search_text  # bản không dấu phục vụ tra cứu


def test_empty_draft_creates_nothing(session):
    class Empty:
        kind = "inspector"
        title = None
        items: list = []
        source_text = ""
        warnings: list = []

    document = _document(session, "bieu7_kdv.docx")
    summary = store_catalog_draft(session, document=document, draft=Empty())
    assert summary["rows"] == 0 and summary["extraction_id"] is None
    assert session.query(Extraction).count() == 0


def test_unknown_kind_is_rejected(session):
    class Unknown:
        kind = "khong_biet"
        title = None
        items = [object()]
        source_text = ""
        warnings: list = []

    document = _document(session, "bieu7_kdv.docx")
    with pytest.raises(ValueError):
        store_catalog_draft(session, document=document, draft=Unknown())
