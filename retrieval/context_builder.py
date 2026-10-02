"""Dựng ngữ cảnh + trích dẫn cho LLM từ kết quả truy hồi.

Lọc đuôi nguồn điểm thấp, cắt mỗi nguồn theo ngân sách ký tự (lấy cửa sổ quanh
đoạn con được truy hồi) rồi ghép thành context_str + citations_md đánh số [n].
"""

from __future__ import annotations

from core.settings_loader import get_settings

# ── Lọc nguồn theo độ tin cậy (cắt đuôi nguồn yếu) ───────────────────────────
# Reranker (bge-reranker-v2-m3) trả điểm sigmoid [0,1]. Với câu HẸP, chỉ 1-2 nguồn
# thực sự liên quan; phần đuôi điểm ~0 là NHIỄU - không nên hiện như "nguồn của câu
# trả lời" (mất uy tín) lẫn nhồi vào ngữ cảnh LLM (lost-in-the-middle). Cắt đuôi:
# LUÔN giữ nguồn top; giữ nguồn sau nếu điểm ≥ CẢ ngưỡng tuyệt đối VÀ tương đối-theo-top.
# Áp dụng SAU retrieve() (ở consumer) nên KHÔNG đụng thứ hạng/recall của retrieve() -
# evaluation/run_eval đo recall@5 trên top-5 đầy đủ vẫn nguyên. Ngưỡng chọn để không rớt nguồn
# gold của eval_set (xem tests/unit/retrieval/test_source_filter.py + scripts kiểm tra).


def filter_by_confidence(results: list[dict]) -> list[dict]:
    """Cắt đuôi nguồn điểm thấp khỏi CẢ panel LẪN ngữ cảnh LLM (giữ [n] nhất quán).

    `results` đã sắp giảm dần theo ``rerank_score`` (từ ``retrieve()``). Luôn giữ
    ``results[0]``; giữ ``results[i]`` nếu ``rerank_score ≥ max(ABS_FLOOR, REL_FLOOR×top)``.
    Giữ nguyên trật tự, không đánh số lại ở đây (consumer đánh [n] trên list trả về).
    """
    if not results:
        return results
    context = get_settings().llm.context
    top = results[0].get("rerank_score", 0.0)
    floor = max(context.source_abs_floor, context.source_rel_floor * top)
    return [results[0]] + [r for r in results[1:] if r.get("rerank_score", 0.0) >= floor]


# ── Builder ngữ cảnh + trích dẫn ──────────────────────────────────────────────


def window(parent: str, child: str, budget: int) -> str:
    """``budget`` ký tự của mục cha, luôn chứa đoạn con được truy hồi.

    Mặc định lấy đầu mục. Đoạn con nằm ngoài phần đầu (mục dài, fact ở cuối) thì nửa
    ngân sách giữ đầu mục, nửa còn lại là cửa sổ quanh đoạn con. Chỉ lấy quanh đoạn con
    là mất công thức ở đầu mục khi đoạn con là dòng "trong đó: … là …" (đo 2026-10-01:
    QTKĐ 1.159 mục 6.3.1, công thức M ở ký tự 348, đoạn con ở 3 449); chỉ lấy đầu mục là
    mất fact ở cuối (QTKĐ 1.071 mục 5.3, "± 0,1 %" ở ký tự 3 458 / 3 513).
    """
    # Đoạn con thường là nguyên văn một khúc của mục cha; so 80 ký tự đầu chỉ khi không
    # khớp trọn (phần đuôi khác khoảng trắng).
    pos = parent.find(child) if child.strip() else -1
    if pos < 0 and child.strip():
        pos = parent.find(child[:80])
    # Đoạn con bắt đầu trong nửa đầu (đoạn con dài) thì phần đầu mục đã chứa nó.
    if pos < budget // 2 or pos + len(child) <= budget:
        return parent[:budget] + "…"
    head = parent[: budget // 2]
    room = budget - len(head)
    start = max(len(head), pos - max(0, room - len(child)) // 2)
    start = min(start, len(parent) - room, pos)
    end = start + room
    tail = parent[start:end] + ("…" if end < len(parent) else "")
    return head + ("\n…\n" if start > len(head) else "") + tail


def build_context_and_citations(results: list[dict]) -> tuple[str, str]:
    """Dựng (context_str cho system prompt, citations_md cho UI) từ kết quả retrieve.

    Context dùng PARENT text (đủ ngữ cảnh) với NGÂN SÁCH ĐỘNG: mỗi nguồn được quota
    `total_context_chars / số nguồn`; nguồn ngắn nhường phần dư cho nguồn sau; có sàn
    min_block_chars. Citations dùng snippet CHILD (cap 220). Đánh số [n] khớp 1:1 giữa
    hai phần và với results[n-1].
    """
    llm = get_settings().llm
    max_block = llm.context.max_block_chars
    min_block = llm.context.min_block_chars

    ctx_parts: list[str] = []
    cite_parts: list[str] = []

    n = len(results) or 1
    # Quota mỗi nguồn: chia đều theo trần tổng, nhưng KẸP trong [MIN, MAX].
    per_block = min(max_block, max(min_block, llm.total_context_chars // n))
    carried = 0  # phần quota dư từ các nguồn ngắn, nhường cho nguồn sau

    for i, r in enumerate(results, 1):
        p = r["payload"]
        pp = r.get("parent_payload")
        file_stem = p["file_stem"]
        section_path = p["section_path"]
        child_text = p["text"]

        ctx_text = pp["text"] if pp else child_text
        budget = min(max_block, per_block + carried)  # không nguồn nào vượt cap
        if len(ctx_text) > budget:
            ctx_text = window(ctx_text, child_text, budget)
            carried = 0
        else:
            carried = budget - len(ctx_text)

        ctx_parts.append(f"[{i}] Nguồn: {file_stem} — {section_path}\n---\n{ctx_text}")

        snippet = child_text[:220].replace("\n", " ")
        if len(child_text) > 220:
            snippet += "…"
        cite_parts.append(f"**[{i}]** `{file_stem}` • {section_path}\n> {snippet}")

    context_str = "\n\n---\n\n".join(ctx_parts)
    citations_md = "\n\n---\n\n**📎 Nguồn tham khảo:**\n\n" + "\n\n".join(cite_parts)
    return context_str, citations_md
