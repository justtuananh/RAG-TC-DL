"""Ingestion job sinh dòng ``procedure`` chỉ cho tài liệu QTKĐ.

Router văn bản cần ``procedure`` để ghim file; tài liệu loại khác không được gọi
``knowledge.procedure.ensure_procedure``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base, Document, DocumentType, Procedure
from ingestion import jobs as ingestion_jobs

QTKD_STEM = "QTKD_9.003_2026_Huyet_ap_ke"
KHAC_STEM = "Ghi_chu_noi_bo"


@pytest.fixture
def factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.drop_all(engine)
    engine.dispose()


def _add_document(factory, stem: str, doc_type: DocumentType) -> None:
    db = factory()
    db.add(
        Document(
            id=stem,
            file_stem=stem,
            display_name=f"{stem}.docx",
            ext="DOCX",
            doc_type=doc_type,
            sha256="0" * 64,
            size_bytes=1,
        )
    )
    db.commit()
    db.close()


def _spy(monkeypatch) -> list[str]:
    import knowledge.procedure as procedure_module

    calls: list[str] = []

    def _fake(session, document, text):
        calls.append(document.file_stem)
        return None

    monkeypatch.setattr(procedure_module, "ensure_procedure", _fake)
    return calls


def test_ensure_procedure_gates_on_qtkd(factory, monkeypatch, tmp_path):
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", factory)
    _add_document(factory, QTKD_STEM, DocumentType.QTKD)
    _add_document(factory, KHAC_STEM, DocumentType.KHAC)
    md = tmp_path / "doc.md"
    md.write_text("QTKĐ 9.003 : 2026\nHuyết áp kế\n", encoding="utf-8")
    calls = _spy(monkeypatch)

    ingestion_jobs._ensure_procedure("khong_ton_tai", md)
    ingestion_jobs._ensure_procedure(KHAC_STEM, md)
    assert calls == []

    ingestion_jobs._ensure_procedure(QTKD_STEM, md)
    assert calls == [QTKD_STEM]


def test_markdown_job_invokes_ensure_procedure(factory, monkeypatch, tmp_path, settings_override):
    settings_override({"paths.markdown_dir": str(tmp_path / "md")})
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", factory)
    _add_document(factory, QTKD_STEM, DocumentType.QTKD)
    calls = _spy(monkeypatch)

    def _fake_process_one(source_path: Path, out_dir: Path) -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{QTKD_STEM}.md").write_text("# QTKĐ\n", encoding="utf-8")
        return {"file": source_path.name}

    monkeypatch.setattr(ingestion_jobs, "process_one", _fake_process_one)
    monkeypatch.setattr(ingestion_jobs, "_merge_report_entry", lambda entry: None)
    monkeypatch.setattr(ingestion_jobs, "parse_file", lambda md_path: [])
    monkeypatch.setattr(ingestion_jobs, "_invalidate_bm25", lambda: None)
    monkeypatch.setattr(ingestion_jobs.qdrant, "get_client", lambda: object())
    monkeypatch.setattr(ingestion_jobs.qdrant, "ensure_collection", lambda client: None)
    monkeypatch.setattr(ingestion_jobs.upsert, "index_chunks", lambda client, chunks: None)

    ingestion_jobs._run_markdown_job(QTKD_STEM, tmp_path / f"{QTKD_STEM}.docx")

    assert calls == [QTKD_STEM]
    db = factory()
    try:
        assert db.query(Procedure).count() == 0  # spy không ghi DB thật
    finally:
        db.close()
