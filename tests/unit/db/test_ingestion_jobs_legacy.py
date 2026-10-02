"""Định tuyến upload/xử lý cho .doc/.xls cũ (K1) + chuyển đổi trong spike_a.process_one.

Không cần LibreOffice: ca ``process_one`` thay ``spike_a.convert_legacy`` bằng
một tệp .docx/.xlsx thật dựng bằng OOXML thô; ca định tuyến chỉ monkeypatch hai
nhánh ``_run_markdown_job`` / ``_run_record_job``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base, Document, DocumentType
from ingestion import jobs as ingestion_jobs
from ingestion import spike_a
from scripts.knowledge_corpus import ooxml as ox

DOC_STEM = "Bieu_1_NAS"
XLS_STEM = "Bieu_3_NAS"
RECORD_STEM = "BB_2024_002"


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


def test_find_source_locates_doc_and_xls(tmp_path, monkeypatch, settings_override):
    settings_override({"paths.source_dir": str(tmp_path)})
    doc = tmp_path / f"{DOC_STEM}.doc"
    xls = tmp_path / f"{XLS_STEM}.xls"
    doc.write_bytes(b"\xd0\xcf\x11\xe0")
    xls.write_bytes(b"\xd0\xcf\x11\xe0")
    assert ingestion_jobs.get_source_path(DOC_STEM) == doc
    assert ingestion_jobs.get_source_path(XLS_STEM) == xls


def test_save_upload_accepts_doc_and_updates_ledger(
    tmp_path, monkeypatch, session, settings_override
):
    settings_override({"paths.source_dir": str(tmp_path / "tc_dl")})
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)

    stem = ingestion_jobs.save_upload("4. Bieu 1 Kiem dinh NAS.doc", b"\xd0\xcf\x11\xe0")

    assert (tmp_path / "tc_dl" / f"{stem}.doc").exists()
    assert session.get(Document, stem).doc_type == DocumentType.DANH_MUC


def test_doc_catalog_routes_markdown(session, monkeypatch):
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)
    _add_document(session, DOC_STEM, DocumentType.DANH_MUC, "DOC")

    seen: list[str] = []
    monkeypatch.setattr(ingestion_jobs, "_run_markdown_job", lambda stem, path: seen.append("md"))
    monkeypatch.setattr(ingestion_jobs, "_run_record_job", lambda stem: seen.append("record"))

    ingestion_jobs._run_job(DOC_STEM, Path(DOC_STEM + ".doc"))

    assert seen == ["md"]


def test_xls_catalog_routes_markdown(session, monkeypatch):
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)
    _add_document(session, XLS_STEM, DocumentType.DANH_MUC, "XLS")

    seen: list[str] = []
    monkeypatch.setattr(ingestion_jobs, "_run_markdown_job", lambda stem, path: seen.append("md"))
    monkeypatch.setattr(ingestion_jobs, "_run_record_job", lambda stem: seen.append("record"))

    ingestion_jobs._run_job(XLS_STEM, Path(XLS_STEM + ".xls"))

    assert seen == ["md"]


def test_xlsx_record_still_routes_record(session, monkeypatch):
    """Không lùi: .xlsx loại hồ sơ kiểm định vẫn đi đường ghi bản ghi."""
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)
    _add_document(session, RECORD_STEM, DocumentType.HO_SO_KIEM_DINH, "XLSX")

    seen: list[str] = []
    monkeypatch.setattr(ingestion_jobs, "_run_markdown_job", lambda stem, path: seen.append("md"))
    monkeypatch.setattr(ingestion_jobs, "_run_record_job", lambda stem: seen.append("record"))

    ingestion_jobs._run_job(RECORD_STEM, Path(RECORD_STEM + ".xlsx"))

    assert seen == ["record"]


def test_process_one_doc_converts_and_keeps_original_name(tmp_path, monkeypatch):
    converted = tmp_path / "converted.docx"
    ox.write_docx(converted, [{"t": "p", "text": "Noi dung NAS"}])
    src = tmp_path / "10. Bieu 7 Danh sach KDV (NAS).doc"
    src.write_bytes(b"\xd0\xcf\x11\xe0")
    monkeypatch.setattr(spike_a, "convert_legacy", lambda path, out_dir: converted)

    entry = spike_a.process_one(src, tmp_path / "out")

    assert entry["status"] == "ok"
    assert entry["file"] == src.name
    assert entry["converted_from"] == str(converted)
    assert (tmp_path / "out" / f"{spike_a._safe(src.stem)}.md").exists()


def test_process_one_xls_converts_and_extracts(tmp_path, monkeypatch):
    converted = tmp_path / "converted.xlsx"
    ox.write_xlsx(converted, [ox.Sheet("NAS-2022", [["TT", "Ten"], [1, "abc"]])])
    src = tmp_path / "6. Bieu 3 Danh muc chuan mau 2022 NAS.xls"
    src.write_bytes(b"\xd0\xcf\x11\xe0")
    monkeypatch.setattr(spike_a, "convert_legacy", lambda path, out_dir: converted)

    entry = spike_a.process_one(src, tmp_path / "out")

    assert entry["status"] == "ok"
    assert entry["file"] == src.name
    assert entry["converted_from"] == str(converted)
    assert entry["formulas_found"] == 0
    md = (tmp_path / "out" / f"{spike_a._safe(src.stem)}.md").read_text(encoding="utf-8")
    assert "# NAS-2022" in md


def test_xlsx_catalog_extracts_markdown_without_formula_regression(tmp_path):
    """Entry bảng tính: 0 công thức, tỉ lệ None, B10 không coi là hồi quy."""
    converted = tmp_path / "c.xlsx"
    ox.write_xlsx(converted, [ox.Sheet("NAS-2022", [["TT", "Ten"], [1, "abc"]])])
    entry = spike_a._process_xlsx(converted, tmp_path / "out")
    assert ingestion_jobs.totals_from_entries([entry])["latex_rate_total"] is None
    assert ingestion_jobs._regression_message(entry, entry) is None
    assert entry["formulas_found"] == 0
