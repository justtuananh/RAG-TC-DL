"""Luồng SSE của /api/chat/stream: định tuyến intent, truy hồi và stream LLM.

Tách nguyên từ api_server.py. Gọi qua tên module (retriever.retrieve,
generator.stream_ollama) để test chỉ cần patch một chỗ.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

from sqlalchemy.orm import Session

from api.schemas import ChatMessage, ChatRequest
from core.latex import fix_latex
from llm import generator
from llm.guards import REFUSAL_SENTENCE, enforce_refusal_stop, is_calculation_request
from llm.prompt import build_messages
from query import device_ambiguity
from query import router as query_router
from retrieval import retriever
from retrieval.context_builder import build_context_and_citations, filter_by_confidence

logger = logging.getLogger(__name__)


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


def _detect_device_ambiguity(
    db: Session | None, question: str
) -> device_ambiguity.DeviceAmbiguity | None:
    """Câu hỏi nêu loại thiết bị chung chung (khớp nhiều QTKĐ)? None nếu không/không đọc được DB."""
    if db is None:
        return None
    try:
        catalog = device_ambiguity.load_device_procedures(db)
    except Exception as e:  # noqa: BLE001 - thiếu danh mục thì trả lời như cũ
        logger.warning("Không đọc được danh mục QTKĐ để kiểm tra câu hỏi mơ hồ: %s", e)
        return None
    return device_ambiguity.find_device_ambiguity(question, catalog)


def chat_stream_events(req: ChatRequest, db: Session | None = None) -> Iterator[str]:
    if is_calculation_request(req.message):
        yield _sse({"type": "done", "answer": REFUSAL_SENTENCE, "sources": []})
        return

    # "Áp kế pít tông ..." khớp nhiều loại (kiểu H3000, tiêu chuẩn): không được trả lời
    # bằng số liệu của một loại như câu trả lời chung.
    ambiguity = _detect_device_ambiguity(db, req.message)

    # ── Sprint 9: định tuyến chat lai văn bản + số liệu ──────────────────────
    # Không chắc chắn → nhánh text (pipeline RAG hiện tại, không đổi). Nhánh số
    # liệu lỗi cũng rơi về text: trả lời thiếu số liệu tốt hơn trả lời sai nhánh.
    branch = "text"
    data_payload = None
    if db is not None:
        decision = query_router.plan_route(req.message)
        single_procedure = (
            decision.request is not None
            and decision.request.intent in query_router.SINGLE_PROCEDURE_INTENTS
        )
        if (
            decision.request is not None
            and decision.branch in ("data", "mixed")
            and not (ambiguity is not None and single_procedure)
        ):
            try:
                data_payload = query_router.build_data_payload(db, decision.request)
                branch = decision.branch
                if data_payload.empty:
                    # Bảng rỗng (định tuyến nhầm hoặc chưa có dòng đã duyệt): trả lời
                    # bằng nhánh văn bản thay vì để người dùng không có câu trả lời.
                    branch, data_payload = "text", None
            except Exception as e:  # noqa: BLE001 - không chặn câu trả lời văn bản
                logger.warning("Tra cứu số liệu thất bại, rơi về nhánh văn bản: %s", e)
                branch = "text"
                data_payload = None

    if branch == "data":
        yield _sse({"type": "status", "text": "⏳ Đang tra cứu sổ cái hồ sơ đã duyệt…"})
        payload = query_router.payload_to_dict(data_payload) if data_payload else None
        if data_payload is not None and not data_payload.empty:
            # Cực trị: câu trả lời tất định từ nguyên văn ô của biên bản thắng.
            answer = data_payload.answer or "Kết quả tra cứu từ sổ cái hồ sơ đã duyệt:"
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

    retrieval_query = (
        device_ambiguity.scoped_retrieval_query(req.message, ambiguity)
        if ambiguity is not None
        else req.message
    )
    try:
        results = retriever.retrieve(retrieval_query)
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
    guidance = device_ambiguity.ambiguity_guidance(ambiguity) if ambiguity is not None else None
    messages = build_messages(req.message, context_str, prior, guidance=guidance)

    yield _sse({"type": "status", "text": "💭 Đang tổng hợp câu trả lời…"})

    preface = device_ambiguity.ambiguity_preface(ambiguity) if ambiguity is not None else ""
    closing = device_ambiguity.ambiguity_closing(ambiguity) if ambiguity is not None else ""
    if preface:
        yield _sse({"type": "delta", "text": preface})

    partial = ""
    try:
        for delta in generator.stream_ollama(messages):
            partial += delta
            yield _sse({"type": "delta", "text": delta})
    except Exception as e:
        yield _sse({"type": "error", "text": f"Lỗi LLM: {e}"})
        return
    if closing:
        yield _sse({"type": "delta", "text": closing})

    answer = preface + fix_latex(enforce_refusal_stop(partial)) + closing
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
