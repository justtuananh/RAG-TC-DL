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
    monkeypatch.setattr(ingestion_jobs, "_invalidate_search_caches", lambda stems: None)

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


def test_registry_failure_leaves_document_intact_and_retry_succeeds(corpus, monkeypatch):
    """Sổ công thức không ghi được (vd. SQLite thuộc root): xoá hỏng sạch, giữ nguyên tài liệu."""
    from formula_registry.store import Registry

    def _readonly(self, document_id):
        raise OSError("attempt to write a readonly database")

    original = Registry.invalidate
    monkeypatch.setattr(Registry, "invalidate", _readonly)

    with pytest.raises(OSError):
        ingestion_jobs.delete_document(STEM)

    assert _counts(corpus["factory"]) == {"document": 1, "procedure": 1}
    assert (corpus["src"] / f"{STEM}.docx").exists()
    assert (corpus["out"] / f"{STEM}.md").exists()
    assert corpus["qdrant_deletes"] == []

    monkeypatch.setattr(Registry, "invalidate", original)
    ingestion_jobs.delete_document(STEM)

    assert _counts(corpus["factory"]) == {"document": 0, "procedure": 0}
    assert not (corpus["src"] / f"{STEM}.docx").exists()


def test_failed_processing_still_reports_error_after_restart(corpus):
    """Job trong bộ nhớ mất khi API khởi động lại: sổ ghi ERROR thì không được báo "ready" chỉ vì .md còn."""
    from db.models import IngestStatus

    db = corpus["factory"]()
    row = db.query(Document).one()
    row.ingest_status = IngestStatus.ERROR
    row.ingest_error = "Không tạo được nháp công thức"
    db.commit()
    db.close()

    (doc,) = ingestion_jobs.list_documents()

    assert doc["status"] == "error"
    assert doc["error"] == "Không tạo được nháp công thức"


def test_report_entry_with_decomposed_unicode_name_is_removed(corpus, monkeypatch, tmp_path):
    """Tên tệp NFD (macOS) phải cho cùng stem với NFC, để xoá gỡ được mục report."""
    import json
    import unicodedata

    stem = "Biểu_mẫu"
    (corpus["src"] / f"{stem}.docx").write_bytes(b"docx")
    nfd_name = unicodedata.normalize("NFD", "Biểu mẫu.docx")
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps({"files": [{"file": nfd_name}], "totals": {}}), encoding="utf-8"
    )
    monkeypatch.setattr(ingestion_jobs, "_report_path", lambda: report_path)

    ingestion_jobs.delete_document(stem)

    assert json.loads(report_path.read_text(encoding="utf-8"))["files"] == []
