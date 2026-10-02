"""Xoá tài liệu: chặn khi còn dữ liệu đã duyệt, không bao giờ để lại trạng thái nửa vời.

Lỗi gốc (đo E2E 2026-10-02): xoá một QTKĐ đã xử lý xoá tệp nguồn, Markdown và điểm Qdrant
TRƯỚC, rồi mới xoá hàng ``document`` và vấp khoá ngoại ``procedure_document_id_fkey``:
CSDL còn bản ghi, tệp và vector đã mất. Test bật khoá ngoại SQLite để tái hiện như Postgres.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import (
    AppUser,
    Base,
    Document,
    DocumentType,
    Extraction,
    ExtractionStatus,
    Procedure,
    Term,
    UserRole,
)
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


def _add_extraction(factory, status: ExtractionStatus) -> int:
    db = factory()
    row = Extraction(document_id=STEM, quote="Phạm vi đo", extractor="rule:test", status=status)
    db.add(row)
    db.commit()
    row_id = row.id
    db.close()
    return row_id


def _counts(factory) -> dict[str, int]:
    db = factory()
    try:
        return {
            "document": db.query(Document).count(),
            "procedure": db.query(Procedure).count(),
            "extraction": db.query(Extraction).count(),
        }
    finally:
        db.close()


def _untouched(corpus) -> bool:
    return (
        (corpus["src"] / f"{STEM}.docx").exists()
        and (corpus["out"] / f"{STEM}.md").exists()
        and corpus["qdrant_deletes"] == []
    )


def test_pending_extractions_are_removed_with_the_document(corpus):
    _add_extraction(corpus["factory"], ExtractionStatus.PENDING)
    _add_extraction(corpus["factory"], ExtractionStatus.REJECTED)

    ingestion_jobs.delete_document(STEM)

    assert _counts(corpus["factory"]) == {"document": 0, "procedure": 0, "extraction": 0}
    assert not (corpus["src"] / f"{STEM}.docx").exists()
    assert not (corpus["out"] / f"{STEM}.md").exists()
    assert corpus["qdrant_deletes"] == [STEM]


@pytest.mark.parametrize("status", [ExtractionStatus.APPROVED, ExtractionStatus.SUPERSEDED])
def test_reviewed_extraction_blocks_delete_and_touches_nothing(corpus, status):
    _add_extraction(corpus["factory"], status)

    with pytest.raises(ingestion_jobs.DocumentInUseError, match="đã duyệt"):
        ingestion_jobs.delete_document(STEM)

    assert _counts(corpus["factory"]) == {"document": 1, "procedure": 1, "extraction": 1}
    assert _untouched(corpus)


def test_facts_of_pending_extractions_go_with_the_document(corpus):
    # Xử lý xong một QTKĐ là đã có dữ kiện gắn vào trích xuất CHỜ duyệt (đo E2E: 16 fact,
    # 6 standard, 4 term); duyệt nằm ở extraction nên chúng chưa phải dữ liệu sổ cái.
    extraction_id = _add_extraction(corpus["factory"], ExtractionStatus.PENDING)
    db = corpus["factory"]()
    procedure_id = db.query(Procedure.id).scalar()
    db.add(Term(extraction_id=extraction_id, procedure_id=procedure_id, term_vi="huyết áp kế"))
    db.commit()
    db.close()

    ingestion_jobs.delete_document(STEM)

    db = corpus["factory"]()
    assert db.query(Term).count() == 0
    db.close()
    assert _counts(corpus["factory"]) == {"document": 0, "procedure": 0, "extraction": 0}


def test_other_documents_data_referencing_the_procedure_blocks_delete(corpus):
    # Dữ kiện đã duyệt của TÀI LIỆU KHÁC trỏ tới QTKĐ này: xoá sẽ làm mồ côi nó.
    db = corpus["factory"]()
    db.add(
        Document(
            id="khac",
            file_stem="khac",
            display_name="khac.docx",
            ext="DOCX",
            doc_type=DocumentType.QTKD,
            sha256="1" * 64,
            size_bytes=1,
        )
    )
    other = Extraction(
        document_id="khac", quote="q", extractor="rule:test", status=ExtractionStatus.APPROVED
    )
    db.add(other)
    db.flush()
    procedure_id = db.query(Procedure.id).filter(Procedure.document_id == STEM).scalar()
    db.add(Term(extraction_id=other.id, procedure_id=procedure_id, term_vi="huyết áp kế"))
    db.commit()
    db.close()

    with pytest.raises(ingestion_jobs.DocumentInUseError, match="thuật ngữ: 1"):
        ingestion_jobs.delete_document(STEM)

    assert _counts(corpus["factory"])["document"] == 2
    assert _untouched(corpus)


def test_route_answers_409_with_the_reason(corpus):
    from fastapi.testclient import TestClient

    from api.main import app
    from auth.dependencies import get_current_user

    _add_extraction(corpus["factory"], ExtractionStatus.APPROVED)
    admin = AppUser(id=1, username="admin", role=UserRole.ADMIN, is_active=1)
    app.dependency_overrides[get_current_user] = lambda: admin
    try:
        resp = TestClient(app).delete(f"/api/documents/{STEM}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409
    assert "đã duyệt" in resp.json()["detail"]
    assert _untouched(corpus)
