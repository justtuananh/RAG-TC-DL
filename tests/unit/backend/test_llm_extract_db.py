"""Ghi extraction §6 bằng LLM ở trạng thái ``pending``; P3 view che tới khi duyệt;
supersede tách khỏi dòng luật; nối vào ``ingestion_jobs`` (spec §5.3, §5.7, §9 S5)."""

from __future__ import annotations

import json

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
)
from db.views import create_approved_views
from knowledge import llm_extract
from knowledge.extract import extract_and_store, extract_section6_and_store
from knowledge.seed_data import seed_reference_data

STEM = "QTKD_1.061_2021_ND_V2"


class ScriptedClient:
    model_name = "scripted"

    def __init__(self, payload):
        self.payload = payload

    def chat(self, prompt, system=None):
        return json.dumps(self.payload, ensure_ascii=False)


def _payload() -> dict:
    return {
        "facts": [
            {
                "fact_kind": "max_permissible_error",
                "label": "Sai số áp suất chỉnh đặt",
                "rel_op": "±",
                "value_text": "3%",
                "limit": {"value": 3.0, "unit": "%", "quote": "± 3% áp suất chỉnh đặt của van"},
                "floor": {"value": 0.15, "unit": "bar", "quote": "không nhỏ hơn ± 0,15 bar"},
                "condition_text": "không nhỏ hơn ± 0,15 bar",
                "quote": (
                    "Giá trị cho phép của sai số áp suất chỉnh đặt bằng ± 3% áp suất "
                    "chỉnh đặt của van nhưng không nhỏ hơn ± 0,15 bar."
                ),
            },
            {
                "fact_kind": "formula",
                "label": "Sai số",
                "formula": "\\DeltaP_{cd} = P_{m} - P_{cd}",
                "quote": "$\\DeltaP_{cd} = P_{m} - P_{cd}$",
            },
        ]
    }


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


def _llm_facts(session) -> list[ProcedureFact]:
    return (
        session.query(ProcedureFact)
        .join(Extraction, Extraction.id == ProcedureFact.extraction_id)
        .filter(Extraction.extractor.like("llm:%"))
        .all()
    )


def test_section6_store_creates_pending_rows(session, corpus_text):
    summary = extract_section6_and_store(
        session, _document(session), corpus_text, client=ScriptedClient(_payload())
    )
    session.commit()

    assert summary.facts == 3  # limit + floor + formula
    assert summary.by_fact_kind["max_permissible_error"] == 2
    assert summary.by_fact_kind["formula"] == 1

    llm_rows = _llm_facts(session)
    assert len(llm_rows) == 3
    assert all(row.extraction.status == ExtractionStatus.PENDING for row in llm_rows)
    assert all(row.extraction.extractor == "llm:scripted" for row in llm_rows)


def test_section6_values_normalised_and_text_preserved(session, corpus_text):
    extract_section6_and_store(
        session, _document(session), corpus_text, client=ScriptedClient(_payload())
    )
    session.commit()

    rows = _llm_facts(session)
    floor = next(row for row in rows if row.value_text == "không nhỏ hơn ± 0,15 bar")
    assert floor.value_min == pytest.approx(0.15 * 100_000)
    assert floor.unit_id is not None

    limit = next(
        row for row in rows if row.fact_kind == "max_permissible_error" and row.value_text == "3%"
    )
    # "%" chưa seed → để trống số, giữ nguyên văn, không đoán đơn vị.
    assert limit.value_min is None and limit.value_max is None
    assert limit.unit_id is None


def test_section6_views_hide_pending_until_approved(session, corpus_text):
    extract_section6_and_store(
        session, _document(session), corpus_text, client=ScriptedClient(_payload())
    )
    session.commit()

    def view_count() -> int:
        return session.execute(text("select count(*) from v_procedure_fact")).scalar_one()

    assert view_count() == 0  # P3: chưa duyệt thì không lộ
    assert session.query(ProcedureFact).count() == 3

    for row in _llm_facts(session):
        row.extraction.status = ExtractionStatus.APPROVED
    session.commit()
    assert view_count() == 3


def test_section6_supersede_is_scoped_to_llm_rows(session, corpus_text):
    extract_and_store(session, _document(session), corpus_text)
    session.commit()
    rule_pending = (
        session.query(Extraction).filter(Extraction.status == ExtractionStatus.PENDING).count()
    )

    first = extract_section6_and_store(
        session, _document(session), corpus_text, client=ScriptedClient(_payload())
    )
    session.commit()
    assert first.superseded == 0
    # Dòng luật vẫn pending — §6 không vô hiệu hóa chúng.
    assert (
        session.query(Extraction).filter(Extraction.status == ExtractionStatus.PENDING).count()
        == rule_pending + 2
    )

    second = extract_section6_and_store(
        session, _document(session), corpus_text, client=ScriptedClient(_payload())
    )
    session.commit()
    assert second.superseded == 2  # chỉ 2 extraction llm: cũ bị superseded
    assert (
        session.query(Extraction).filter(Extraction.status == ExtractionStatus.SUPERSEDED).count()
        == 2
    )
    assert (
        session.query(Extraction).filter(Extraction.status == ExtractionStatus.PENDING).count()
        == rule_pending + 2
    )


def test_llm_unavailable_writes_nothing(session, corpus_text):
    class _Down:
        model_name = "down"

        def chat(self, prompt, system=None):
            return None

    summary = extract_section6_and_store(session, _document(session), corpus_text, client=_Down())
    session.commit()
    assert summary.facts == 0
    assert _llm_facts(session) == []


def test_run_extraction_integration_with_llm_enabled(monkeypatch, factory, corpus_text, tmp_path):
    import ingestion_jobs

    monkeypatch.setattr(ingestion_jobs, "SessionLocal", factory)
    monkeypatch.setenv("SECTION6_LLM_ENABLED", "1")
    monkeypatch.setattr(llm_extract, "default_client", lambda: ScriptedClient(_payload()))

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
        pending = (
            check.query(Extraction).filter(Extraction.status == ExtractionStatus.PENDING).count()
        )
        assert pending == 20 + 2  # 20 dòng luật + 2 extraction §6
        assert check.query(Procedure).count() == 1
        assert (
            check.query(ProcedureFact)
            .join(Extraction, Extraction.id == ProcedureFact.extraction_id)
            .filter(Extraction.extractor.like("llm:%"))
            .count()
            == 3
        )
    finally:
        check.close()


def test_run_extraction_skips_llm_when_disabled(monkeypatch, factory, corpus_text, tmp_path):
    import ingestion_jobs

    monkeypatch.setattr(ingestion_jobs, "SessionLocal", factory)
    monkeypatch.delenv("SECTION6_LLM_ENABLED", raising=False)

    def _fail():
        raise AssertionError("default_client không được gọi khi LLM tắt")

    monkeypatch.setattr(llm_extract, "default_client", _fail)

    db = factory()
    seed_reference_data(db)
    db.add(
        Document(
            id=STEM,
            file_stem=STEM,
            display_name=f"{STEM}.docx",
            ext="DOCX",
            doc_type=DocumentType.QTKD,
            sha256="2" * 64,
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
        assert check.query(Extraction).filter(Extraction.extractor.like("llm:%")).count() == 0
    finally:
        check.close()
