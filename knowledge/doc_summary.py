"""Tóm tắt tài liệu: LLM viết nháp lúc nạp, người duyệt phê duyệt, chat chỉ dùng bản đã duyệt.

Vòng đời một bản tóm tắt (bảng ``document_summary``)::

    generating → draft → approved
                   ↘ rejected      (sửa lại → draft; sinh lại → draft)
    generating → error             (LLM/Ollama lỗi; sinh lại được)

LLM chỉ đọc văn bản của chính tài liệu (từ mục 1 trở đi, công thức thay bằng "[công thức]").
Số liệu trong bản tóm tắt không tìm thấy trong tài liệu được ghi vào ``warnings`` để người duyệt
đối chiếu. Tài liệu xử lý lại mà Markdown đổi thì bản tóm tắt cũ, kể cả đã duyệt, bị viết lại
thành nháp mới: bản đã duyệt luôn khớp đúng phiên bản tài liệu đang được tìm kiếm.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.settings_loader import get_settings
from db.models import AppUser, Document, DocumentSummary, IngestStatus, SummaryStatus
from retrieval import doc_profile

log = logging.getLogger(__name__)

_SETTLED = {SummaryStatus.DRAFT.value, SummaryStatus.APPROVED.value, SummaryStatus.REJECTED.value}
_FIRST_SECTION_RE = re.compile(r"^#{1,3}\s*1\.?\s+\S", re.MULTILINE)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_DISPLAY_MATH_RE = re.compile(r"\$\$.+?\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"\$[^$\n]{30,}\$")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_FENCE_RE = re.compile(r"^```[a-z]*\s*|\s*```$")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_DIGIT_GROUP_RE = re.compile(r"(?<=\d)[ \u00a0\u202f](?=\d{3}\b)")
_FORMULA = "[công thức]"

SYSTEM_PROMPT = """Bạn tóm tắt một quy trình kiểm định (QTKĐ) hoặc tiêu chuẩn đo lường cho kỹ thuật viên.
Chỉ dùng thông tin có trong văn bản được cung cấp.
Quy tắc:
- Không thêm thông tin, số liệu, tên thiết bị hay tên tài liệu không có trong văn bản.
- Giữ nguyên số liệu, đơn vị và kiểu thiết bị như trong văn bản.
- Không viết công thức.
- Viết tiếng Việt, 4 đến 8 gạch đầu dòng, mỗi dòng dạng "- **Tên ý:** nội dung", theo thứ tự các ý: Đối tượng và phạm vi; Các phép kiểm định chính; Phương tiện kiểm định; Điều kiện kiểm định; Yêu cầu kỹ thuật chính; Chu kỳ kiểm định.
- Văn bản không nêu ý nào thì bỏ ý đó. Với tiêu chuẩn, dùng các ý: Phạm vi; Các nhóm yêu cầu chính; Đối tượng áp dụng.
- Không viết lời mở đầu hay kết luận."""


class SummaryError(Exception):
    """Lỗi nghiệp vụ của bản tóm tắt; ``status`` là mã HTTP tương ứng cho tầng API."""

    status = 422


class NotFound(SummaryError):
    status = 404


class Conflict(SummaryError):
    status = 409


# ── Dựng prompt ───────────────────────────────────────────────────────────────


def source_excerpt(markdown: str, max_chars: int) -> str:
    """Văn bản đưa cho LLM: từ mục 1 trở đi, bỏ hình, thay công thức dài, cắt ở ranh giới dòng."""
    match = _FIRST_SECTION_RE.search(markdown)
    text = markdown[match.start():] if match else markdown
    text = _IMAGE_RE.sub("", text)
    text = _DISPLAY_MATH_RE.sub(_FORMULA, text)
    text = _INLINE_MATH_RE.sub(_FORMULA, text)
    text = _BLANK_LINES_RE.sub("\n\n", text).strip()
    if len(text) <= max_chars:
        return text
    cut = text.rfind("\n", 0, max_chars)
    return text[: cut if cut > 0 else max_chars].rstrip()


def build_messages(profile: doc_profile.DocProfile, excerpt: str) -> list[dict]:
    toc = "\n".join(f"- {s.label}" for s in profile.sections if s.level == 1)
    title = f"{profile.label} - {profile.title}" if profile.title else profile.label
    user = f"Tài liệu: {title}\n\nCác mục chính:\n{toc or '(không có)'}\n\nVăn bản:\n{excerpt}"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def clean_output(text: str) -> str:
    return _FENCE_RE.sub("", text.strip()).strip()


def _plain_numbers(text: str) -> str:
    return _DIGIT_GROUP_RE.sub("", text).replace(",", ".")


def number_warnings(summary: str, source: str) -> list[str]:
    """Số liệu trong bản tóm tắt không xuất hiện trong tài liệu (so sau khi bỏ dấu cách nghìn, đổi , → .)."""
    known = set(_NUMBER_RE.findall(_plain_numbers(source)))
    missing: list[str] = []
    for number in _NUMBER_RE.findall(_plain_numbers(summary)):
        if number not in known and number not in missing:
            missing.append(number)
    return [f"Số liệu không thấy trong tài liệu: {n}" for n in missing]


# ── Truy cập CSDL ─────────────────────────────────────────────────────────────


def _session() -> Session:
    from db import SessionLocal

    return SessionLocal()


def _markdown_path(file_stem: str) -> Path:
    return Path(get_settings().paths.markdown_dir) / f"{file_stem}.md"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _current_sha(file_stem: str) -> str | None:
    path = _markdown_path(file_stem)
    return _sha256(path.read_text(encoding="utf-8")) if path.exists() else None


def _is_stale(row: DocumentSummary, current_sha: str | None) -> bool:
    """Bản tóm tắt không còn khớp Markdown đang được tìm kiếm (tài liệu đã xử lý lại hoặc mất Markdown)."""
    return current_sha is None or row.source_sha256 != current_sha


def _document(db: Session, file_stem: str) -> Document:
    document = db.query(Document).filter(Document.file_stem == file_stem).one_or_none()
    if document is None:
        raise NotFound("Không tìm thấy tài liệu.")
    return document


def _row(db: Session, document: Document) -> DocumentSummary | None:
    return db.query(DocumentSummary).filter(DocumentSummary.document_id == document.id).one_or_none()


def _user_label(user: AppUser | None) -> str | None:
    if user is None:
        return None
    return f"{user.full_name} ({user.username})" if user.full_name else user.username


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def _snapshot(row: DocumentSummary, file_stem: str) -> dict:
    current = _current_sha(file_stem)
    return {
        "document_id": file_stem,
        "status": row.status,
        "text": row.text or "",
        "generated_text": row.generated_text or "",
        "warnings": list(row.warnings or []),
        "model": row.model,
        "error": row.error,
        "revision": row.revision,
        "generated_at": _iso(row.generated_at),
        "edited_by": _user_label(row.editor),
        "edited_at": _iso(row.edited_at),
        "reviewed_by": _user_label(row.reviewer),
        "reviewed_at": _iso(row.reviewed_at),
        "review_note": row.review_note,
        "stale": bool(row.source_sha256 and current and row.source_sha256 != current),
    }


def get(file_stem: str) -> dict | None:
    db = _session()
    try:
        row = _row(db, _document(db, file_stem))
        return _snapshot(row, file_stem) if row is not None else None
    finally:
        db.close()


def is_queued(file_stem: str) -> bool:
    """Tài liệu đang chờ hoặc đang được sinh tóm tắt trên luồng nền của tiến trình này.

    Dòng ``generating`` mà không còn trong hàng đợi là lần sinh bị gián đoạn (máy chủ khởi động lại
    giữa chừng): giao diện cho sinh lại thay vì chờ mãi.
    """
    with _pending_lock:
        return file_stem in _pending


def check_can_generate(file_stem: str) -> None:
    """Điều kiện để xếp hàng sinh tóm tắt; lỗi trả ngay cho người bấm thay vì hỏng ngầm trên luồng nền."""
    if not get_settings().doc_summary.enabled:
        raise Conflict("Tính năng tóm tắt tài liệu đang tắt trong cấu hình.")
    db = _session()
    try:
        document = _document(db, file_stem)
        if document.ingest_status != IngestStatus.READY:
            raise Conflict("Chỉ sinh tóm tắt cho tài liệu đã xử lý xong và đang được tìm kiếm.")
    finally:
        db.close()
    if not _markdown_path(file_stem).exists():
        raise NotFound("Tài liệu chưa được xử lý nên chưa có nội dung để tóm tắt.")


def approved_text(file_stem: str) -> str | None:
    """Bản tóm tắt đã duyệt (chat dùng); ``None`` nếu chưa có hoặc CSDL không đọc được.

    Chat không bao giờ hỏng vì không đọc được bản tóm tắt: lỗi CSDL / kết nối chỉ ghi log,
    câu hỏi rơi về câu trả lời trích phạm vi nguyên văn.
    """
    db = None
    try:
        db = _session()
        row = (
            db.query(DocumentSummary)
            .join(Document, Document.id == DocumentSummary.document_id)
            .filter(Document.file_stem == file_stem)
            .one_or_none()
        )
        if row is None or row.status != SummaryStatus.APPROVED.value or not (row.text or "").strip():
            return None
        if _is_stale(row, _current_sha(file_stem)):
            return None  # tài liệu đã xử lý lại: bản đã duyệt không còn chắc khớp nội dung
        return row.text.strip()
    except Exception as e:  # noqa: BLE001 - xem docstring
        log.warning("Không đọc được tóm tắt %s: %s", file_stem, e)
        return None
    finally:
        if db is not None:
            db.close()


def delete_for(db: Session, document_id: str) -> None:
    """Xoá bản tóm tắt của tài liệu trong transaction của nơi gọi (SQLite không tự CASCADE)."""
    db.query(DocumentSummary).filter(DocumentSummary.document_id == document_id).delete()


# ── Sinh bản tóm tắt ──────────────────────────────────────────────────────────


def _call_llm(messages: list[dict]) -> str:
    from llm.generator import chat_once

    cfg = get_settings().doc_summary
    return chat_once(messages, num_predict=cfg.max_new_tokens, timeout_s=cfg.timeout_s)


def _claim(file_stem: str, sha: str, force: bool) -> bool:
    """Đánh dấu ``generating``; ``False`` khi bản hiện có đã khớp đúng Markdown này (không cần sinh lại)."""
    db = _session()
    try:
        document = _document(db, file_stem)
        row = _row(db, document)
        if row is None:
            row = DocumentSummary(document_id=document.id, revision=1, warnings=[])
            db.add(row)
        elif not force and row.source_sha256 == sha and row.status in _SETTLED:
            return False
        else:
            row.revision += 1
        row.status = SummaryStatus.GENERATING.value
        row.error = None
        db.commit()
        return True
    except IntegrityError as e:  # tiến trình khác (CLI) vừa tạo dòng cho cùng tài liệu
        db.rollback()
        raise Conflict("Bản tóm tắt của tài liệu này đang được sinh ở nơi khác.") from e
    finally:
        db.close()


def _store(file_stem: str, apply: Callable[[DocumentSummary], None]) -> dict:
    db = _session()
    try:
        row = _row(db, _document(db, file_stem))
        if row is None:
            raise NotFound("Tài liệu chưa có bản tóm tắt.")
        apply(row)
        row.revision += 1
        db.commit()
        db.refresh(row)
        return _snapshot(row, file_stem)
    finally:
        db.close()


def generate(file_stem: str, *, force: bool = False) -> dict:
    """Sinh (đồng bộ) bản tóm tắt nháp. Bỏ qua khi bản hiện có đã khớp Markdown, trừ khi ``force``."""
    path = _markdown_path(file_stem)
    if not path.exists():
        raise NotFound("Tài liệu chưa được xử lý nên chưa có nội dung để tóm tắt.")
    markdown = path.read_text(encoding="utf-8")
    sha = _sha256(markdown)
    if not _claim(file_stem, sha, force):
        return get(file_stem)

    cfg = get_settings()
    try:
        profile = doc_profile.build_profile(file_stem, markdown, cfg.doc_profile.max_scope_chars)
        excerpt = source_excerpt(markdown, cfg.doc_summary.max_input_chars)
        summary = clean_output(_call_llm(build_messages(profile, excerpt)))
        if not summary:
            raise RuntimeError("LLM trả về bản tóm tắt rỗng.")
    except Exception as e:  # noqa: BLE001 - mọi lỗi sinh đều thành trạng thái error để người dùng sinh lại
        log.warning("Sinh tóm tắt %s thất bại: %s", file_stem, e)
        message = str(e) or type(e).__name__

        def failed(row: DocumentSummary) -> None:
            row.status = SummaryStatus.ERROR.value
            row.error = message

        return _store(file_stem, failed)

    def drafted(row: DocumentSummary) -> None:
        row.status = SummaryStatus.DRAFT.value
        row.text = row.generated_text = summary
        row.warnings = number_warnings(summary, markdown)
        row.source_sha256 = sha
        row.model = cfg.llm_model("chat")
        row.generated_at = datetime.utcnow()
        row.edited_by = row.edited_at = None
        row.reviewed_by = row.reviewed_at = row.review_note = None

    return _store(file_stem, drafted)


_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="doc-summary")
# stem đang chờ/đang sinh → yêu cầu chạy lại đến trong lúc đó: None = không có, bool = cờ ``force`` của lần chạy lại.
_pending: dict[str, bool | None] = {}
_pending_lock = threading.Lock()


def _run_queued(file_stem: str, force: bool) -> None:
    try:
        generate(file_stem, force=force)
    except Exception:  # noqa: BLE001 - luồng nền: ghi log, không làm sập worker
        log.exception("Sinh tóm tắt %s thất bại", file_stem)
    finally:
        with _pending_lock:
            rerun = _pending.get(file_stem)
            if rerun is None:
                _pending.pop(file_stem, None)
            else:
                _pending[file_stem] = None
        if rerun is not None:
            _submit(file_stem, rerun)


def _submit(file_stem: str, force: bool) -> None:
    _executor.submit(_run_queued, file_stem, force)


def queue(file_stem: str, *, force: bool = False) -> bool:
    """Xếp hàng sinh tóm tắt trên luồng nền (một LLM, một việc mỗi lúc).

    Tài liệu đang chờ hoặc đang sinh thì không chạy song song: yêu cầu mới được ghi lại và chạy ngay
    sau lần hiện tại (gộp cờ ``force``), để Markdown vừa xử lý lại không bao giờ bị bỏ sót. Trả ``True``
    khi xếp hàng mới, ``False`` khi gộp vào lần đang chờ.
    """
    with _pending_lock:
        if file_stem in _pending:
            _pending[file_stem] = bool(_pending[file_stem]) or force
            return False
        _pending[file_stem] = None
    _submit(file_stem, force)
    return True


# ── Sửa và duyệt ──────────────────────────────────────────────────────────────


def _check_revision(row: DocumentSummary, revision: int) -> None:
    if row.revision != revision:
        raise Conflict("Bản tóm tắt đã được thay đổi ở nơi khác. Tải lại để xem phiên bản mới nhất.")


def edit(file_stem: str, revision: int, text: str, user: AppUser | None) -> dict:
    """Kỹ thuật viên sửa nội dung; mọi chỉnh sửa đưa bản tóm tắt về nháp chờ duyệt lại."""
    text = text.strip()
    if not text:
        raise SummaryError("Nội dung tóm tắt không được để trống.")

    def apply(row: DocumentSummary) -> None:
        _check_revision(row, revision)
        if row.status not in _SETTLED:
            raise Conflict("Bản tóm tắt đang được sinh hoặc lỗi, chưa sửa được.")
        path = _markdown_path(file_stem)
        source = path.read_text(encoding="utf-8") if path.exists() else ""
        row.text = text
        row.warnings = number_warnings(text, source)
        row.status = SummaryStatus.DRAFT.value
        row.edited_by = user.id if user is not None else None
        row.edited_at = datetime.utcnow()
        row.reviewed_by = row.reviewed_at = row.review_note = None

    return _store(file_stem, apply)


def decide(file_stem: str, revision: int, approve: bool, note: str, user: AppUser | None) -> dict:
    """Người duyệt phê duyệt nháp, hoặc từ chối nháp / thu hồi bản đã duyệt (cần ghi chú)."""
    note = note.strip()
    if not approve and not note:
        raise SummaryError("Cần ghi lý do từ chối.")

    def apply(row: DocumentSummary) -> None:
        _check_revision(row, revision)
        allowed = {SummaryStatus.DRAFT.value} if approve else {SummaryStatus.DRAFT.value, SummaryStatus.APPROVED.value}
        if row.status not in allowed:
            raise Conflict("Trạng thái hiện tại của bản tóm tắt không cho phép thao tác này.")
        if approve and not (row.text or "").strip():
            raise SummaryError("Bản tóm tắt rỗng, không phê duyệt được.")
        if approve and _is_stale(row, _current_sha(file_stem)):
            raise Conflict("Tài liệu đã được xử lý lại sau khi sinh bản tóm tắt này. Cần sinh lại trước khi phê duyệt.")
        row.status = (SummaryStatus.APPROVED if approve else SummaryStatus.REJECTED).value
        row.reviewed_by = user.id if user is not None else None
        row.reviewed_at = datetime.utcnow()
        row.review_note = note or None

    return _store(file_stem, apply)


# ── CLI: sinh cho tài liệu đã có trước khi có tính năng ──────────────────────


def _ready_stems() -> list[str]:
    db = _session()
    try:
        rows = db.query(Document.file_stem).filter(Document.ingest_status == IngestStatus.READY).all()
        return sorted(stem for (stem,) in rows)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh bản tóm tắt nháp (chờ duyệt) cho tài liệu đã nạp")
    parser.add_argument("stems", nargs="*", help="file_stem; bỏ trống = mọi tài liệu ready")
    parser.add_argument("--force", action="store_true", help="sinh lại cả khi bản hiện có đã khớp tài liệu")
    args = parser.parse_args()
    from core.startup import startup

    startup()
    for stem in args.stems or _ready_stems():
        result = generate(stem, force=args.force)
        print(f"{stem}: {result['status']} {result.get('error') or ''}".rstrip(), flush=True)  # noqa: T201 - CLI


if __name__ == "__main__":
    main()
