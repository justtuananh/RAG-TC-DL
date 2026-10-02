"""Upload .xlsx + bước "Xử lý" tài liệu hồ sơ (B1, B2, B3).

Hồ sơ kiểm định đi đường ``records.ingest`` (ghi bản ghi chờ duyệt), KHÔNG trích
Markdown và KHÔNG nhúng Qdrant. Test cố lập ``ingestion_jobs`` như các test hiện
có: monkeypatch ``TC_DL_DIR``/``SessionLocal``, không cần Docker.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import ingestion_jobs
from db.models import Base, Document, DocumentType, IngestStatus
from records.ingest import IngestError
from records.store import StoreResult

RECORD_STEM = "BB_2024_001"
QTKD_STEM = "QTKD_1.061_2021_ND_V2"


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
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
    """Không để trạng thái job rò rỉ giữa các test."""
    with ingestion_jobs._jobs_lock:
        ingestion_jobs._jobs.clear()
    yield
    with ingestion_jobs._jobs_lock:
        ingestion_jobs._jobs.clear()


def _add_document(session, stem: str, doc_type: DocumentType, ext: str) -> None:
    session.add(
        Document(
            id=stem,
            file_stem=stem,
            display_name=f"{stem}.{ext.lower()}",
            ext=ext,
            doc_type=doc_type,
            sha256="0" * 64,
            size_bytes=1,
        )
    )
    session.commit()


def test_find_source_locates_uploaded_xlsx(tmp_path, monkeypatch):
    """B2: ``get_source_path`` phải tìm được tệp .xlsx đã upload."""
    monkeypatch.setattr(ingestion_jobs, "TC_DL_DIR", tmp_path)
    path = tmp_path / f"{RECORD_STEM}.xlsx"
    path.write_bytes(b"PK\x03\x04")
    assert ingestion_jobs.get_source_path(RECORD_STEM) == path


def test_save_upload_accepts_xlsx(tmp_path, monkeypatch, session):
    """B1: upload nhận .xlsx và xếp loại hồ sơ kiểm định."""
    monkeypatch.setattr(ingestion_jobs, "TC_DL_DIR", tmp_path / "tc_dl")
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)

    stem = ingestion_jobs.save_upload("Biên bản kiểm định A.xlsx", b"PK\x03\x04noi-dung")

    assert (tmp_path / "tc_dl" / f"{stem}.xlsx").exists()
    assert session.get(Document, stem).doc_type == DocumentType.HO_SO_KIEM_DINH


def test_save_upload_rejects_unknown_extension():
    with pytest.raises(ingestion_jobs.UploadError, match="Excel"):
        ingestion_jobs.save_upload("tai-lieu.txt", b"x")


def test_record_job_ingests_without_markdown_or_embedding(session, monkeypatch):
    """B3: hồ sơ đi ``records.ingest``; nhánh Markdown/nhúng Qdrant không được chạm."""
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)
    _add_document(session, RECORD_STEM, DocumentType.HO_SO_KIEM_DINH, "XLSX")

    seen: dict[str, object] = {}

    def fake_ingest(file_stem: str) -> StoreResult:
        seen["stem"] = file_stem
        return StoreResult(record_id=7, extraction_id=8, device_id=9, measurement_points=3)

    def bomb(*_args, **_kwargs):
        raise AssertionError("nhánh hồ sơ KHÔNG được trích Markdown/nhúng Qdrant")

    monkeypatch.setattr("records.ingest.ingest_file_stem", fake_ingest)
    monkeypatch.setattr(ingestion_jobs, "process_one", bomb)
    monkeypatch.setattr("vectorstore.upsert.index_chunks", bomb)

    ingestion_jobs._run_job(RECORD_STEM, Path(RECORD_STEM + ".xlsx"))

    assert seen["stem"] == RECORD_STEM
    job = ingestion_jobs._get_job(RECORD_STEM)
    assert job is not None and job.stage == "ready"
    assert (
        job.result
        == StoreResult(record_id=7, extraction_id=8, device_id=9, measurement_points=3).as_dict()
    )
    assert session.get(Document, RECORD_STEM).ingest_status == IngestStatus.READY


def test_record_job_surfaces_business_error_verbatim(session, monkeypatch):
    """B3: lỗi nghiệp vụ (IngestError) hiện nguyên văn, document chuyển ERROR."""
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)
    _add_document(session, RECORD_STEM, DocumentType.HO_SO_KIEM_DINH, "XLSX")

    message = "Chưa có dữ kiện Phụ lục A nào đã duyệt cho QTKĐ 1.159."

    def boom(_file_stem: str) -> StoreResult:
        raise IngestError(message)

    monkeypatch.setattr("records.ingest.ingest_file_stem", boom)

    ingestion_jobs._run_job(RECORD_STEM, Path(RECORD_STEM + ".xlsx"))

    job = ingestion_jobs._get_job(RECORD_STEM)
    assert job is not None and job.stage == "error"
    assert job.error == message
    assert job.result is None
    row = session.get(Document, RECORD_STEM)
    assert row.ingest_status == IngestStatus.ERROR
    assert row.ingest_error == message


def test_qtkd_job_uses_markdown_path(session, monkeypatch):
    """Tài liệu QTKĐ vẫn đi đường trích Markdown (không đổi hành vi cũ)."""
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)
    _add_document(session, QTKD_STEM, DocumentType.QTKD, "DOCX")

    seen: list[str] = []
    monkeypatch.setattr(ingestion_jobs, "_run_markdown_job", lambda stem, path: seen.append("md"))
    monkeypatch.setattr(ingestion_jobs, "_run_record_job", lambda stem: seen.append("record"))

    ingestion_jobs._run_job(QTKD_STEM, Path(QTKD_STEM + ".docx"))

    assert seen == ["md"]


def test_list_documents_exposes_store_result(session, monkeypatch):
    """API trả ``result`` (StoreResult.as_dict) cho hồ sơ đã xử lý xong."""
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)
    _add_document(session, RECORD_STEM, DocumentType.HO_SO_KIEM_DINH, "XLSX")
    payload = StoreResult(record_id=7, extraction_id=8, device_id=9, measurement_points=3).as_dict()
    ingestion_jobs._set_job(RECORD_STEM, "ready", result=payload)

    docs = {doc["id"]: doc for doc in ingestion_jobs.list_documents()}

    assert docs[RECORD_STEM]["status"] == "ready"
    assert docs[RECORD_STEM]["progress"] == 100
    assert docs[RECORD_STEM]["result"] == payload
