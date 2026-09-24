"""QTKĐ RAG API Server — FastAPI + SSE, giao tiếp với React frontend.

Run (cùng kotaemon/.venv):
  /path/to/kotaemon/.venv/bin/python api_server.py

Cần cài thêm (nếu chưa có trong kotaemon/.venv):
  pip install fastapi uvicorn

CORS: localhost:5173 (Vite dev), localhost:5174
Port: 8080 (không đụng Gradio :7861, embedding :8010, reranker :8011)

Endpoints:
  GET    /api/health
  GET    /api/examples
  POST   /api/chat/stream            — SSE streaming (text/event-stream)
    Sprint 9: định tuyến 3 nhánh — text (RAG hiện tại) / data (sổ cái) / mixed.
    Event: status | sources | data (khối số liệu) | delta | done{branch,data} | error
  GET    /api/documents              — list real files in TC_DL/ + ingestion status
  POST   /api/documents/upload       — save a .docx/.pdf (multipart "file"), status "pending"
  POST   /api/documents/{id}/process — extract → chunk → embed (background thread)
  GET    /api/documents/{id}/markdown
  GET    /api/documents/{id}/file    — tệp gốc (.docx/.pdf) thô, dùng để hiển thị "tài liệu gốc"
  DELETE /api/documents/{id}
  PATCH  /api/documents/{id}         — {"name": str} display-name override

  Sprint 6 — hàng đợi duyệt (vai trò approver/admin):
  GET    /api/extractions            — danh sách chờ duyệt + lọc (document/fact_kind/confidence)
  GET    /api/extractions/{id}       — chi tiết + nguồn nguyên văn để tô sáng
  POST   /api/extractions/{id}/approve
  POST   /api/extractions/{id}/reject — {"reason": str}
  POST   /api/extractions/{id}/edit   — sửa giá trị rồi duyệt
  POST   /api/extractions/bulk-approve — duyệt mọi dòng pending cùng một luật
  GET    /api/extractions/{id}/audit  — lịch sử duyệt

  Sprint 8 — bề mặt tra cứu dữ liệu (mọi vai trò đã đăng nhập, chỉ đọc view đã duyệt):
  GET    /api/data/filters           — giá trị bộ lọc (loại thiết bị/đại lượng/QTKĐ/kết luận)
  GET    /api/data/records           — bảng hồ sơ: phân trang, sắp xếp, lọc nhiều tiêu chí
  GET    /api/data/records/{id}      — chi tiết hồ sơ + điểm đo, mỗi ô số có tham chiếu xuất xứ
  GET    /api/data/records/export.xlsx — xuất Excel kết quả lọc kèm cột xuất xứ
  GET    /api/data/devices           — thiết bị có hồ sơ đã duyệt (tìm theo số hiệu)
  GET    /api/data/devices/{id}/history — định danh + dòng thời gian + diễn biến sai số
  GET    /api/data/devices/by-serial/{serial} — trang thiết bị theo số hiệu
  GET    /api/data/provenance        — mở đoạn nguyên văn của một ô số (tài liệu/mục/chunk)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Generator

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent))

from retrieval.retriever import retrieve
from generation import (
    REFUSAL_SENTENCE,
    build_context_and_citations,
    build_messages,
    enforce_refusal_stop,
    filter_by_confidence,
    is_calculation_request,
    stream_ollama,
)
from latex import fix_latex
import ingestion_jobs
import review.queue as review
from query import export as data_export
from query import provenance as provenance_query
from query import records as data_query
from query import router as query_router
from auth import (
    create_access_token,
    create_audit_log,
    get_current_user,
    require_role,
    verify_password,
)
from db import get_db
from db.models import AppUser, ExtractionStatus, UserRole

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="QTKĐ RAG API", version="1.0.0")

logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

EXAMPLES = [
    "Thời gian quay tự do tối thiểu của píttông áp kế là bao lâu?",
    "Công thức hiệu chỉnh nhiệt độ cho thời gian quay tự do?",
    "Sai số cho phép khi kiểm tra van an toàn là bao nhiêu?",
    "Điều kiện môi trường khi tiến hành kiểm định áp suất?",
    "Thiết bị chuẩn cần thiết để kiểm định đồng hồ áp suất?",
    "Số lần đo tối thiểu khi kiểm tra đồng hồ áp suất?",
]


# ── Pydantic models ───────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class RenameRequest(BaseModel):
    name: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ApproveRequest(BaseModel):
    note: str | None = None


class RejectRequest(BaseModel):
    reason: str


class EditApproveRequest(BaseModel):
    """Trường dữ kiện được sửa rồi duyệt (chỉ gửi trường thực sự đổi)."""

    label: str | None = None
    rel_op: str | None = None
    value_min: float | None = None
    value_max: float | None = None
    unit_id: int | None = None
    value_text: str | None = None
    condition_text: str | None = None
    name_vi: str | None = None
    range_text: str | None = None
    accuracy_text: str | None = None
    note: str | None = None
    term_vi: str | None = None
    term_en: str | None = None
    definition: str | None = None


class BulkApproveRequest(BaseModel):
    extractor: str
    section_path: str | None = None
    document_id: str | None = None
    note: str | None = None


class IngestRecordRequest(BaseModel):
    """Chỉ định QTKĐ khi hồ sơ không tự nhận diện được (tùy chọn)."""

    procedure_id: int | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _audit(
    db: Session,
    user: AppUser,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """Record a write operation in audit_log (design §5.6).

    In dev-without-auth mode get_current_user may return a lightweight mock that
    is not a persisted row; persisting an audit entry for it would violate the
    actor_id foreign key, so it is skipped. Real accounts are always recorded.
    """
    if not isinstance(user, AppUser):
        return
    create_audit_log(
        db=db,
        actor=user,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
    )


def _document_snapshot(doc: dict) -> dict:
    """Minimal, JSON-safe snapshot of a document row for before/after audit."""
    return {k: doc.get(k) for k in ("id", "name", "ext", "size", "doc_type", "status", "sha256")}


def _history_to_prior(history: list[ChatMessage]) -> list[list[str]]:
    """Flatten flat message list → [[user, assistant], ...] for build_messages."""
    prior: list[list[str]] = []
    i = 0
    while i + 1 < len(history):
        u, a = history[i], history[i + 1]
        if u.role == "user" and a.role == "assistant":
            prior.append([u.content, a.content])
        i += 2
    return prior


def _build_sources_payload(results: list[dict]) -> list[dict]:
    out = []
    for i, r in enumerate(results, 1):
        p = r["payload"]
        pp = r.get("parent_payload")
        child_text = p["text"]
        snippet = child_text[:220].replace("\n", " ")
        if len(child_text) > 220:
            snippet += "…"
        out.append(
            {
                "index": i,
                "file_stem": p["file_stem"],
                "section_path": p["section_path"],
                "kind": p.get("kind", "paragraph"),
                "snippet": snippet,
                "rerank_score": round(r.get("rerank_score", 0.0), 4),
                "parent_text": pp["text"] if pp else child_text,
                "child_text": child_text,
            }
        )
    return out


# ── SSE generator ─────────────────────────────────────────────────────────────


def _chat_stream_gen(req: ChatRequest, db: Session | None = None) -> Generator[str, None, None]:
    if is_calculation_request(req.message):
        yield _sse({"type": "done", "answer": REFUSAL_SENTENCE, "sources": []})
        return

    # ── Sprint 9: định tuyến chat lai văn bản + số liệu ──────────────────────
    # Không chắc chắn → nhánh text (pipeline RAG hiện tại, không đổi). Nhánh số
    # liệu lỗi cũng rơi về text: trả lời thiếu số liệu tốt hơn trả lời sai nhánh.
    branch = "text"
    data_payload = None
    if db is not None:
        decision = query_router.plan_route(req.message)
        if decision.request is not None and decision.branch in ("data", "mixed"):
            try:
                data_payload = query_router.build_data_payload(db, decision.request)
                branch = decision.branch
            except Exception as e:  # noqa: BLE001 - không chặn câu trả lời văn bản
                logger.warning("Tra cứu số liệu thất bại, rơi về nhánh văn bản: %s", e)
                branch = "text"
                data_payload = None

    if branch == "data":
        yield _sse({"type": "status", "text": "⏳ Đang tra cứu sổ cái hồ sơ đã duyệt…"})
        payload = query_router.payload_to_dict(data_payload) if data_payload else None
        if data_payload is not None and not data_payload.empty:
            answer = "Kết quả tra cứu từ sổ cái hồ sơ đã duyệt:"
        else:
            answer = "Không tìm thấy hồ sơ đã duyệt phù hợp trong sổ cái."
        yield _sse({"type": "data", "data": payload})
        yield _sse(
            {
                "type": "done",
                "answer": answer,
                "sources": [],
                "branch": "data",
                "data": payload,
            }
        )
        return

    yield _sse({"type": "status", "text": "⏳ Đang nhúng câu hỏi (embedding)…"})

    try:
        results = retrieve(req.message, top_k=50, top_n=5)
    except Exception as e:
        yield _sse({"type": "error", "text": f"Lỗi tìm kiếm: {e}"})
        return

    if not results:
        mixed_payload = (
            query_router.payload_to_dict(data_payload)
            if branch == "mixed" and data_payload is not None
            else None
        )
        if mixed_payload is not None:
            yield _sse({"type": "data", "data": mixed_payload})
        yield _sse(
            {
                "type": "done",
                "answer": "Không tìm thấy thông tin liên quan trong tài liệu QTKĐ.",
                "sources": [],
                "branch": branch,
                "data": mixed_payload,
            }
        )
        return

    # Cắt đuôi nguồn điểm thấp → panel + ngữ cảnh LLM chỉ còn nguồn uy tín ([n] khớp).
    results = filter_by_confidence(results)
    sources = _build_sources_payload(results)
    yield _sse({"type": "sources", "sources": sources})

    context_str, _ = build_context_and_citations(results)
    prior = _history_to_prior(req.history)
    messages = build_messages(req.message, context_str, prior)

    yield _sse({"type": "status", "text": "💭 Đang tổng hợp câu trả lời…"})

    partial = ""
    try:
        for delta in stream_ollama(messages):
            partial += delta
            yield _sse({"type": "delta", "text": delta})
    except Exception as e:
        yield _sse({"type": "error", "text": f"Lỗi LLM: {e}"})
        return

    answer = fix_latex(enforce_refusal_stop(partial))
    # Nhánh mixed: ghép thêm khối số liệu sổ cái, giữ trích dẫn QTKĐ tách bạch.
    mixed_payload = (
        query_router.payload_to_dict(data_payload)
        if branch == "mixed" and data_payload is not None
        else None
    )
    if mixed_payload is not None:
        yield _sse({"type": "data", "data": mixed_payload})
    yield _sse(
        {
            "type": "done",
            "answer": answer,
            "sources": sources,
            "branch": branch,
            "data": mixed_payload,
        }
    )


# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/api/health")
def health():
    return {"status": "ok", "model": os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")}


@app.get("/api/examples")
def examples():
    return {"examples": EXAMPLES}


@app.post("/api/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(AppUser).filter(AppUser.username == req.username).one_or_none()
    if user is None or not user.is_active or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu.")
    return {
        "access_token": create_access_token(user.id, user.username, user.role.value),
        "token_type": "bearer",
    }


@app.get("/api/auth/me")
def me(user: AppUser = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role.value,
    }


@app.post("/api/auth/logout", status_code=204)
def logout(user: AppUser = Depends(get_current_user)):
    """Stateless JWT logout — the client discards the token. Kept server-side so
    the frontend has a single, authenticated place to end a session."""
    return None


@app.post("/api/auth/refresh")
def refresh(user: AppUser = Depends(get_current_user)):
    """Issue a fresh access token for the current user (sliding expiry)."""
    return {
        "access_token": create_access_token(user.id, user.username, user.role.value),
        "token_type": "bearer",
    }


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest, db: Session = Depends(get_db)):
    return StreamingResponse(
        _chat_stream_gen(req, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Document routes (upload → extract → chunk → embed) ───────────────────────


@app.get("/api/documents")
def list_documents():
    return {"documents": ingestion_jobs.list_documents()}


@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    user: AppUser = Depends(require_role(UserRole.TECHNICIAN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    data = await file.read()
    try:
        file_stem = ingestion_jobs.save_upload(
            file.filename or "",
            data,
            uploaded_by=user.id if isinstance(user, AppUser) else None,
        )
    except ingestion_jobs.UploadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    doc = next((d for d in ingestion_jobs.list_documents() if d["id"] == file_stem), None)
    if doc is None:
        raise HTTPException(status_code=500, detail="Đã lưu tệp nhưng không đọc lại được.")
    _audit(db, user, "upload", "document", file_stem, after=_document_snapshot(doc))
    return doc


@app.post("/api/documents/{file_stem}/process")
def process_document(
    file_stem: str,
    user: AppUser = Depends(require_role(UserRole.TECHNICIAN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        ingestion_jobs.start_processing(file_stem)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")
    except RuntimeError:
        raise HTTPException(status_code=409, detail="Tài liệu đang được xử lý.")
    _audit(db, user, "process", "document", file_stem, after={"status": "queued"})
    return {"status": "queued"}


@app.get("/api/documents/{file_stem}/markdown")
def document_markdown(file_stem: str):
    md = ingestion_jobs.get_markdown(file_stem)
    if md is None:
        raise HTTPException(status_code=404, detail="Tài liệu chưa được xử lý.")
    return {"file_stem": file_stem, "markdown": md}


_FILE_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@app.get("/api/documents/{file_stem}/file")
def document_file(file_stem: str):
    """Trả về tệp .docx/.pdf gốc (không phải Markdown đã trích xuất/embed) để
    frontend hiển thị đúng tài liệu nguồn."""
    path = ingestion_jobs.get_source_path(file_stem)
    if path is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp gốc.")
    media_type = _FILE_MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(
        path, media_type=media_type, filename=path.name, content_disposition_type="inline"
    )


@app.delete("/api/documents/{file_stem}", status_code=204)
def delete_document(
    file_stem: str,
    user: AppUser = Depends(require_role(UserRole.TECHNICIAN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    before = next((d for d in ingestion_jobs.list_documents() if d["id"] == file_stem), None)
    ingestion_jobs.delete_document(file_stem)
    if before is not None:
        _audit(db, user, "delete", "document", file_stem, before=_document_snapshot(before))


@app.patch("/api/documents/{file_stem}")
def rename_document(
    file_stem: str,
    req: RenameRequest,
    user: AppUser = Depends(require_role(UserRole.TECHNICIAN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    before = next((d for d in ingestion_jobs.list_documents() if d["id"] == file_stem), None)
    try:
        doc = ingestion_jobs.rename_document(file_stem, req.name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")
    _audit(
        db,
        user,
        "rename",
        "document",
        file_stem,
        before={"name": before["name"]} if before else None,
        after={"name": doc["name"]},
    )
    return doc


# ── Sprint 6: hàng đợi duyệt (approver/admin) ─────────────────────────────────
# Đây là bề mặt làm việc của người duyệt nên thấy dữ liệu `pending`; mọi bề mặt
# tra cứu khác chỉ đọc view đã duyệt ở `query/` (P3). Vai trò approver/admin được
# ép ở dependency, trước cả khi chạm DB.


def _review_http(exc: review.ReviewError) -> HTTPException:
    if isinstance(exc, review.NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, review.ConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@app.get("/api/extractions")
def list_extractions(
    document_id: str | None = None,
    fact_kind: str | None = None,
    extractor: str | None = None,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    status: str = "pending",
    limit: int = 50,
    offset: int = 0,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        status_enum = ExtractionStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Trạng thái không hợp lệ: {status}")
    items, total = review.list_queue(
        db,
        status=status_enum,
        document_id=document_id,
        fact_kind=fact_kind,
        extractor=extractor,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        limit=max(1, min(limit, 200)),
        offset=max(0, offset),
    )
    return {
        "items": items,
        "total": total,
        "status": status_enum.value,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/extractions/{extraction_id}")
def get_extraction(
    extraction_id: int,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        return review.get_extraction(db, extraction_id)
    except review.ReviewError as exc:
        raise _review_http(exc)


@app.post("/api/extractions/{extraction_id}/approve")
def approve_extraction(
    extraction_id: int,
    req: ApproveRequest | None = None,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        return review.approve(db, extraction_id, user, note=req.note if req else None)
    except review.ReviewError as exc:
        raise _review_http(exc)


@app.post("/api/extractions/{extraction_id}/reject")
def reject_extraction(
    extraction_id: int,
    req: RejectRequest,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        return review.reject(db, extraction_id, user, reason=req.reason)
    except review.ReviewError as exc:
        raise _review_http(exc)


@app.post("/api/extractions/{extraction_id}/edit")
def edit_extraction(
    extraction_id: int,
    req: EditApproveRequest,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    payload = req.model_dump(exclude_unset=True)
    note = payload.pop("note", None)
    try:
        return review.edit_and_approve(db, extraction_id, user, payload, note=note)
    except review.ReviewError as exc:
        raise _review_http(exc)


@app.post("/api/extractions/bulk-approve")
def bulk_approve_extractions(
    req: BulkApproveRequest,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        return review.bulk_approve(
            db,
            user,
            extractor=req.extractor,
            section_path=req.section_path,
            document_id=req.document_id,
            note=req.note,
        )
    except review.ReviewError as exc:
        raise _review_http(exc)


@app.get("/api/extractions/{extraction_id}/audit")
def extraction_audit(
    extraction_id: int,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        review.get_extraction(db, extraction_id)
    except review.ReviewError as exc:
        raise _review_http(exc)
    return {"entries": review.audit_history(db, extraction_id)}


# ── Sprint 7: nạp hồ sơ kiểm định / phiếu đo ──────────────────────────────────
# Nạp hồ sơ là thao tác ghi (technician/admin) và đi qua hàng đợi duyệt: dữ liệu
# đo mới luôn `pending`. Bề mặt đọc chỉ trả hồ sơ đã duyệt qua view (P3).


@app.post("/api/records/ingest/{file_stem}")
def ingest_record(
    file_stem: str,
    req: IngestRecordRequest | None = None,
    user: AppUser = Depends(require_role(UserRole.TECHNICIAN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    from db.models import Document, Procedure
    from records.ingest import IngestError, ingest_record_path

    document = db.query(Document).filter(Document.file_stem == file_stem).one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")
    source_path = ingestion_jobs.get_source_path(file_stem)
    if source_path is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp gốc của tài liệu.")

    procedure = None
    if req is not None and req.procedure_id is not None:
        procedure = db.get(Procedure, req.procedure_id)
        if procedure is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy QTKĐ.")

    try:
        result = ingest_record_path(
            db, document=document, source_path=source_path, procedure=procedure
        )
        db.commit()
    except IngestError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise
    _audit(db, user, "ingest_record", "document", file_stem, after=result.as_dict())
    return result.as_dict()


@app.get("/api/records")
def list_records(
    procedure_id: int | None = None,
    device_id: int | None = None,
    limit: int = 200,
    offset: int = 0,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Hồ sơ kiểm định ĐÃ DUYỆT (đọc ``v_calibration_record``, P3)."""
    from query import approved as approved_query

    records = approved_query.list_approved_records(
        db, procedure_id=procedure_id, device_id=device_id, limit=limit, offset=offset
    )
    return {"records": records, "total": len(records)}


# ── Sprint 8: bề mặt tra cứu dữ liệu (tab "Dữ liệu" + lịch sử thiết bị) ──────
# Mọi route chỉ ĐỌC qua các view đã duyệt ở `query/records.py` (P3). Vai trò: mọi
# người dùng đã đăng nhập (kể cả viewer) đều tra cứu được; đây là bề mặt đọc.
# Mỗi ô số trả kèm tham chiếu xuất xứ; `GET /api/data/provenance` mở đoạn nguồn.


def _data_http(exc: Exception) -> HTTPException:
    if isinstance(exc, data_query.NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (data_query.QueryError, provenance_query.ProvenanceError)):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@app.get("/api/data/filters")
def data_filters(
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Giá trị bộ lọc (loại thiết bị, đại lượng, QTKĐ, kết luận) đọc từ dữ liệu đã duyệt."""
    return data_query.filter_options(db)


@app.get("/api/data/records")
def data_records(
    device_type_id: int | None = None,
    quantity_id: int | None = None,
    procedure_id: int | None = None,
    verdict: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    range_min: float | None = None,
    range_max: float | None = None,
    range_unit: str | None = None,
    accuracy: str | None = None,
    serial: str | None = None,
    search: str | None = None,
    sort: str = data_query.DEFAULT_SORT,
    order: str = data_query.DEFAULT_ORDER,
    limit: int = 50,
    offset: int = 0,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bảng hồ sơ đã duyệt: phân trang, sắp xếp, lọc nhiều tiêu chí (P3)."""
    try:
        items, total = data_query.list_records(
            db,
            device_type_id=device_type_id,
            quantity_id=quantity_id,
            procedure_id=procedure_id,
            verdict=verdict,
            date_from=date_from,
            date_to=date_to,
            range_min=range_min,
            range_max=range_max,
            range_unit=range_unit,
            accuracy=accuracy,
            serial=serial,
            search=search,
            sort=sort,
            order=order,
            limit=limit,
            offset=offset,
        )
    except data_query.QueryError as exc:
        raise _data_http(exc)
    return {
        "items": items,
        "total": total,
        "limit": max(1, min(limit, data_query.LIST_LIMIT_MAX)),
        "offset": max(0, offset),
        "sort": sort,
        "order": order,
    }


@app.get("/api/data/records/export.xlsx")
def data_records_export(
    device_type_id: int | None = None,
    quantity_id: int | None = None,
    procedure_id: int | None = None,
    verdict: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    range_min: float | None = None,
    range_max: float | None = None,
    range_unit: str | None = None,
    accuracy: str | None = None,
    serial: str | None = None,
    search: str | None = None,
    sort: str = data_query.DEFAULT_SORT,
    order: str = data_query.DEFAULT_ORDER,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Xuất Excel kết quả lọc hiện tại, kèm cột xuất xứ cho từng ô số (P1)."""
    try:
        records = data_query.all_records(
            db,
            device_type_id=device_type_id,
            quantity_id=quantity_id,
            procedure_id=procedure_id,
            verdict=verdict,
            date_from=date_from,
            date_to=date_to,
            range_min=range_min,
            range_max=range_max,
            range_unit=range_unit,
            accuracy=accuracy,
            serial=serial,
            search=search,
            sort=sort,
            order=order,
        )
    except data_query.QueryError as exc:
        raise _data_http(exc)

    fact_cache: dict[int, dict | None] = {}

    def _fact_lookup(fact_id: int) -> dict | None:
        if fact_id not in fact_cache:
            try:
                fact_cache[fact_id] = provenance_query.fact_provenance(db, fact_id)
            except provenance_query.ProvenanceError:
                fact_cache[fact_id] = None
        return fact_cache[fact_id]

    payload = data_export.records_xlsx(records, _fact_lookup)
    filename = f"du-lieu-kiem-dinh-{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/data/records/{record_id}")
def data_record_detail(
    record_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Chi tiết một hồ sơ đã duyệt + các điểm đo, mỗi ô số có tham chiếu xuất xứ."""
    try:
        return data_query.get_record(db, record_id)
    except data_query.QueryError as exc:
        raise _data_http(exc)


@app.get("/api/data/devices")
def data_devices(
    q: str | None = None,
    device_type_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Thiết bị có ít nhất một hồ sơ đã duyệt (tìm theo số hiệu/model/hãng)."""
    devices, total = data_query.list_devices(
        db, q=q, device_type_id=device_type_id, limit=limit, offset=offset
    )
    return {
        "items": devices,
        "total": total,
        "limit": max(1, min(limit, data_query.LIST_LIMIT_MAX)),
        "offset": max(0, offset),
    }


@app.get("/api/data/devices/{device_id}/history")
def data_device_history(
    device_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trang thiết bị: định danh, dòng thời gian kiểm định, diễn biến sai số (P3)."""
    try:
        return data_query.device_history(db, device_id=device_id)
    except data_query.QueryError as exc:
        raise _data_http(exc)


@app.get("/api/data/devices/by-serial/{serial}")
def data_device_history_by_serial(
    serial: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trang thiết bị theo số hiệu (đường dẫn tiện dụng cho liên kết từ bảng)."""
    try:
        return data_query.device_history(db, serial=serial)
    except data_query.QueryError as exc:
        raise _data_http(exc)


@app.get("/api/data/provenance")
def data_provenance(
    extraction_id: int | None = None,
    record_id: int | None = None,
    fact_id: int | None = None,
    measurement_id: int | None = None,
    field: str | None = None,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mở đúng đoạn nguyên văn sinh ra một ô số: tài liệu, mục, chunk, trích dẫn (P1)."""
    try:
        return provenance_query.resolve(
            db,
            extraction_id=extraction_id,
            record_id=record_id,
            fact_id=fact_id,
            measurement_id=measurement_id,
            field=field,
        )
    except provenance_query.ProvenanceError as exc:
        raise _data_http(exc)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
