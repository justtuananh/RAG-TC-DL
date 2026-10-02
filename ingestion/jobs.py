"""Glue upload -> extraction -> chunking -> embedding for one document at a time.

Backs the /api/documents/* routes in api_server.py. Each ingestion job runs on
a dedicated worker thread (not asyncio BackgroundTasks) so a slow Ruby/MTEF
subprocess or embedding-service HTTP call never blocks the chat SSE event loop.

Tài liệu QTKĐ (.docx/.pdf) đi đường trích Markdown + nhúng Qdrant. Hồ sơ kiểm
định (.xlsx/.docx loại ``ho_so_kiem_dinh``/``phieu_do``) KHÔNG nhúng vào kho văn
bản: bước "Xử lý" gọi ``records.ingest`` để ghi bản ghi chờ duyệt.
"""
from __future__ import annotations

import json
import hashlib
import logging
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from qdrant_client.http.exceptions import ResponseHandlingException

# Connection failures from the embedding service (requests -> OSError subclass)
# and from Qdrant (its own ResponseHandlingException, NOT an OSError subclass)
# both mean "Docker isn't running" — treat them the same way for the user.
_CONNECTION_ERRORS = (OSError, ResponseHandlingException)

from ingestion.chunker import parse_file
from vectorstore import qdrant, upsert
from ingestion.spike_a import _safe, process_one, totals_from_entries
from ingestion.classify import classify_document
from db import SessionLocal
from db.models import Document, DocumentType, IngestStatus

# vectorstore.hybrid_index is imported lazily where used (see invalidate_bm25) —
# it requires rank_bm25, and retriever.py already avoids a hard module-level
# dependency on that package for the same reason.

TC_DL_DIR = Path("TC_DL")
OUT_DIR = Path("build/spike_a")


def _report_path() -> Path:
    """``extraction_report.json`` theo OUT_DIR hiện hành (test thay OUT_DIR được)."""
    return OUT_DIR / "extraction_report.json"

MAX_UPLOAD_BYTES = 50 * 1024 * 1024

_PROCESSING_STAGES = {"queued", "extracting", "reading_record", "chunking", "embedding"}
_STAGE_PROGRESS = {
    "queued": 5,
    "extracting": 35,
    "reading_record": 55,
    "chunking": 60,
    "embedding": 85,
    "ready": 100,
}

# Loại tài liệu đi đường ghi hồ sơ, không đi đường trích Markdown + nhúng Qdrant.
_RECORD_DOC_TYPES = frozenset({DocumentType.HO_SO_KIEM_DINH, DocumentType.PHIEU_DO})


class UploadError(ValueError):
    """User-facing validation error for an upload (bad extension, too large, empty)."""


@dataclass
class Job:
    stage: str  # "queued" | "extracting" | "reading_record" | "chunking" | "embedding" | "ready" | "error"
    progress: int
    error: Optional[str] = None
    result: Optional[dict] = None  # StoreResult.as_dict() cho job hồ sơ


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1)

logger = logging.getLogger(__name__)


def _set_job(file_stem: str, stage: str, error: str | None = None, result: dict | None = None) -> None:
    with _jobs_lock:
        prev = _jobs.get(file_stem)
        progress = _STAGE_PROGRESS[stage] if stage in _STAGE_PROGRESS else (prev.progress if prev else 0)
        _jobs[file_stem] = Job(stage=stage, progress=progress, error=error, result=result)


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
        from vectorstore.hybrid_index import invalidate
        invalidate()
    except Exception:
        pass


# Đuôi tệp được nhận khi upload + tìm tệp gốc. Gồm .xlsx vì hồ sơ kiểm định
# (biên bản/phiếu đo) cũng vào sổ tài liệu rồi đi đường ``records.ingest``; gồm
# .doc/.xls cũ vì K1 chuyển bằng LibreOffice rồi trích Markdown như QTKĐ.
SUPPORTED_EXTS = (".docx", ".doc", ".pdf", ".xlsx", ".xls")


def _find_source(file_stem: str) -> Path | None:
    """Locate the on-disk source file (.docx/.doc/.pdf/.xlsx/.xls) for a file_stem:
    its real filename may still carry spaces/original casing (pre-existing corpus
    files) while a freshly uploaded file is saved directly under its sanitized
    stem."""
    if not TC_DL_DIR.exists():
        return None
    for ext in SUPPORTED_EXTS:
        for f in TC_DL_DIR.glob(f"*{ext}"):
            if _safe(f.stem) == file_stem:
                return f
    return None


def get_source_path(file_stem: str) -> Path | None:
    """Public accessor for the on-disk original (.docx/.doc/.pdf/.xlsx/.xls): used
    to serve the raw file back to the frontend (as opposed to its extracted Markdown)."""
    return _find_source(file_stem)


def get_preview_path(file_stem: str) -> Path | None:
    """Bản xem được trên trình duyệt của tệp gốc: .doc/.xls cũ trả bản .docx/.xlsx
    đã chuyển bằng LibreOffice (cache ``build/converted``, chuyển nếu chưa có); định
    dạng khác trả chính tệp gốc. ``None`` nếu không có tệp gốc.

    Ném ``convert_legacy.ConvertLegacyError`` khi không chuyển đổi được."""
    from ingestion import convert_legacy

    path = _find_source(file_stem)
    if path is None or path.suffix.lower() not in convert_legacy.TARGET_EXT:
        return path
    cached = convert_legacy.cache_path(path)
    return cached if cached.exists() else convert_legacy.convert_legacy(path)


def save_upload(filename: str, data: bytes, uploaded_by: int | None = None) -> str:
    """Validate + save an uploaded .docx/.doc/.pdf/.xlsx/.xls into TC_DL/. Returns its file_stem."""
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise UploadError(
            "Chỉ hỗ trợ tệp Word (.docx/.doc), Excel (.xlsx/.xls) hoặc PDF (.pdf)."
        )
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


def _status_for(file_stem: str) -> tuple[str, int, str | None, dict | None]:
    job = _get_job(file_stem)
    if job is not None:
        if job.stage in _PROCESSING_STAGES:
            return "processing", job.progress, None, None
        if job.stage == "error":
            return "error", job.progress, job.error, None
        # Job hồ sơ xong: trạng thái ready đến từ kết quả ghi, không có .md.
        if job.stage == "ready" and job.result is not None:
            return "ready", 100, None, job.result
        # job.stage == "ready" của tài liệu QTKĐ falls through to the file check below
    if (OUT_DIR / f"{file_stem}.md").exists():
        return "ready", 100, None, None
    return "pending", 0, None, None


def list_documents() -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.query(Document).order_by(Document.uploaded_at.desc()).all()
        result = []
        for row in rows:
            status, progress, error, job_result = _status_for(row.file_stem)
            # Tài liệu READY trong sổ nhưng job đã mất sau khi API khởi động lại.
            status_out = status if status != "pending" or row.ingest_status.value == "pending" else row.ingest_status.value
            result.append({
                "id": row.file_stem,
                "name": row.display_name,
                "ext": row.ext,
                "size": _human_size(row.size_bytes),
                "pages": None,
                "date": row.uploaded_at.strftime("%d/%m/%Y"),
                "status": status_out,
                "progress": 100 if status_out == "ready" else progress,
                "error": error or row.ingest_error,
                "doc_type": row.doc_type.value,
                "sha256": row.sha256,
                "result": job_result,
            })
        return result
    finally:
        db.close()


def get_markdown(file_stem: str) -> str | None:
    p = OUT_DIR / f"{file_stem}.md"
    return p.read_text(encoding="utf-8") if p.exists() else None


def _read_report() -> dict:
    """Đọc extraction_report.json hiện có, trả report rỗng nếu chưa có."""
    path = _report_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"source": str(TC_DL_DIR), "files": [], "totals": {}}


def _merge_report_entry(entry: dict) -> None:
    """Replace this file's entry in extraction_report.json and recompute totals
    without re-processing the rest of the corpus."""
    report = _read_report()
    report["files"] = [e for e in report["files"] if e["file"] != entry["file"]]
    report["files"].append(entry)
    report["totals"] = totals_from_entries(report["files"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _report_path().write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _old_entry(entry: dict) -> dict | None:
    """Entry cũ cùng tên tệp trong extraction_report.json (None nếu chưa có)."""
    for old in _read_report()["files"]:
        if old.get("file") == entry.get("file"):
            return old
    return None


def _fmt_pct(rate: float | None) -> str:
    """0.095 -> '9,5' (dấu thập phân tiếng Việt, bỏ ',0' thừa)."""
    text = f"{rate * 100:.1f}".replace(".", ",")
    return text[:-2] if text.endswith(",0") else text


def _regression_message(new_entry: dict, old_entry: dict) -> str | None:
    """Thông báo tiếng Việt nếu bản mới làm giảm độ trung thực công thức, else None.

    Rủi ro #1 của dự án: không bao giờ để một lần trích lỗi (thiếu gem Ruby)
    ghi đè bản Markdown đã kiểm chứng. Chặn khi tỉ lệ chuyển THẤP HƠN hoặc số
    công thức chuyển được ÍT HƠN bản cũ.
    """
    new = totals_from_entries([new_entry])
    old = totals_from_entries([old_entry])
    new_ok, old_ok = new["formulas_latex_total"], old["formulas_latex_total"]
    new_rate, old_rate = new["latex_rate_total"], old["latex_rate_total"]
    if new_ok >= old_ok and (new_rate is None or old_rate is None or new_rate >= old_rate):
        return None
    if new_rate is not None and old_rate is not None:
        detail = f"{_fmt_pct(old_rate)} % xuống {_fmt_pct(new_rate)} %"
    else:
        detail = f"{old_ok} xuống {new_ok} công thức"
    return (
        f"Trích xuất mới làm giảm tỉ lệ chuyển công thức ({detail}); "
        "giữ nguyên bản đã kiểm chứng. Kiểm tra cài đặt Ruby gem mathtype_to_mathml và pry."
    )


def _publish_extraction(tmp_dir: Path, file_stem: str) -> None:
    """Chuyển .md + assets từ thư mục tạm sang OUT_DIR, thay bản cũ."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md_dst = OUT_DIR / f"{file_stem}.md"
    md_dst.unlink(missing_ok=True)
    tmp_md = tmp_dir / f"{file_stem}.md"
    if tmp_md.exists():
        shutil.move(str(tmp_md), str(md_dst))

    assets_src = tmp_dir / "assets" / file_stem
    if assets_src.exists():
        assets_dst = OUT_DIR / "assets" / file_stem
        if assets_dst.exists():
            shutil.rmtree(assets_dst)
        assets_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(assets_src), str(assets_dst))


def _document_doc_type(file_stem: str) -> DocumentType | None:
    """Loại tài liệu trong sổ (None nếu chưa có dòng nào)."""
    db = SessionLocal()
    try:
        row = db.query(Document).filter(Document.file_stem == file_stem).one_or_none()
        return row.doc_type if row is not None else None
    finally:
        db.close()


def _run_job(file_stem: str, source_path: Path) -> None:
    """Điều phối: hồ sơ kiểm định ghi bản ghi, còn lại trích Markdown + nhúng."""
    if _document_doc_type(file_stem) in _RECORD_DOC_TYPES:
        _run_record_job(file_stem)
    else:
        _run_markdown_job(file_stem, source_path)


def _run_record_job(file_stem: str) -> None:
    """Đọc hồ sơ thành bản ghi chờ duyệt: KHÔNG trích Markdown, KHÔNG nhúng Qdrant.

    ``records.ingest`` tự nhận QTKĐ từ nội dung hồ sơ rồi dựng cấu hình từ Phụ
    lục A đã duyệt (P3). Lỗi nghiệp vụ (thiếu cấu hình, thiếu QTKĐ) hiện nguyên
    văn trên UI; lỗi khác đi nhánh chung.
    """
    from records.ingest import IngestError, ingest_file_stem
    from records.template import TemplateError

    try:
        _set_db_status(file_stem, IngestStatus.PROCESSING)
        _set_job(file_stem, "reading_record")
        result = ingest_file_stem(file_stem)
        payload = result.as_dict()
        _set_job(file_stem, "ready", result=payload)
        _set_db_status(file_stem, IngestStatus.READY)
    except (IngestError, TemplateError) as e:
        _set_job(file_stem, "error", str(e))
        _set_db_status(file_stem, IngestStatus.ERROR, str(e))
    except Exception as e:  # noqa: BLE001 - surface any failure as a job error, never crash the worker thread
        _set_job(file_stem, "error", str(e))
        _set_db_status(file_stem, IngestStatus.ERROR, str(e))


def _run_markdown_job(file_stem: str, source_path: Path) -> None:
    try:
        _set_db_status(file_stem, IngestStatus.PROCESSING)
        _set_job(file_stem, "extracting")
        # B10: trích vào thư mục tạm trước, chỉ công bố nếu không làm giảm
        # độ trung thực công thức so với bản đã kiểm chứng trong report.
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"ingest_{file_stem}_"))
        try:
            entry = process_one(source_path, tmp_dir)
            old = _old_entry(entry)
            if old is not None:
                message = _regression_message(entry, old)
                if message is not None:
                    raise RuntimeError(message)
            _publish_extraction(tmp_dir, file_stem)
            _merge_report_entry(entry)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        md_path = OUT_DIR / f"{file_stem}.md"
        if not md_path.exists():
            raise RuntimeError("Không trích xuất được nội dung — tệp có thể bị lỗi hoặc rỗng.")

        _set_job(file_stem, "chunking")
        chunks = parse_file(md_path)

        _set_job(file_stem, "embedding")
        client = qdrant.get_client()
        qdrant.ensure_collection(client)
        upsert.index_chunks(client, chunks)
        _invalidate_bm25()

        # Sprint 4: sau khi nhúng, trích xuất tri thức cho QTKĐ (trạng thái pending).
        # Lỗi trích xuất không làm hỏng tài liệu đã nhúng; ghi lại để rà sau.
        errors: list[str] = []
        try:
            _run_extraction(file_stem, md_path)
        except Exception as e:  # noqa: BLE001 - best-effort, không chặn ingestion
            errors.append(f"Trích xuất tri thức thất bại: {e}")

        # Pha D1: tài liệu danh mục có thể chứa bảng NAS (chuẩn mẫu, KĐV, quy
        # trình, lĩnh vực). Không phải mọi danh mục đều có bảng NAS nên
        # ``CatalogError`` được bỏ qua; lỗi khác ghi vào ``ingest_error``.
        catalog_result: dict | None = None
        if _document_doc_type(file_stem) == DocumentType.DANH_MUC:
            try:
                catalog_result = _run_catalog(file_stem, source_path)
            except Exception as e:  # noqa: BLE001 - best-effort, không chặn ingestion
                errors.append(f"Đọc danh mục NAS thất bại: {e}")

        _set_job(file_stem, "ready", result=catalog_result)
        _set_db_status(file_stem, IngestStatus.READY, "; ".join(errors) if errors else None)
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


def _run_catalog(file_stem: str, source_path: Path) -> dict | None:
    """Đọc bảng danh mục NAS của tài liệu loại ``danh_muc`` và ghi ``pending``.

    Bản ``.doc``/``.xls`` dùng bản chuyển đổi trong ``build/converted`` (K1); bản
    ``.docx``/``.xlsx`` đọc thẳng. Trả ``None`` khi tệp không chứa bảng NAS
    (``CatalogError``) hoặc định dạng không đọc được; lỗi khác để tầng gọi ghi vào
    ``ingest_error`` như bước trích tri thức.
    """
    from catalogs.readers import CatalogError, read_catalog
    from catalogs.store import store_catalog_draft
    from ingestion import convert_legacy

    suffix = source_path.suffix.lower()
    if suffix not in (".doc", ".docx", ".xls", ".xlsx"):
        return None
    path = source_path
    if suffix in (".doc", ".xls"):
        path = convert_legacy.cache_path(source_path)
        if not path.exists():
            path = convert_legacy.convert_legacy(source_path)
    try:
        draft = read_catalog(path)
    except CatalogError:
        return None

    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.file_stem == file_stem).one_or_none()
        if document is None:
            return None
        summary = store_catalog_draft(db, document=document, draft=draft)
        db.commit()
        return summary
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

    if _report_path().exists():
        report = _read_report()
        report["files"] = [e for e in report["files"] if _safe(Path(e["file"]).stem) != file_stem]
        report["totals"] = totals_from_entries(report["files"])
        _report_path().write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        qdrant.delete_file_chunks(qdrant.get_client(), file_stem)
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
