"""Glue upload -> extraction -> chunking -> embedding for one document at a time.

Backs the /api/documents/* routes in api/routes/documents.py. Each ingestion job runs on
a dedicated worker thread (not asyncio BackgroundTasks) so a slow Ruby/MTEF
subprocess or embedding-service HTTP call never blocks the chat SSE event loop.

Kho nhận quy trình kiểm định (QTKĐ) dạng Word/PDF. Mỗi tài liệu đi một đường:
trích Markdown, nhúng Qdrant. Tài liệu có mã QTKĐ trong đầu mục được nhận là
QTKĐ (kể cả khi tên tệp không nói vậy) và giữ dòng ``procedure`` của số đó để
router văn bản ghim đúng file. Mỗi số QTKĐ chỉ có MỘT phiên bản trong chỉ mục:
bản cũ hơn chuyển sang ``superseded`` (gỡ khỏi Qdrant, giữ tệp gốc + Markdown)
và được khôi phục khi bản mới bị xóa.
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from qdrant_client.http.exceptions import ResponseHandlingException

from core.settings_loader import REPO_ROOT, get_settings
from db import SessionLocal
from db.models import (
    Document,
    DocumentType,
    IngestStatus,
    Procedure,
)
from ingestion.chunker import parse_file
from ingestion.classify import classify_document
from ingestion.spike_a import _safe, process_one, totals_from_entries
from knowledge.procedure import ProcedureHeader, parse_procedure_header
from vectorstore import qdrant, upsert

# vectorstore.hybrid_index is imported lazily where used (see _invalidate_search_caches) -
# it requires rank_bm25, and retriever.py already avoids a hard module-level
# dependency on that package for the same reason.

# Connection failures from the embedding service (requests -> OSError subclass)
# and from Qdrant (its own ResponseHandlingException, NOT an OSError subclass)
# both mean "Docker isn't running" - treat them the same way for the user.
_CONNECTION_ERRORS = (OSError, ResponseHandlingException)


def _source_dir() -> Path:
    """Thư mục tài liệu QTKĐ nguồn; đọc settings tại thời điểm gọi."""
    return get_settings().paths.source_dir


def _out_dir() -> Path:
    """Thư mục Markdown + assets; đọc settings tại thời điểm gọi."""
    return get_settings().paths.markdown_dir


def _report_path() -> Path:
    """``extraction_report.json`` theo thư mục Markdown hiện hành."""
    return _out_dir() / "extraction_report.json"

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
    error: str | None = None


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


def _invalidate_search_caches(file_stems: set[str]) -> None:
    """Cập nhật BM25 cho các file vừa đổi và bỏ map số/alias của router.

    Best-effort - a stale cache is a search-quality issue, not a reason
    to fail an otherwise-successful embed or delete (also lets this work in
    environments where rank_bm25 isn't installed, same as retriever.py)."""
    try:
        from vectorstore.hybrid_index import refresh_files

        refresh_files(file_stems)
    except Exception:
        logger.warning("Không cập nhật được BM25 cho %s", sorted(file_stems), exc_info=True)
    from retrieval import router

    router.invalidate()


# Đuôi tệp được nhận khi upload: QTKĐ là văn bản Word/PDF; .doc cũ được K1 chuyển
# bằng LibreOffice rồi trích Markdown như .docx.
UPLOAD_EXTS = (".docx", ".doc", ".pdf")
# Đuôi tệp gốc có thể có trong kho (tìm/xem/xóa): gồm cả bảng tính đã nạp trước
# khi kho chỉ nhận QTKĐ.
SUPPORTED_EXTS = (*UPLOAD_EXTS, ".xlsx", ".xls")


def _find_source(file_stem: str) -> Path | None:
    """Locate the on-disk source file (.docx/.doc/.pdf/.xlsx/.xls) for a file_stem:
    its real filename may still carry spaces/original casing (pre-existing corpus
    files) while a freshly uploaded file is saved directly under its sanitized
    stem."""
    if not _source_dir().exists():
        return None
    for ext in SUPPORTED_EXTS:
        for f in _source_dir().glob(f"*{ext}"):
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
    """Validate + save an uploaded .docx/.doc/.pdf into TC_DL/. Returns its file_stem."""
    ext = Path(filename).suffix.lower()
    if ext not in UPLOAD_EXTS:
        raise UploadError("Chỉ hỗ trợ quy trình kiểm định dạng Word (.docx/.doc) hoặc PDF (.pdf).")
    if len(data) == 0:
        raise UploadError("Tệp rỗng.")
    max_bytes = get_settings().ingestion.max_upload_bytes
    if len(data) > max_bytes:
        raise UploadError(
            f"Tệp vượt quá dung lượng cho phép ({max_bytes // (1024 * 1024)} MB)."
        )
    digest = hashlib.sha256(data).hexdigest()

    _source_dir().mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        if db.query(Document).filter(Document.sha256 == digest).first() is not None:
            raise UploadError("Tài liệu đã tồn tại trong kho (trùng nội dung).")
    finally:
        db.close()
    stem = _safe(Path(filename).stem)
    candidate = stem
    n = 2
    while (_source_dir() / f"{candidate}{ext}").exists() or _find_source(candidate) is not None:
        candidate = f"{stem}_{n}"
        n += 1

    (_source_dir() / f"{candidate}{ext}").write_bytes(data)
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
        (_source_dir() / f"{candidate}{ext}").unlink(missing_ok=True)
        raise
    finally:
        db.close()
    return candidate


def _status_for(file_stem: str, ingest_status: IngestStatus) -> tuple[str, int, str | None]:
    job = _get_job(file_stem)
    if job is not None:
        if job.stage in _PROCESSING_STAGES:
            return "processing", job.progress, None
        if job.stage == "error":
            return "error", job.progress, job.error
        # stage == "ready" rơi xuống kiểm tra sổ + .md dưới đây.
    # Bản cũ vẫn giữ .md (để khôi phục), nên xét trạng thái sổ trước .md.
    if ingest_status == IngestStatus.SUPERSEDED:
        return "superseded", 100, None
    if (_out_dir() / f"{file_stem}.md").exists():
        return "ready", 100, None
    return "pending", 0, None


def list_documents() -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.query(Document).order_by(Document.uploaded_at.desc()).all()
        result = []
        for row in rows:
            status, progress, error = _status_for(row.file_stem, row.ingest_status)
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
                "progress": 100 if status_out in ("ready", "superseded") else progress,
                "error": error or row.ingest_error,
                "doc_type": row.doc_type.value,
                "sha256": row.sha256,
            })
        return result
    finally:
        db.close()


def get_markdown(file_stem: str) -> str | None:
    p = _out_dir() / f"{file_stem}.md"
    return p.read_text(encoding="utf-8") if p.exists() else None


def _read_report() -> dict:
    """Đọc extraction_report.json hiện có, trả report rỗng nếu chưa có."""
    path = _report_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    # Ghi tương đối gốc repo như spike_a ("TC_DL"): không lộ đường dẫn máy/container.
    source = _source_dir()
    if source.is_relative_to(REPO_ROOT):
        source = source.relative_to(REPO_ROOT)
    return {"source": str(source), "files": [], "totals": {}}


def _merge_report_entry(entry: dict) -> None:
    """Replace this file's entry in extraction_report.json and recompute totals
    without re-processing the rest of the corpus."""
    report = _read_report()
    report["files"] = [e for e in report["files"] if e["file"] != entry["file"]]
    report["files"].append(entry)
    report["totals"] = totals_from_entries(report["files"])
    _out_dir().mkdir(parents=True, exist_ok=True)
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
    """Chuyển .md + assets từ thư mục tạm sang _out_dir(), thay bản cũ."""
    _out_dir().mkdir(parents=True, exist_ok=True)
    md_dst = _out_dir() / f"{file_stem}.md"
    md_dst.unlink(missing_ok=True)
    tmp_md = tmp_dir / f"{file_stem}.md"
    if tmp_md.exists():
        shutil.move(str(tmp_md), str(md_dst))

    assets_src = tmp_dir / "assets" / file_stem
    if assets_src.exists():
        assets_dst = _out_dir() / "assets" / file_stem
        if assets_dst.exists():
            shutil.rmtree(assets_dst)
        assets_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(assets_src), str(assets_dst))


def _run_job(file_stem: str, source_path: Path) -> None:
    """Điều phối: trích Markdown rồi đưa vào chỉ mục."""
    _run_guarded(file_stem, lambda: _extract_and_index(file_stem, source_path))


def _restore_job(file_stem: str) -> None:
    """Đưa phiên bản cũ trở lại chỉ mục từ Markdown đã có (không trích lại)."""
    _run_guarded(file_stem, lambda: _index_markdown(file_stem, _out_dir() / f"{file_stem}.md"))


def _run_guarded(file_stem: str, work) -> None:
    """Chạy một job trên luồng worker: mọi lỗi thành trạng thái lỗi, không làm sập worker."""
    try:
        _set_db_status(file_stem, IngestStatus.PROCESSING)
        work()
    except _CONNECTION_ERRORS as e:
        _set_job(file_stem, "error", f"Không kết nối được dịch vụ embedding/Qdrant - kiểm tra Docker đã chạy chưa ({e}).")
        _set_db_status(file_stem, IngestStatus.ERROR, str(e))
    except Exception as e:  # noqa: BLE001 - surface any failure as a job error, never crash the worker thread
        _set_job(file_stem, "error", str(e))
        _set_db_status(file_stem, IngestStatus.ERROR, str(e))


def _extract_and_index(file_stem: str, source_path: Path) -> None:
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

    md_path = _out_dir() / f"{file_stem}.md"
    if md_path.exists():
        _register_formula_drafts(source_path, file_stem, entry, md_path)
    _index_markdown(file_stem, md_path)


def _register_formula_drafts(source_path: Path, file_stem: str, entry: dict, md_path: Path) -> None:
    """Tạo nháp công thức TRƯỚC khi nhúng: tài liệu lỗi embedding vẫn rà soát được.

    Chỉ tạo nháp chờ duyệt, không bao giờ tự phê duyệt hay tính.
    """
    from formula_registry.drafts import register_extraction

    try:
        source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        register_extraction(
            source_path, file_stem, source_hash, entry, md_path.read_text(encoding="utf-8")
        )
    except Exception as e:  # noqa: BLE001 - đổi tên lỗi để không bị coi là mất kết nối dịch vụ
        raise RuntimeError(f"Không tạo được nháp công thức: {e}") from e


def _index_markdown(file_stem: str, md_path: Path) -> None:
    """Nhận diện QTKĐ, chọn phiên bản, rồi chunk + nhúng Markdown vào Qdrant."""
    if not md_path.exists():
        raise RuntimeError("Không trích xuất được nội dung - tệp có thể bị lỗi hoặc rỗng.")
    text = md_path.read_text(encoding="utf-8")
    header = parse_procedure_header(text)

    newer = _classify_and_find_newer(file_stem, header)
    if newer is not None:
        # Bản cũ hơn bản đang dùng: không đưa vào chỉ mục (gỡ chunk của lần nhúng trước, nếu có).
        _supersede(file_stem, newer)
        _set_job(file_stem, "ready")
        _invalidate_search_caches({file_stem})
        return

    _set_job(file_stem, "chunking")
    chunks = parse_file(md_path)

    _set_job(file_stem, "embedding")
    client = qdrant.get_client()
    qdrant.ensure_collection(client)
    upsert.index_chunks(client, chunks)

    # Dòng ``procedure`` để router ghim đúng file. Lỗi ở bước này không làm hỏng
    # tài liệu đã nhúng; ghi lại để rà sau.
    touched = {file_stem}
    errors: list[str] = []
    try:
        replaced = _claim_procedure(file_stem, text)
    except Exception as e:  # noqa: BLE001 - best-effort, không chặn ingestion
        replaced = None
        errors.append(f"Tạo dòng procedure thất bại: {e}")
    if replaced is not None:
        _supersede(replaced, _display_name(file_stem))
        touched.add(replaced)

    _set_job(file_stem, "ready")
    _set_db_status(file_stem, IngestStatus.READY, "; ".join(errors) if errors else None)
    _invalidate_search_caches(touched)


def _classify_and_find_newer(file_stem: str, header: ProcedureHeader | None) -> str | None:
    """Nhận tài liệu là QTKĐ theo đầu mục; trả tên phiên bản mới hơn nếu tài liệu là bản cũ.

    Tên tệp không nhắc "QTKĐ" thì lúc upload tài liệu rơi vào ``khac``; nội dung
    có mã QTKĐ ở đầu mục mới là bằng chứng chắc chắn. Chỉ nâng ``khac`` → ``qtkd``,
    không đổi loại đã nhận rõ khác (biên bản thường nhắc QTKĐ trong nội dung).
    """
    from knowledge.procedure import newer_version_document_id

    if header is None:
        return None
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.file_stem == file_stem).one_or_none()
        if document is None:
            return None
        if document.doc_type == DocumentType.KHAC:
            document.doc_type = DocumentType.QTKD
            db.commit()
        if document.doc_type != DocumentType.QTKD:
            return None
        newer_id = newer_version_document_id(db, document, header)
        if newer_id is None:
            return None
        newer = db.get(Document, newer_id)
        return newer.display_name if newer is not None else None
    finally:
        db.close()


def _claim_procedure(file_stem: str, text: str) -> str | None:
    """Gán dòng ``procedure`` cho tài liệu QTKĐ; trả file_stem phiên bản cũ vừa bị thay.

    Chỉ chạy cho loại ``qtkd``. Dùng procedure đã có nếu trùng ``document_id``;
    nếu chưa, dựng từ đầu mục Markdown để giữ liên kết P1.
    """
    from knowledge.procedure import ensure_procedure
    from knowledge.reference import procedure_by_number

    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.file_stem == file_stem).one_or_none()
        if document is None or document.doc_type != DocumentType.QTKD:
            return None
        header = parse_procedure_header(text)
        current = procedure_by_number(db, header.number) if header is not None else None
        previous_id = current.document_id if current is not None else None
        procedure = ensure_procedure(db, document, text)
        db.commit()
        if procedure is None or previous_id in (None, document.id):
            return None
        previous = db.get(Document, previous_id)
        return previous.file_stem if previous is not None else None
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _supersede(file_stem: str, newer_name: str) -> None:
    """Gỡ một phiên bản cũ khỏi chỉ mục; tệp gốc và Markdown giữ lại để khôi phục."""
    qdrant.delete_file_chunks(qdrant.get_client(), file_stem)
    _set_db_status(file_stem, IngestStatus.SUPERSEDED, f"Đã có phiên bản mới hơn: {newer_name}")


def _display_name(file_stem: str) -> str:
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.file_stem == file_stem).one_or_none()
        return document.display_name if document is not None else file_stem
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
    """Xoá một tài liệu: bước CSDL TRƯỚC, rồi mới tới tệp, Markdown, report và Qdrant.

    Xoá phiên bản hiện hành của một QTKĐ thì phiên bản cũ mới nhất còn lại được
    đưa trở lại chỉ mục, để số QTKĐ đó không mất khỏi kho.
    """
    number = _delete_document_rows(file_stem)
    from formula_registry.store import Registry

    # Nguồn mất thì nháp/công thức đã duyệt của tài liệu hết hiệu lực (chặn tính).
    Registry().invalidate(file_stem)
    source_path = _find_source(file_stem)
    if source_path is not None:
        source_path.unlink()

    md_path = _out_dir() / f"{file_stem}.md"
    if md_path.exists():
        md_path.unlink()

    assets_dir = _out_dir() / "assets" / file_stem
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
        pass  # best-effort - local files are already gone; index cleanup can be retried by re-uploading

    with _jobs_lock:
        _jobs.pop(file_stem, None)

    _invalidate_search_caches({file_stem})

    successor = _latest_superseded_version(number) if number is not None else None
    if successor is not None:
        _set_job(successor, "queued")
        _executor.submit(_restore_job, successor)


def _delete_document_rows(file_stem: str) -> str | None:
    """Xoá hàng ``document`` cùng dòng ``procedure`` của nó, trong một transaction.

    Hàng duy nhất trỏ tới tài liệu là ``procedure`` (khoá ngoại nullable); xoá
    tài liệu kèm procedure để không còn dòng mồ côi. Trả số QTKĐ tài liệu đang
    giữ (nếu có), để tìm phiên bản cũ thay thế.
    """
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.file_stem == file_stem).one_or_none()
        if doc is None:
            return None
        number = None
        for row in db.query(Procedure).filter(Procedure.document_id == doc.id).all():
            number = row.number
            db.delete(row)
        db.delete(doc)
        db.commit()
        return number
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _latest_superseded_version(number: str) -> str | None:
    """file_stem của phiên bản cũ mới nhất (năm lớn nhất, rồi tải lên sau) của số QTKĐ."""
    db = SessionLocal()
    try:
        rows = (
            db.query(Document)
            .filter(Document.ingest_status == IngestStatus.SUPERSEDED)
            .order_by(Document.uploaded_at)
            .all()
        )
        best: tuple[int, str] | None = None
        for row in rows:
            md_path = _out_dir() / f"{row.file_stem}.md"
            if not md_path.exists():
                continue
            header = parse_procedure_header(md_path.read_text(encoding="utf-8"))
            if header is None or header.number != number:
                continue
            candidate = (header.year or 0, row.file_stem)
            if best is None or candidate[0] >= best[0]:
                best = candidate
        return best[1] if best is not None else None
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
