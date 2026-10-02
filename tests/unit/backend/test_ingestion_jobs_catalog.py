"""Tài liệu ``danh_muc`` đọc bảng NAS sau khi trích Markdown (Pha D1).

Cố lập như các test ``ingestion_jobs`` hiện có: monkeypatch ``SessionLocal`` và
các phụ thuộc nặng (Qdrant, chunker). Không cần LibreOffice: nhánh ``.doc`` thay
``convert_legacy.cache_path`` bằng bản chuyển đổi thật trong ``tests/data/nas``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base, Document, DocumentType, Extraction, ExtractionStatus
from ingestion import jobs as ingestion_jobs
from scripts.knowledge_corpus import ooxml as ox

NAS = Path(__file__).resolve().parents[2] / "data" / "nas"
STEM = "bieu7_kdv"


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def _clear_jobs():
    with ingestion_jobs._jobs_lock:
        ingestion_jobs._jobs.clear()
    yield
    with ingestion_jobs._jobs_lock:
        ingestion_jobs._jobs.clear()


def _add_document(session, stem: str = STEM, ext: str = "DOCX") -> None:
    session.add(
        Document(
            id=stem,
            file_stem=stem,
            display_name=f"{stem}.{ext.lower()}",
            ext=ext,
            doc_type=DocumentType.DANH_MUC,
            sha256="0" * 64,
            size_bytes=1,
        )
    )
    session.commit()


def test_run_catalog_stores_pending_extraction(session, monkeypatch):
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)
    _add_document(session)

    summary = ingestion_jobs._run_catalog(STEM, NAS / "bieu7_kdv.docx")

    assert summary["kind"] == "inspector"
    assert summary["rows"] == 8
    extraction = session.get(Extraction, summary["extraction_id"])
    assert extraction.status == ExtractionStatus.PENDING
    assert extraction.extractor == "catalog:inspector.v1"


def test_run_catalog_skips_file_without_nas_table(session, monkeypatch, tmp_path):
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)
    _add_document(session, "khong_phai_danh_muc")
    plain = tmp_path / "khong_phai_danh_muc.docx"
    ox.write_docx(plain, [{"t": "p", "text": "Tài liệu thường, không có bảng NAS."}])

    assert ingestion_jobs._run_catalog("khong_phai_danh_muc", plain) is None
    assert session.query(Extraction).count() == 0


def test_run_catalog_reads_converted_file_for_legacy_doc(session, monkeypatch):
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)
    _add_document(session, STEM, "DOC")
    converted = NAS / "bieu7_kdv.docx"
    monkeypatch.setattr("ingestion.convert_legacy.cache_path", lambda path, out_dir=None: converted)

    summary = ingestion_jobs._run_catalog(STEM, Path("10. Bieu 7 (NAS).doc"))

    assert summary["rows"] == 8


def test_run_catalog_ignores_unsupported_format(session, monkeypatch):
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)
    _add_document(session, STEM, "PDF")
    assert ingestion_jobs._run_catalog(STEM, Path("tai-lieu.pdf")) is None


def test_markdown_job_runs_catalog_and_reports_result(session, monkeypatch, tmp_path):
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)
    monkeypatch.setattr(ingestion_jobs, "OUT_DIR", tmp_path)
    _add_document(session)

    def fake_process_one(source_path, out_dir):
        return {"file": source_path.name, "status": "ok", "formulas_found": 0}

    def fake_publish(tmp_dir, file_stem):
        (tmp_path / f"{file_stem}.md").write_text("# Danh sách KĐV", encoding="utf-8")

    payload = {
        "kind": "inspector",
        "label": "Danh sách kiểm định viên",
        "rows": 8,
        "extraction_id": 1,
        "superseded": 0,
        "warnings": [],
    }
    monkeypatch.setattr(ingestion_jobs, "process_one", fake_process_one)
    monkeypatch.setattr(ingestion_jobs, "_publish_extraction", fake_publish)
    monkeypatch.setattr(ingestion_jobs, "_merge_report_entry", lambda entry: None)
    monkeypatch.setattr(ingestion_jobs, "parse_file", lambda path: [])
    monkeypatch.setattr("vectorstore.qdrant.ensure_collection", lambda client: None)
    monkeypatch.setattr("vectorstore.upsert.index_chunks", lambda client, chunks: None)
    monkeypatch.setattr(ingestion_jobs, "_invalidate_bm25", lambda: None)
    monkeypatch.setattr(ingestion_jobs, "_run_extraction", lambda stem, md: None)
    monkeypatch.setattr(ingestion_jobs, "_run_catalog", lambda stem, path: payload)

    ingestion_jobs._run_markdown_job(STEM, Path("bieu7_kdv.docx"))

    job = ingestion_jobs._get_job(STEM)
    assert job is not None and job.stage == "ready"
    assert job.result == payload
    assert session.get(Document, STEM).ingest_error is None
