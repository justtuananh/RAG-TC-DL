"""QTKĐ RAG API Server — FastAPI + SSE, giao tiếp với React frontend.

Run (cùng kotaemon/.venv):
  /path/to/kotaemon/.venv/bin/python api_server.py

Cần cài thêm (nếu chưa có trong kotaemon/.venv):
  pip install fastapi uvicorn

CORS: localhost:5173 (Vite dev), localhost:5174
Port: 8080 (không đụng Gradio :7861, embedding :8010, reranker :8011)

Endpoints:
  GET  /api/health
  GET  /api/examples
  POST /api/chat/stream  — SSE streaming (text/event-stream)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Generator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
