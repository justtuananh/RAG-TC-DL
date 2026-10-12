"""Xoá tài liệu: CSDL trước, rồi tệp/Markdown/Qdrant, không để lại trạng thái nửa vời.

Sau khi gỡ luồng tri thức, hàng duy nhất trỏ tới tài liệu là ``procedure``: xoá
tài liệu xoá kèm procedure. Test bật khoá ngoại SQLite để tái hiện như Postgres.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base, Document, DocumentType, Procedure
from ingestion import jobs as ingestion_jobs

STEM = "QTKD_9.003_2026_Huyet_ap_ke"


@pytest.fixture
def factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def corpus(tmp_path, factory, monkeypatch, settings_override):
    """Một QTKĐ đã xử lý: tệp nguồn, Markdown, hàng document + procedure."""
    src, out = tmp_path / "TC_DL", tmp_path / "md"
    src.mkdir()
    out.mkdir()
    settings_override({"paths.source_dir": str(src), "paths.markdown_dir": str(out)})
    (src / f"{STEM}.docx").write_bytes(b"docx")
    (out / f"{STEM}.md").write_text("# QTKĐ", encoding="utf-8")

    qdrant_deletes: list[str] = []
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", factory)
    monkeypatch.setattr(ingestion_jobs.qdrant, "get_client", lambda: object())
    monkeypatch.setattr(
        ingestion_jobs.qdrant, "delete_file_chunks", lambda _c, stem: qdrant_deletes.append(stem)
    )
    monkeypatch.setattr(ingestion_jobs, "_invalidate_bm25", lambda: None)

    db = factory()
    db.add(
        Document(
            id=STEM,
            file_stem=STEM,
            display_name=f"{STEM}.docx",
            ext="DOCX",
            doc_type=DocumentType.QTKD,
            sha256="0" * 64,
            size_bytes=4,
        )
    )
    db.add(Procedure(document_id=STEM, number="9.003", title="Huyết áp kế"))
    db.commit()
    db.close()
    return {"src": src, "out": out, "qdrant_deletes": qdrant_deletes, "factory": factory}


def _counts(factory) -> dict[str, int]:
    db = factory()
    try:
        return {
            "document": db.query(Document).count(),
            "procedure": db.query(Procedure).count(),
        }
    finally:
        db.close()


def test_document_and_procedure_are_removed_with_files(corpus):
    ingestion_jobs.delete_document(STEM)

    assert _counts(corpus["factory"]) == {"document": 0, "procedure": 0}
    assert not (corpus["src"] / f"{STEM}.docx").exists()
    assert not (corpus["out"] / f"{STEM}.md").exists()
    assert corpus["qdrant_deletes"] == [STEM]
