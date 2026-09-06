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
  GET    /api/documents              — list real files in TC_DL/ + ingestion status
  POST   /api/documents/upload       — save a .docx/.pdf (multipart "file"), status "pending"
  POST   /api/documents/{id}/process — extract → chunk → embed (background thread)
  GET    /api/documents/{id}/markdown
  GET    /api/documents/{id}/file    — tệp gốc (.docx/.pdf) thô, dùng để hiển thị "tài liệu gốc"
  DELETE /api/documents/{id}
  PATCH  /api/documents/{id}         — {"name": str} display-name override
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Generator

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

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

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="QTKĐ RAG API", version="1.0.0")

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
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class RenameRequest(BaseModel):
    name: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


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
        out.append({
            "index": i,
            "file_stem": p["file_stem"],
            "section_path": p["section_path"],
            "kind": p.get("kind", "paragraph"),
            "snippet": snippet,
            "rerank_score": round(r.get("rerank_score", 0.0), 4),
            "parent_text": pp["text"] if pp else child_text,
            "child_text": child_text,
        })
    return out


# ── SSE generator ─────────────────────────────────────────────────────────────

def _chat_stream_gen(req: ChatRequest) -> Generator[str, None, None]:
    if is_calculation_request(req.message):
        yield _sse({"type": "done", "answer": REFUSAL_SENTENCE, "sources": []})
        return

    yield _sse({"type": "status", "text": "⏳ Đang nhúng câu hỏi (embedding)…"})

    try:
        results = retrieve(req.message, top_k=50, top_n=5)
    except Exception as e:
        yield _sse({"type": "error", "text": f"Lỗi tìm kiếm: {e}"})
        return

    if not results:
        yield _sse({
            "type": "done",
            "answer": "Không tìm thấy thông tin liên quan trong tài liệu QTKĐ.",
            "sources": [],
        })
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
    yield _sse({"type": "done", "answer": answer, "sources": sources})


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "model": os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")}


@app.get("/api/examples")
def examples():
    return {"examples": EXAMPLES}


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    return StreamingResponse(
        _chat_stream_gen(req),
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
async def upload_document(file: UploadFile = File(...)):
    data = await file.read()
    try:
        file_stem = ingestion_jobs.save_upload(file.filename or "", data)
    except ingestion_jobs.UploadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    doc = next((d for d in ingestion_jobs.list_documents() if d["id"] == file_stem), None)
    if doc is None:
        raise HTTPException(status_code=500, detail="Đã lưu tệp nhưng không đọc lại được.")
    return doc


@app.post("/api/documents/{file_stem}/process")
def process_document(file_stem: str):
    try:
        ingestion_jobs.start_processing(file_stem)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")
    except RuntimeError:
        raise HTTPException(status_code=409, detail="Tài liệu đang được xử lý.")
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
    return FileResponse(path, media_type=media_type, filename=path.name, content_disposition_type="inline")


@app.delete("/api/documents/{file_stem}", status_code=204)
def delete_document(file_stem: str):
    ingestion_jobs.delete_document(file_stem)


@app.patch("/api/documents/{file_stem}")
def rename_document(file_stem: str, req: RenameRequest):
    try:
        return ingestion_jobs.rename_document(file_stem, req.name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
