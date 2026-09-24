"""Glue upload -> extraction -> chunking -> embedding for one .docx/.pdf at a time.

Backs the /api/documents/* routes in api_server.py. Each ingestion job runs on
a dedicated worker thread (not asyncio BackgroundTasks) so a slow Ruby/MTEF
subprocess or embedding-service HTTP call never blocks the chat SSE event loop.
"""
from __future__ import annotations

import json
import hashlib
import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException
from qdrant_client.models import FieldCondition, Filter, MatchValue

# Connection failures from the embedding service (requests -> OSError subclass)
# and from Qdrant (its own ResponseHandlingException, NOT an OSError subclass)
# both mean "Docker isn't running" — treat them the same way for the user.
_CONNECTION_ERRORS = (OSError, ResponseHandlingException)

from index.chunker import parse_file
from index.embed_store import COLLECTION, QDRANT_URL, ensure_collection, index_chunks
from ingestion.spike_a import _safe, process_one, totals_from_entries
from ingestion.classify import classify_document
from db import SessionLocal
from db.models import Document, DocumentType, IngestStatus

# retrieval.bm25_index is imported lazily where used (see invalidate_bm25) —
# it requires rank_bm25, and retriever.py already avoids a hard module-level
# dependency on that package for the same reason.

TC_DL_DIR = Path("TC_DL")
OUT_DIR = Path("build/spike_a")
REPORT_PATH = OUT_DIR / "extraction_report.json"

MAX_UPLOAD_BYTES = 50 * 1024 * 1024

_PROCESSING_STAGES = {"queued", "extracting", "chunking", "embedding"}
_STAGE_PROGRESS = {
    "queued": 5,
    "extracting": 35,
    "chunking": 60,
    "embedding": 85,
    "ready": 100,
}


class UploadError(ValueError):
    """User-facing validation error for an upload (bad extension, too large, empty)."""


@dataclass
class Job:
    stage: str  # "queued" | "extracting" | "chunking" | "embedding" | "ready" | "error"
    progress: int
    error: Optional[str] = None


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1)

logger = logging.getLogger(__name__)


def _set_job(file_stem: str, stage: str, error: str | None = None) -> None:
    with _jobs_lock:
        prev = _jobs.get(file_stem)
        progress = _STAGE_PROGRESS[stage] if stage in _STAGE_PROGRESS else (prev.progress if prev else 0)
        _jobs[file_stem] = Job(stage=stage, progress=progress, error=error)


def _get_job(file_stem: str) -> Job | None:
    with _jobs_lock:
        return _jobs.get(file_stem)


def _human_size(n: int) -> str:
    mb = n / (1024 * 1024)
    if mb >= 1:
        return f"{mb:.1f} MB".replace(".", ",")
    return f"{n / 1024:.0f} KB"


def _invalidate_bm25() -> None:
    """Best-effort — a stale BM25 cache is a search-quality issue, not a reason
    to fail an otherwise-successful embed or delete (also lets this work in
    environments where rank_bm25 isn't installed, same as retriever.py)."""
    try:
        from retrieval.bm25_index import invalidate
        invalidate()
    except Exception:
        pass


SUPPORTED_EXTS = (".docx", ".pdf")


def _find_source(file_stem: str) -> Path | None:
    """Locate the on-disk source file (.docx or .pdf) for a file_stem — its
    real filename may still carry spaces/original casing (pre-existing corpus
    files) while a freshly uploaded file is saved directly under its
    sanitized stem."""
    if not TC_DL_DIR.exists():
        return None
    for ext in SUPPORTED_EXTS:
        for f in TC_DL_DIR.glob(f"*{ext}"):
            if _safe(f.stem) == file_stem:
                return f
    return None


def get_source_path(file_stem: str) -> Path | None:
    """Public accessor for the on-disk original .docx/.pdf — used to serve the
    raw file back to the frontend (as opposed to its extracted Markdown)."""
    return _find_source(file_stem)


def save_upload(filename: str, data: bytes, uploaded_by: int | None = None) -> str:
    """Validate + save an uploaded .docx/.pdf into TC_DL/. Returns its file_stem."""
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise UploadError("Chỉ hỗ trợ tệp Word (.docx) hoặc PDF (.pdf).")
    if len(data) == 0:
        raise UploadError("Tệp rỗng.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadError("Tệp vượt quá dung lượng cho phép (50 MB).")
    digest = hashlib.sha256(data).hexdigest()

    TC_DL_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        if db.query(Document).filter(Document.sha256 == digest).first() is not None:
            raise UploadError("Tài liệu đã tồn tại trong kho (trùng nội dung).")
    finally:
        db.close()
    stem = _safe(Path(filename).stem)
    candidate = stem
    n = 2
    while (TC_DL_DIR / f"{candidate}{ext}").exists() or _find_source(candidate) is not None:
        candidate = f"{stem}_{n}"
        n += 1

    (TC_DL_DIR / f"{candidate}{ext}").write_bytes(data)
    db = SessionLocal()
    try:
        classification = classify_document(filename)
        db.add(
            Document(
                id=candidate,
                file_stem=candidate,
                display_name=Path(filename).name,
                ext=ext[1:].upper(),
                doc_type=DocumentType(classification.doc_type),
                sha256=digest,
                size_bytes=len(data),
                uploaded_by=uploaded_by,
                ingest_status=IngestStatus.PENDING,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        (TC_DL_DIR / f"{candidate}{ext}").unlink(missing_ok=True)
        raise
    finally:
        db.close()
    return candidate


def _status_for(file_stem: str) -> tuple[str, int, str | None]:
    job = _get_job(file_stem)
    if job is not None:
        if job.stage in _PROCESSING_STAGES:
            return "processing", job.progress, None
        if job.stage == "error":
            return "error", job.progress, job.error
        # job.stage == "ready" falls through to the file check below
    if (OUT_DIR / f"{file_stem}.md").exists():
        return "ready", 100, None
    return "pending", 0, None


def list_documents() -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.query(Document).order_by(Document.uploaded_at.desc()).all()
        result = []
        for row in rows:
            status, progress, error = _status_for(row.file_stem)
            result.append({
                "id": row.file_stem,
                "name": row.display_name,
                "ext": row.ext,
                "size": _human_size(row.size_bytes),
                "pages": None,
                "date": row.uploaded_at.strftime("%d/%m/%Y"),
                "status": status if status != "pending" or row.ingest_status.value == "pending" else row.ingest_status.value,
                "progress": progress,
                "error": error or row.ingest_error,
                "doc_type": row.doc_type.value,
                "sha256": row.sha256,
            })
        return result
    finally:
        db.close()


def get_markdown(file_stem: str) -> str | None:
    p = OUT_DIR / f"{file_stem}.md"
    return p.read_text(encoding="utf-8") if p.exists() else None


def _merge_report_entry(entry: dict) -> None:
    """Replace this file's entry in extraction_report.json and recompute totals
    without re-processing the rest of the corpus."""
    if REPORT_PATH.exists():
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    else:
        report = {"source": str(TC_DL_DIR), "files": [], "totals": {}}
    report["files"] = [e for e in report["files"] if e["file"] != entry["file"]]
    report["files"].append(entry)
    report["totals"] = totals_from_entries(report["files"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_job(file_stem: str, source_path: Path) -> None:
    try:
        _set_db_status(file_stem, IngestStatus.PROCESSING)
        _set_job(file_stem, "extracting")
        entry = process_one(source_path, OUT_DIR)
        _merge_report_entry(entry)

        md_path = OUT_DIR / f"{file_stem}.md"
        if not md_path.exists():
            raise RuntimeError("Không trích xuất được nội dung — tệp có thể bị lỗi hoặc rỗng.")

        _set_job(file_stem, "chunking")
        chunks = parse_file(md_path)

        _set_job(file_stem, "embedding")
        client = QdrantClient(url=QDRANT_URL)
        ensure_collection(client)
        index_chunks(client, chunks)
        _invalidate_bm25()

        # Sprint 4: sau khi nhúng, trích xuất tri thức cho QTKĐ (trạng thái pending).
        # Lỗi trích xuất không làm hỏng tài liệu đã nhúng; ghi lại để rà sau.
        extraction_error: str | None = None
        try:
            _run_extraction(file_stem, md_path)
        except Exception as e:  # noqa: BLE001 - best-effort, không chặn ingestion
            extraction_error = f"Trích xuất tri thức thất bại: {e}"

        _set_job(file_stem, "ready")
        _set_db_status(file_stem, IngestStatus.READY, extraction_error)
    except _CONNECTION_ERRORS as e:
        _set_job(file_stem, "error", f"Không kết nối được dịch vụ embedding/Qdrant — kiểm tra Docker đã chạy chưa ({e}).")
        _set_db_status(file_stem, IngestStatus.ERROR, str(e))
    except Exception as e:  # noqa: BLE001 - surface any failure as a job error, never crash the worker thread
        _set_job(file_stem, "error", str(e))
        _set_db_status(file_stem, IngestStatus.ERROR, str(e))


def _run_extraction(file_stem: str, md_path: Path) -> None:
    """Chạy bộ luật trích xuất cho tài liệu QTKĐ và ghi extraction ``pending``.

    Bỏ qua tài liệu không phải QTKĐ. Dùng procedure đã sinh nếu có; nếu chưa,
    ``knowledge.extract`` tự dựng từ đầu mục Markdown để giữ liên kết P1.

    Sprint 5: sau luật, tùy chọn chạy trích xuất §6 bằng LLM (``SECTION6_LLM_ENABLED``).
    Bọc trong SAVEPOINT và thất bại an toàn — Ollama chưa lên/model chưa pull
    không được làm hỏng phần luật đã ghi, và mọi dòng mới vẫn ``pending`` (P3).
    """
    from db.models import Procedure
    from knowledge.extract import extract_and_store, extract_section6_and_store
    from knowledge.llm_extract import llm_extraction_enabled

    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.file_stem == file_stem).one_or_none()
        if document is None or document.doc_type != DocumentType.QTKD:
            return
        text = md_path.read_text(encoding="utf-8")
        procedure = (
            db.query(Procedure).filter(Procedure.document_id == document.id).one_or_none()
        )
        extract_and_store(db, document, text, procedure=procedure)

        if llm_extraction_enabled():
            try:
                with db.begin_nested():
                    extract_section6_and_store(db, document, text, procedure=procedure)
            except Exception as e:  # noqa: BLE001 - §6 best-effort, không chặn ingestion
                logger.warning("Trích xuất §6 bằng LLM thất bại cho %s: %s", file_stem, e)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _set_db_status(file_stem: str, status: IngestStatus, error: str | None = None) -> None:
    db = SessionLocal()
    try:
        row = db.query(Document).filter(Document.file_stem == file_stem).one_or_none()
        if row:
            row.ingest_status = status
            row.ingest_error = error
            db.commit()
    finally:
        db.close()


def start_processing(file_stem: str) -> None:
    source_path = _find_source(file_stem)
    if source_path is None:
        raise FileNotFoundError(file_stem)
    job = _get_job(file_stem)
    if job is not None and job.stage in _PROCESSING_STAGES:
        raise RuntimeError("already processing")
    _set_job(file_stem, "queued")
    _executor.submit(_run_job, file_stem, source_path)


def delete_document(file_stem: str) -> None:
    source_path = _find_source(file_stem)
    if source_path is not None:
        source_path.unlink()

    md_path = OUT_DIR / f"{file_stem}.md"
    if md_path.exists():
        md_path.unlink()

    assets_dir = OUT_DIR / "assets" / file_stem
    if assets_dir.exists():
        shutil.rmtree(assets_dir)

    if REPORT_PATH.exists():
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        report["files"] = [e for e in report["files"] if _safe(Path(e["file"]).stem) != file_stem]
        report["totals"] = totals_from_entries(report["files"])
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        client = QdrantClient(url=QDRANT_URL)
        client.delete(
            collection_name=COLLECTION,
            points_selector=Filter(must=[FieldCondition(key="file_stem", match=MatchValue(value=file_stem))]),
        )
    except Exception:
        pass  # best-effort — local files are already gone; index cleanup can be retried by re-uploading

    with _jobs_lock:
        _jobs.pop(file_stem, None)

    _invalidate_bm25()
    db = SessionLocal()
    try:
        row = db.query(Document).filter(Document.file_stem == file_stem).one_or_none()
        if row:
            db.delete(row)
            db.commit()
    finally:
        db.close()


def rename_document(file_stem: str, name: str) -> dict:
    if _find_source(file_stem) is None:
        raise FileNotFoundError(file_stem)
    db = SessionLocal()
    try:
        row = db.query(Document).filter(Document.file_stem == file_stem).one_or_none()
        if row is None:
            raise FileNotFoundError(file_stem)
        row.display_name = name.strip() or row.display_name
        db.commit()
    finally:
        db.close()
    return next(d for d in list_documents() if d["id"] == file_stem)
