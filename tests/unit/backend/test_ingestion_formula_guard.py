"""B10: chốt chặn hồi quy công thức khi bấm "Xử lý" lại một tài liệu.

Một lần trích lỗi (thiếu gem Ruby ``pry``) trước đây ghi đè bản Markdown đã
kiểm chứng và nhúng chunk hỏng. Test cô lập ``ingestion_jobs`` bằng
``tmp_path`` + monkeypatch ``OUT_DIR``/``process_one``; không đụng
``build/spike_a/`` thật, không cần Docker.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import ingestion_jobs
from db.models import Base, Document, DocumentType, IngestStatus
from ingestion.spike_a import totals_from_entries

STEM = "QTKD_1.159_2021_ND_FINAL"
FILE = f"{STEM}.docx"


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
    with ingestion_jobs._jobs_lock:
        ingestion_jobs._jobs.clear()
    yield
    with ingestion_jobs._jobs_lock:
        ingestion_jobs._jobs.clear()


def _entry(file_name: str, n_found: int, n_converted: int) -> dict:
    """Entry thô đúng dạng ``process_one`` trả (đủ khóa cho totals_from_entries)."""
    detail = [
        {
            "fid": f"F{i}",
            "kind": "ole",
            "section": "1",
            "in_table": False,
            "latex": "x" if i < n_converted else None,
        }
        for i in range(n_found)
    ]
    return {
        "file": file_name,
        "status": "ok",
        "headings": 1,
        "tables": 0,
        "paragraphs": 1,
        "media_parts": 0,
        "embedded_ole": n_found,
        "formulas_found": n_found,
        "formulas_ole": n_found,
        "formulas_omml": 0,
        "formula_detail": detail,
    }


def _prepare(tmp_path, session, monkeypatch) -> Path:
    out = tmp_path / "build_spike_a"
    out.mkdir()
    monkeypatch.setattr(ingestion_jobs, "OUT_DIR", out)
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)
    session.add(
        Document(
            id=STEM,
            file_stem=STEM,
            display_name=FILE,
            ext="DOCX",
            doc_type=DocumentType.QTKD,
            sha256="0" * 64,
            size_bytes=1,
        )
    )
    session.commit()
    return out


def _write_report(out: Path, entries: list[dict]) -> None:
    out.joinpath("extraction_report.json").write_text(
        json.dumps({"source": "TC_DL", "files": entries, "totals": totals_from_entries(entries)}),
        encoding="utf-8",
    )


def test_markdown_job_blocks_formula_regression(tmp_path, monkeypatch, session):
    """Bản mới giảm tỉ lệ (100 % -> 10 %): giữ nguyên .md cũ, không nhúng, ERROR."""
    out = _prepare(tmp_path, session, monkeypatch)
    verified = out / f"{STEM}.md"
    verified.write_text("$x$ bản đã kiểm chứng", encoding="utf-8")
    _write_report(out, [_entry(FILE, 10, 10)])
    before = verified.read_bytes()

    embedded: list[object] = []
    monkeypatch.setattr("vectorstore.upsert.index_chunks", lambda *a, **k: embedded.append(a))

    def fake_process_one(source: Path, out_dir: Path) -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{STEM}.md").write_text("[công thức không đọc được]", encoding="utf-8")
        return _entry(FILE, 10, 1)

    monkeypatch.setattr(ingestion_jobs, "process_one", fake_process_one)

    ingestion_jobs._run_markdown_job(STEM, Path(FILE))

    assert verified.read_bytes() == before
    assert embedded == []
    job = ingestion_jobs._get_job(STEM)
    assert job is not None and job.stage == "error"
    assert "100" in job.error and "10" in job.error
    assert "giữ nguyên" in job.error
    assert session.get(Document, STEM).ingest_status == IngestStatus.ERROR
    report = json.loads((out / "extraction_report.json").read_text(encoding="utf-8"))
    assert [e["file"] for e in report["files"]] == [FILE]


def test_markdown_job_publishes_when_rate_not_worse(tmp_path, monkeypatch, session):
    """Bản mới bằng/tốt hơn: công bố .md mới, nhúng, report và tài liệu READY."""
    out = _prepare(tmp_path, session, monkeypatch)
    (out / f"{STEM}.md").write_text("$x$ cũ", encoding="utf-8")
    _write_report(out, [_entry(FILE, 10, 5)])

    embedded: list[object] = []
    monkeypatch.setattr(
        "vectorstore.upsert.index_chunks", lambda client, chunks: embedded.append(chunks)
    )
    monkeypatch.setattr(ingestion_jobs, "parse_file", lambda p: ["c1", "c2"])
    monkeypatch.setattr("vectorstore.qdrant.ensure_collection", lambda client: None)
    monkeypatch.setattr(ingestion_jobs, "_run_extraction", lambda stem, path: None)

    def fake_process_one(source: Path, out_dir: Path) -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{STEM}.md").write_text("$y$ bản mới", encoding="utf-8")
        return _entry(FILE, 10, 10)

    monkeypatch.setattr(ingestion_jobs, "process_one", fake_process_one)

    ingestion_jobs._run_markdown_job(STEM, Path(FILE))

    assert (out / f"{STEM}.md").read_text(encoding="utf-8") == "$y$ bản mới"
    assert embedded == [["c1", "c2"]]
    job = ingestion_jobs._get_job(STEM)
    assert job is not None and job.stage == "ready"
    assert session.get(Document, STEM).ingest_status == IngestStatus.READY
    report = json.loads((out / "extraction_report.json").read_text(encoding="utf-8"))
    assert report["files"][0]["formula_detail"][0]["latex"] == "x"
