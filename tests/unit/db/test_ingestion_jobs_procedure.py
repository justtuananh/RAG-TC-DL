"""Ingestion job: nhận diện QTKĐ theo nội dung và giữ đúng MỘT phiên bản mỗi số QTKĐ.

Router văn bản ghim file qua bảng ``procedure``; mỗi số QTKĐ chỉ có một tài liệu
trong chỉ mục. Bản cũ hơn chuyển ``superseded`` (gỡ khỏi Qdrant, giữ tệp gốc +
Markdown) và được đưa trở lại khi bản mới bị xóa.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base, Document, DocumentType, IngestStatus, Procedure
from ingestion import jobs as ingestion_jobs

OLD = "QTKD_9.003_2016_Huyet_ap_ke"
NEW = "QTKD_9.003_2026_Huyet_ap_ke"
UNNAMED = "Quy_trinh_huyet_ap_ke"


def _markdown(year: int) -> str:
    return f"QTKĐ 9.003 : {year}\nHuyết áp kế\n\nQUY TRÌNH KIỂM ĐỊNH\n\n# 1. Phạm vi\n\nÁp dụng {year}.\n"


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


class _Index:
    """Qdrant giả: ghi lại file nào đang có chunk trong chỉ mục."""

    def __init__(self):
        self.stems: set[str] = set()
        self.refreshed: list[set[str]] = []


@pytest.fixture
def env(factory, monkeypatch, tmp_path, settings_override):
    out = tmp_path / "md"
    out.mkdir()
    settings_override({"paths.markdown_dir": str(out), "paths.source_dir": str(tmp_path / "src")})
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", factory)
    index = _Index()
    monkeypatch.setattr(ingestion_jobs.qdrant, "get_client", lambda: object())
    monkeypatch.setattr(ingestion_jobs.qdrant, "ensure_collection", lambda client: None)
    monkeypatch.setattr(
        ingestion_jobs.qdrant, "delete_file_chunks", lambda _c, stem: index.stems.discard(stem)
    )
    monkeypatch.setattr(
        ingestion_jobs.upsert,
        "index_chunks",
        lambda _c, chunks: index.stems.update(c.file_stem for c in chunks),
    )
    monkeypatch.setattr(
        ingestion_jobs,
        "_invalidate_search_caches",
        lambda stems: index.refreshed.append(set(stems)),
    )
    # Job khôi phục chạy đồng bộ để test đọc được kết quả ngay.
    monkeypatch.setattr(ingestion_jobs._executor, "submit", lambda fn, *args: fn(*args))
    monkeypatch.setattr(ingestion_jobs, "_jobs", {})
    return {"factory": factory, "out": out, "index": index}


def _add(env, stem: str, doc_type: DocumentType, md: str | None, minutes: int = 0) -> None:
    db = env["factory"]()
    db.add(
        Document(
            id=stem,
            file_stem=stem,
            display_name=f"{stem}.docx",
            ext="DOCX",
            doc_type=doc_type,
            sha256=stem.ljust(64, "0")[:64],
            size_bytes=1,
            uploaded_at=datetime(2026, 10, 12) + timedelta(minutes=minutes),
        )
    )
    db.commit()
    db.close()
    if md is not None:
        (env["out"] / f"{stem}.md").write_text(md, encoding="utf-8")


def _index(env, stem: str) -> None:
    ingestion_jobs._index_markdown(stem, env["out"] / f"{stem}.md")


def _row(env, stem: str) -> Document:
    db = env["factory"]()
    try:
        return db.get(Document, stem)
    finally:
        db.close()


def _owner(env, number: str = "9.003") -> str | None:
    db = env["factory"]()
    try:
        procedure = db.query(Procedure).filter(Procedure.number == number).one_or_none()
        return procedure.document_id if procedure is not None else None
    finally:
        db.close()


def test_procedure_only_for_qtkd(env):
    _add(env, "Bien_ban", DocumentType.HO_SO_KIEM_DINH, _markdown(2026))

    _index(env, "Bien_ban")

    assert _row(env, "Bien_ban").doc_type == DocumentType.HO_SO_KIEM_DINH
    assert _owner(env) is None
    assert ingestion_jobs._claim_procedure("khong_ton_tai", _markdown(2026)) is None


def test_untitled_file_with_qtkd_header_becomes_qtkd(env):
    """Tên tệp không nhắc QTKĐ nhưng đầu mục có mã: nhận là QTKĐ và được ghim."""
    _add(env, UNNAMED, DocumentType.KHAC, _markdown(2026))

    _index(env, UNNAMED)

    assert _row(env, UNNAMED).doc_type == DocumentType.QTKD
    assert _owner(env) == UNNAMED
    assert env["index"].stems == {UNNAMED}


def test_file_without_header_stays_khac(env):
    _add(env, "Ghi_chu", DocumentType.KHAC, "# Ghi chú\n\nKhông có mã quy trình.\n")

    _index(env, "Ghi_chu")

    row = _row(env, "Ghi_chu")
    assert (row.doc_type, row.ingest_status) == (DocumentType.KHAC, IngestStatus.READY)
    assert env["index"].stems == {"Ghi_chu"}


def test_newer_version_supersedes_old(env):
    _add(env, OLD, DocumentType.QTKD, _markdown(2016))
    _add(env, NEW, DocumentType.QTKD, _markdown(2026), minutes=1)
    _index(env, OLD)

    _index(env, NEW)

    assert _owner(env) == NEW
    assert env["index"].stems == {NEW}
    old = _row(env, OLD)
    assert old.ingest_status == IngestStatus.SUPERSEDED
    assert old.ingest_error == f"Đã có phiên bản mới hơn: {NEW}.docx"
    assert (env["out"] / f"{OLD}.md").exists()  # giữ để khôi phục
    assert _row(env, NEW).ingest_status == IngestStatus.READY
    assert env["index"].refreshed[-1] == {OLD, NEW}


def test_older_version_processed_later_is_superseded_itself(env):
    _add(env, NEW, DocumentType.QTKD, _markdown(2026))
    _add(env, OLD, DocumentType.QTKD, _markdown(2016), minutes=1)
    _index(env, NEW)

    _index(env, OLD)

    assert _owner(env) == NEW
    assert env["index"].stems == {NEW}
    assert _row(env, OLD).ingest_status == IngestStatus.SUPERSEDED
    assert _row(env, NEW).ingest_status == IngestStatus.READY


def test_same_year_revision_processed_later_wins(env):
    _add(env, OLD, DocumentType.QTKD, _markdown(2026))
    _add(env, NEW, DocumentType.QTKD, _markdown(2026), minutes=1)
    _index(env, OLD)

    _index(env, NEW)

    assert _owner(env) == NEW
    assert _row(env, OLD).ingest_status == IngestStatus.SUPERSEDED


def test_deleting_current_version_restores_previous(env):
    _add(env, OLD, DocumentType.QTKD, _markdown(2016))
    _add(env, NEW, DocumentType.QTKD, _markdown(2026), minutes=1)
    _index(env, OLD)
    _index(env, NEW)

    ingestion_jobs.delete_document(NEW)

    assert _row(env, NEW) is None
    assert _owner(env) == OLD
    assert env["index"].stems == {OLD}
    restored = _row(env, OLD)
    assert (restored.ingest_status, restored.ingest_error) == (IngestStatus.READY, None)


def test_deleting_superseded_version_keeps_current(env):
    _add(env, OLD, DocumentType.QTKD, _markdown(2016))
    _add(env, NEW, DocumentType.QTKD, _markdown(2026), minutes=1)
    _index(env, OLD)
    _index(env, NEW)

    ingestion_jobs.delete_document(OLD)

    assert _owner(env) == NEW
    assert env["index"].stems == {NEW}


def test_list_documents_reports_superseded(env):
    _add(env, OLD, DocumentType.QTKD, _markdown(2016))
    _add(env, NEW, DocumentType.QTKD, _markdown(2026), minutes=1)
    _index(env, OLD)
    _index(env, NEW)

    rows = {d["id"]: d for d in ingestion_jobs.list_documents()}

    assert (rows[OLD]["status"], rows[OLD]["progress"]) == ("superseded", 100)
    assert rows[OLD]["error"] == f"Đã có phiên bản mới hơn: {NEW}.docx"
    assert rows[NEW]["status"] == "ready"


def test_invalidate_search_caches_refreshes_bm25_files_then_router(monkeypatch):
    import retrieval.router as router_mod
    import vectorstore.hybrid_index as hybrid_index

    calls: list[object] = []
    monkeypatch.setattr(hybrid_index, "refresh_files", lambda stems: calls.append(set(stems)))
    monkeypatch.setattr(router_mod, "invalidate", lambda: calls.append("router"))

    ingestion_jobs._invalidate_search_caches({OLD, NEW})

    assert calls == [{OLD, NEW}, "router"]
