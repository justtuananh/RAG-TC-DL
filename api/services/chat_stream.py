"""Luồng SSE của /api/chat/stream: truy hồi văn bản và stream LLM.

Tách nguyên từ api_server.py. Gọi qua tên module (retriever.retrieve,
generator.stream_ollama) để test chỉ cần patch một chỗ. Câu hỏi đi thẳng pipeline
RAG; xử lý câu hỏi mơ hồ thiết bị nằm ở nhánh văn bản.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Iterator

from sqlalchemy.orm import Session

from api.schemas import ChatMessage, ChatRequest
from core.latex import fix_latex, restore_formulas
from core.settings_loader import get_settings
from llm import citations, generator, number_check
from llm.guards import (
    CALCULATION_GUIDE,
    REFUSAL_SENTENCE,
    enforce_refusal_stop,
    is_calculation_request,
)
from llm.lang_guard import LANGUAGE_FALLBACK, CjkStreamGuard, strip_cjk
from llm.prompt import build_messages
from query import (
    chat_calc,
    device_ambiguity,
    extractive,
    history_context,
    multi_document,
    object_scope,
    unit_convert,
)
from retrieval import doc_pages, doc_titles, retriever, router
from retrieval.context_builder import build_context_and_citations, filter_by_confidence
from retrieval.quote import build_quote

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
    quote_anchors = get_settings().llm.context.quote_anchors
    out = []
    for i, r in enumerate(results, 1):
        p = r["payload"]
        pp = r.get("parent_payload")
        child_text = p["text"]
        snippet = child_text[:220].replace("\n", " ")
        if len(child_text) > 220:
            snippet += "…"
        parent_text = pp["text"] if pp else child_text
        page, page_exact = doc_pages.page_for(p["file_stem"], p["section_path"])
        out.append(
            {
                "index": i,
                "file_stem": p["file_stem"],
                "section_path": p["section_path"],
                "page": page,
                "page_exact": page_exact,
                "kind": p.get("kind", "paragraph"),
                "snippet": snippet,
                "rerank_score": round(r.get("rerank_score", 0.0), 4),
                "parent_text": parent_text,
                "child_text": child_text,
                # Đoạn trích cho panel nguồn: các đoạn con khớp nhất + công thức chúng nói tới.
                "quote": build_quote(
                    parent_text, (r.get("anchor_texts") or [child_text])[:quote_anchors]
                ),
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


def _object_out_of_scope(question: str, results: list[dict]) -> bool:
    """Hỏi quy trình/điều kiện kiểm định của đối tượng không thuộc QTKĐ nào trong kho?"""
    cfg = get_settings().object_scope
    if not cfg.enabled or not object_scope.object_phrase(question, cfg):
        return False
    try:
        if router.route_files(question):
            return False  # nêu số QTKĐ hoặc thiết bị đã biết: đối tượng thuộc kho
        objects = [doc_titles.title_for(stem) for stem in router.known_files()]
        objects += list(router.device_aliases())
    except Exception as e:  # noqa: BLE001 - không dựng được tập đối tượng thì trả lời như cũ
        logger.warning("Không dựng được tập đối tượng kiểm định: %s", e)
        return False
    scope_re = re.compile(cfg.scope_section_pattern, re.IGNORECASE)
    scopes = []
    for r in results:
        for payload in (r.get("payload") or {}, r.get("parent_payload") or {}):
            if scope_re.search(payload.get("section_path", "")):
                scopes.append(payload.get("text", ""))
    return object_scope.is_out_of_scope(question, objects, scopes, cfg)


def _names_device(question: str) -> bool:
    try:
        return multi_document.names_device(
            question, router.device_aliases(), get_settings().llm.multi_document.generic_device_words
        )
    except Exception as e:  # noqa: BLE001 - không đọc được từ điển thiết bị thì coi như không nêu
        logger.warning("Không đọc được từ điển thiết bị: %s", e)
        return False


def _document_plan(question: str, results: list[dict]) -> list[multi_document.DocumentGroup] | None:
    """Tài liệu có thể cần hỏi bổ sung, hoặc None: chỉ trả lời một lượt như thường."""
    cfg = get_settings().llm.multi_document
    groups = multi_document.group_by_document([r["payload"]["file_stem"] for r in results])
    if not cfg.enabled or len(groups) < max(cfg.min_documents, 2):
        return None
    texts = [r["payload"].get("text", "") for r in results]
    texts += [r["parent_payload"].get("text", "") for r in results if r.get("parent_payload")]
    if multi_document.names_unknown_document(question, texts):
        return None  # văn bản ngoài kho: để nhánh một lượt từ chối như mốc
    try:
        named = router.route_files(question)
    except Exception as e:  # noqa: BLE001 - không định tuyến được thì trả lời như cũ
        logger.warning("Không định tuyến được câu hỏi cho nhánh nhiều tài liệu: %s", e)
        return None
    if not named and _names_device(question):
        return None  # nêu một loại thiết bị (chưa đủ để ghim file): trả lời một lượt, không tách tài liệu
    return multi_document.select_documents(
        groups, named, min_documents=cfg.min_documents, max_documents=cfg.max_documents
    )


def _supplement_uncovered(
    question: str,
    results: list[dict],
    groups: list[multi_document.DocumentGroup],
    general: str,
    started_at: float | None = None,
) -> tuple[str, str] | None:
    """Câu trả lời chung có trước; chỉ hỏi RIÊNG các tài liệu mà nó chưa có dòng khẳng định trích [n] tới.

    Ngữ cảnh mỗi lượt chỉ gồm nguồn của một tài liệu (giữ số [n] gốc). Lượt trả "không nêu" thì bỏ qua,
    không ghi đè lên câu chung. Trả (các dòng bổ sung, ngữ cảnh đã dùng) hoặc None khi không có gì thêm."""
    cfg = get_settings().llm.multi_document
    chat = get_settings().llm.chat
    try:
        named = len(router.route_files(question)) >= 2
    except Exception:  # noqa: BLE001 - không định tuyến được: coi như câu chung
        named = False
    missing = multi_document.followup_groups(
        multi_document.uncovered_groups(general, groups),
        [r.get("rerank_score", 0.0) for r in results],
        limit=cfg.max_followups_named if named else cfg.max_followups,
        min_score=0.0 if named else cfg.min_followup_score,  # tài liệu được nêu đích danh luôn đáng hỏi
    )
    entries: list[tuple[str, str]] = []
    contexts: list[str] = []
    for group in missing:
        if started_at is not None and not multi_document.within_budget(
            time.monotonic() - started_at, cfg.time_budget_s
        ):
            break  # đã quá ngân sách thời gian: giữ p95
        subset = [results[i] for i in group.positions]
        ctx, _ = build_context_and_citations(
            subset, numbers=[i + 1 for i in group.positions], total_chars=cfg.context_chars, question=question
        )
        title = doc_titles.title_for(group.stem)
        number = re.search(r"\d+\.\d+", group.stem)
        short = number.group(0) if number else group.stem
        label = f"{short} ({title})" if title else short
        messages = build_messages(question, ctx, [], guidance=multi_document.document_note(label))
        try:
            raw = generator.chat_once(messages, num_predict=cfg.num_predict, timeout_s=chat.timeout_s)
        except Exception as e:  # noqa: BLE001 - lỗi một tài liệu: giữ câu trả lời chung
            logger.warning("Hỏi riêng tài liệu %s thất bại: %s", group.stem, e)
            break
        text = _finalize_text(raw, ctx)
        if multi_document.is_empty_answer(text):
            continue
        contexts.append(ctx)
        entries.append((label, text))
    if not entries:
        return None
    if cfg.merge_identical:
        entries = multi_document.merge_identical(entries, cfg.merge_max_chars)
    return multi_document.render(entries), "\n\n---\n\n".join(contexts)


def _finalize_text(raw: str, context: str) -> str:
    """Lọc CJK, cắt sau câu từ chối, chuẩn hóa công thức: cùng đường xử lý cho bản stream và bản sinh lại."""
    stripped = strip_cjk(raw)
    partial = LANGUAGE_FALLBACK if stripped.empty else stripped.text
    return restore_formulas(fix_latex(enforce_refusal_stop(partial)), context)


def _verify_numbers(
    body: str, messages: list[dict], context: str, allowed_extra: str, *, annotate: bool = True
) -> tuple[str, list[str]]:
    """Số liệu trong câu trả lời phải có trong nguồn (hoặc trong câu hỏi/kết quả tính). Có số lạ thì
    sinh lại tối đa ``max_regen`` lần kèm danh sách số lạ; vẫn còn thì ghi chú để người dùng đối chiếu."""
    cfg = get_settings().llm.number_check
    if not cfg.enabled:
        return body, []
    chat = get_settings().llm.chat
    check_ctx = context + "\n" + allowed_extra
    bad = number_check.unsupported(body, check_ctx)
    for _ in range(cfg.max_regen if bad else 0):
        hint = (
            "\n\n(Kiểm tra số liệu: các số sau KHÔNG có trong các nguồn: "
            + "; ".join(bad)
            + ". Hãy trả lời lại, chỉ dùng số liệu trích NGUYÊN VĂN từ nguồn.)"
        )
        retry = messages[:-1] + [{"role": "user", "content": messages[-1]["content"] + hint}]
        try:
            text = generator.chat_once(retry, num_predict=chat.max_new_tokens, timeout_s=chat.timeout_s)
        except Exception as exc:  # noqa: BLE001 - giữ câu trả lời ban đầu
            logger.warning("Sinh lại để sửa số liệu thất bại: %s", exc)
            break
        cand = _finalize_text(text, context)
        cand_bad = number_check.unsupported(cand, check_ctx)
        if len(cand_bad) >= len(bad):
            break
        body, bad = cand, cand_bad
        if not bad:
            break
    if bad:
        logger.warning("Số liệu chưa có trong nguồn: %s", bad)
        if annotate:
            body += "\n\n> Lưu ý: số liệu " + "; ".join(f"«{b}»" for b in bad) + " chưa tìm thấy trong các nguồn đã trích, cần đối chiếu trực tiếp với tài liệu."
    return body, bad


def chat_stream_events(req: ChatRequest, db: Session | None = None) -> Iterator[str]:
    # Tính toán chỉ bằng công thức ĐÃ DUYỆT (bộ tính Decimal), không để model tự tính.
    conv = unit_convert.try_convert(req.message)
    if conv is not None:
        yield _sse({"type": "done", "answer": conv.text, "sources": []})
        return
    calc = chat_calc.try_calc(req.message)
    if calc is not None and calc.kind in ("ask", "invalid"):
        yield _sse({"type": "done", "answer": calc.text, "sources": []})
        return
    if calc is None and is_calculation_request(req.message):
        yield _sse({"type": "done", "answer": CALCULATION_GUIDE, "sources": []})
        return
    prior = _history_to_prior(req.history)

    # "Áp kế pít tông ..." khớp nhiều loại (kiểu H3000, tiêu chuẩn): không được trả lời
    # bằng số liệu của một loại như câu trả lời chung.
    ambiguity = _detect_device_ambiguity(db, req.message)

    yield _sse({"type": "status", "text": "⏳ Đang nhúng câu hỏi (embedding)…"})

    retrieval_query = (
        device_ambiguity.scoped_retrieval_query(req.message, ambiguity)
        if ambiguity is not None
        else history_context.standalone_query(req.message, prior)
    )
    try:
        results = retriever.retrieve(retrieval_query)
    except Exception as e:
        yield _sse({"type": "error", "text": f"Lỗi tìm kiếm: {e}"})
        return

    if not results:
        yield _sse(
            {
                "type": "done",
                "answer": "Không tìm thấy thông tin liên quan trong tài liệu QTKĐ.",
                "sources": [],
            }
        )
        return

    # Cắt đuôi nguồn điểm thấp → panel + ngữ cảnh LLM chỉ còn nguồn uy tín ([n] khớp).
    results = filter_by_confidence(results)
    if _object_out_of_scope(req.message, results):
        yield _sse({"type": "done", "answer": REFUSAL_SENTENCE, "sources": []})
        return
    sources = _build_sources_payload(results)
    yield _sse({"type": "sources", "sources": sources})

    reference = extractive.reference_answer(results)
    if reference is not None:
        reference = citations.add_citations(reference, sources, doc_titles.title_for)
        yield _sse({"type": "delta", "text": reference})
        yield _sse({"type": "done", "answer": reference, "sources": sources})
        return

    context_str, _ = build_context_and_citations(results, question=retrieval_query)
    if calc is not None and calc.kind == "answer":
        context_str = calc.block + "\n\n---\n\n" + context_str
    guidance = device_ambiguity.ambiguity_guidance(ambiguity) if ambiguity is not None else None
    plan = _document_plan(retrieval_query, results) if ambiguity is None and calc is None else None
    if ambiguity is not None and calc is None:
        plan = multi_document.group_by_document([r['payload']['file_stem'] for r in results])
    if plan is not None:
        quoted = extractive.answer(retrieval_query, results, plan)
        if quoted is not None:
            if ambiguity is not None:
                quoted = device_ambiguity.ambiguity_preface(ambiguity) + quoted + device_ambiguity.ambiguity_closing(ambiguity)
            # Exact quotations retain their original source index; no LLM rewrite.
            quoted = citations.add_citations(quoted, sources, doc_titles.title_for)
            yield _sse({"type": "delta", "text": quoted})
            yield _sse({"type": "done", "answer": quoted, "sources": sources})
            return
    if calc is not None and calc.kind == "answer":
        # Model nhỏ bám lượt người dùng cuối hơn system prompt: đặt kết quả đã xác minh ở đây.
        calc_note = (
            "Bộ tính đã tính sẵn (đã xác minh, KHÔNG tự tính lại, KHÔNG làm tròn khác đi):\n"
            + calc.summary
            + "\nTrình bày công thức, số liệu đầu vào và kết quả đúng như trên; chỉ dùng thêm các giới hạn "
            "trích từ nguồn [n] nếu câu hỏi cần kết luận."
        )
        guidance = f"{guidance}\n\n{calc_note}" if guidance else calc_note
    messages = build_messages(req.message, context_str, prior, guidance=guidance)

    yield _sse({"type": "status", "text": "💭 Đang tổng hợp câu trả lời…"})

    preface = device_ambiguity.ambiguity_preface(ambiguity) if ambiguity is not None else ""
    closing = device_ambiguity.ambiguity_closing(ambiguity) if ambiguity is not None else ""
    if preface:
        yield _sse({"type": "delta", "text": preface})

    started_at = time.monotonic()
    guard = CjkStreamGuard()
    stream = generator.stream_ollama(messages)
    try:
        for delta in stream:
            emit, stop = guard.feed(delta)
            if emit:
                yield _sse({"type": "delta", "text": emit})
            if stop:  # đuôi dịch tiếng Trung đã rõ: ngắt luồng Ollama, khỏi sinh tiếp
                break
    except Exception as e:
        yield _sse({"type": "error", "text": f"Lỗi LLM: {e}"})
        return
    finally:
        close = getattr(stream, "close", None)
        if close is not None:
            close()
    # Tầng 3: lọc CJK tất định trên văn bản cuối (sự kiện ``done`` thay phần đã stream).
    if strip_cjk(guard.raw).fixed:
        logger.warning("Câu trả lời lẫn CJK đã được lọc")
    if closing:
        yield _sse({"type": "delta", "text": closing})

    body = _finalize_text(guard.raw, context_str)
    if calc is None and REFUSAL_SENTENCE in body:
        groups = multi_document.group_by_document([r['payload']['file_stem'] for r in results])
        quoted = extractive.answer(retrieval_query, results, groups, allow_single=True)
        if quoted is not None:
            body = quoted
    allowed_extra = req.message + "\n" + "\n".join(u for u, _ in prior)
    calc_answer = calc is not None and calc.kind == "answer"
    body, bad_numbers = _verify_numbers(body, messages, context_str, allowed_extra, annotate=not calc_answer)
    if plan is not None and ambiguity is None and not calc_answer:
        extra = _supplement_uncovered(retrieval_query, results, plan, body, started_at)
        if extra is not None:
            lines, used_context = extra
            bad = number_check.unsupported(lines, used_context + "\n" + allowed_extra)
            if bad:
                logger.warning("Số liệu chưa có trong nguồn: %s", bad)
                lines += "\n\n> Lưu ý: số liệu " + "; ".join(f"«{b}»" for b in bad) + " chưa tìm thấy trong các nguồn đã trích, cần đối chiếu trực tiếp với tài liệu."
            body = body.rstrip() + "\n\n" + lines
            yield _sse({"type": "delta", "text": "\n\n" + lines})
    if calc_answer and bad_numbers:
        # Model diễn đạt kết quả tính bằng số lạ: chỉ giữ kết quả do bộ tính tạo ra (đã xác minh).
        body = "Kết quả tính bằng công thức đã được phê duyệt:\n" + calc.summary
    else:
        body = citations.add_citations(body, sources, doc_titles.title_for)
    answer = preface + body + closing
    yield _sse({"type": "done", "answer": answer, "sources": sources})
