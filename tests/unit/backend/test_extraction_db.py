"""Ghi extraction vào DB, supersede khi nạp lại, và P3 view chỉ lộ dữ liệu đã duyệt."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import (
    Base,
    Document,
    DocumentType,
    Extraction,
    ExtractionStatus,
    Procedure,
    ProcedureFact,
    ProcedureStandard,
    Term,
)
from db.views import create_approved_views
from knowledge.extract import extract_and_store
from knowledge.seed_data import seed_reference_data

STEM = "QTKD_1.061_2021_ND_V2"


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_approved_views(connection)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def factory(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture
def session(factory):
    db = factory()
    seed_reference_data(db)
    db.add(
        Document(
            id=STEM,
            file_stem=STEM,
            display_name=f"{STEM}.docx",
            ext="DOCX",
            doc_type=DocumentType.QTKD,
            sha256="0" * 64,
            size_bytes=1,
        )
    )
    db.commit()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def corpus_text(repo_root):
    return (repo_root / "build" / "spike_a" / f"{STEM}.md").read_text(encoding="utf-8")


def _document(session) -> Document:
    return session.query(Document).filter(Document.id == STEM).one()


def test_extract_and_store_creates_pending_rows(session, corpus_text):
    summary = extract_and_store(session, _document(session), corpus_text)
    session.commit()

    assert summary.facts == 8
    assert summary.standards == 6
    assert summary.terms == 6
    assert summary.total == 20
    assert summary.by_fact_kind["working_range"] == 1

    assert session.query(Extraction).count() == 20
    assert session.query(ProcedureFact).count() == 8
    assert session.query(ProcedureStandard).count() == 6
    assert session.query(Term).count() == 6
    assert all(row.status == ExtractionStatus.PENDING for row in session.query(Extraction).all())


def test_extract_and_store_builds_procedure_link(session, corpus_text):
    extract_and_store(session, _document(session), corpus_text)
    session.commit()

    procedure = session.query(Procedure).one()
    assert procedure.number == "1.061"
    assert procedure.document_id == STEM
    facts = session.query(ProcedureFact).all()
    assert {fact.procedure_id for fact in facts} == {procedure.id}


def test_values_normalised_to_si_and_text_preserved(session, corpus_text):
    extract_and_store(session, _document(session), corpus_text)
    session.commit()

    facts = session.query(ProcedureFact).all()
    working_range = next(f for f in facts if f.fact_kind == "working_range")
    assert working_range.value_text == "đến 1 400 bar"
    assert working_range.value_max == pytest.approx(1400 * 100_000)
    assert working_range.unit_id is not None

    temperature = next(
        f for f in facts if f.fact_kind == "env_condition" and f.label == "Nhiệt độ môi trường"
    )
    assert temperature.value_text == "(20 ± 5) oC"
    assert temperature.value_min == pytest.approx(293.15)


def test_unknown_unit_leaves_numbers_blank_and_lowers_confidence(session, corpus_text):
    extract_and_store(session, _document(session), corpus_text)
    session.commit()

    interval = next(
        f for f in session.query(ProcedureFact).all() if f.fact_kind == "calibration_interval"
    )
    assert interval.value_text == "12 tháng"
    assert interval.value_min is None and interval.value_max is None
    assert interval.unit_id is None
    assert interval.extraction.confidence == pytest.approx(0.6)


def test_views_hide_pending_until_approved(session, corpus_text):
    extract_and_store(session, _document(session), corpus_text)
    session.commit()

    def view_count(view: str) -> int:
        return session.execute(text(f"select count(*) from {view}")).scalar_one()

    assert view_count("v_procedure_fact") == 0
    assert view_count("v_procedure_standard") == 0
    assert view_count("v_term") == 0
    assert session.query(ProcedureFact).count() == 8  # bảng gốc vẫn giữ

    approved = (
        session.query(Extraction)
        .join(ProcedureFact, ProcedureFact.extraction_id == Extraction.id)
        .first()
    )
    approved.status = ExtractionStatus.APPROVED
    session.commit()
    assert view_count("v_procedure_fact") == 1

    rejected = session.query(Extraction).filter(Extraction.id != approved.id).first()
    rejected.status = ExtractionStatus.REJECTED
    session.commit()
    assert view_count("v_procedure_fact") == 1  # rejected không lộ ra


def test_reload_supersedes_previous_not_deletes(session, corpus_text):
    first = extract_and_store(session, _document(session), corpus_text)
    session.commit()
    assert first.superseded == 0

    second = extract_and_store(session, _document(session), corpus_text)
    session.commit()

    assert second.superseded == 20
    assert session.query(Extraction).count() == 40  # giữ lịch sử, không xóa
    assert (
        session.query(Extraction).filter(Extraction.status == ExtractionStatus.SUPERSEDED).count()
        == 20
    )
    assert (
        session.query(Extraction).filter(Extraction.status == ExtractionStatus.PENDING).count()
        == 20
    )
    assert session.query(Extraction).filter(Extraction.supersedes_id.isnot(None)).count() == 20


def test_reload_removes_previously_approved_from_view(session, corpus_text):
    extract_and_store(session, _document(session), corpus_text)
    session.commit()
    for row in session.query(Extraction).all():
        row.status = ExtractionStatus.APPROVED
    session.commit()
    assert session.execute(text("select count(*) from v_procedure_fact")).scalar_one() == 8

    extract_and_store(session, _document(session), corpus_text)
    session.commit()
    # Bản đã duyệt cũ chuyển superseded → biến khỏi bề mặt; bản mới đang pending.
    assert session.execute(text("select count(*) from v_procedure_fact")).scalar_one() == 0


def test_run_extraction_from_ingestion(monkeypatch, factory, corpus_text, tmp_path):
    import ingestion_jobs

    monkeypatch.setattr(ingestion_jobs, "SessionLocal", factory)
    db = factory()
    seed_reference_data(db)
    db.add(
        Document(
            id=STEM,
            file_stem=STEM,
            display_name=f"{STEM}.docx",
            ext="DOCX",
            doc_type=DocumentType.QTKD,
            sha256="1" * 64,
            size_bytes=1,
        )
    )
    db.commit()
    db.close()

    md_path = tmp_path / f"{STEM}.md"
    md_path.write_text(corpus_text, encoding="utf-8")
    ingestion_jobs._run_extraction(STEM, md_path)

    check = factory()
    try:
        assert (
            check.query(Extraction).filter(Extraction.status == ExtractionStatus.PENDING).count()
            == 20
        )
    finally:
        check.close()
