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


def _find(parent: str, text: str) -> int:
    # Đoạn con thường là nguyên văn một khúc của mục cha; so 80 ký tự đầu chỉ khi không
    # khớp trọn (phần đuôi khác khoảng trắng).
    if not text.strip():
        return -1
    pos = parent.find(text)
    return pos if pos >= 0 else parent.find(text[:80])


def _snap(parent: str, start: int, end: int, keep: tuple[int, int] | None) -> tuple[int, int]:
    """Đưa khúc [start, end) về ranh giới dòng: bỏ dòng dở ở hai đầu, trừ dòng công thức
    ở cuối khúc được kéo trọn (tối đa ``formula_line_slack`` ký tự). Không bỏ đoạn neo
    ``keep``; không có ranh giới dòng thì giữ nguyên chỗ cắt."""
    slack = get_settings().llm.context.formula_line_slack
    if start > 0 and parent[start - 1] != "\n":
        nl = parent.find("\n", start, end)
        if nl >= 0 and (keep is None or nl < keep[0]):
            start = nl + 1
    if end < len(parent) and parent[end - 1] != "\n":
        line_start = parent.rfind("\n", start, end) + 1
        line_end = parent.find("\n", end)
        line_end = len(parent) if line_end < 0 else line_end
        if "$" in parent[line_start:line_end] and line_end - end <= slack:
            end = line_end
        elif line_start > start and (keep is None or line_start >= keep[1]):
            end = line_start
    return start, end


def window(parent: str, child: str | list[str], budget: int) -> str:
    """``budget`` ký tự của mục cha, luôn chứa các đoạn con được truy hồi (đoạn neo).

    Mặc định lấy đầu mục. Đoạn neo nằm ngoài phần đầu (mục dài, fact ở cuối) thì ngân
    sách chia đều cho đầu mục và một cửa sổ quanh mỗi đoạn neo đó. Chỉ lấy quanh đoạn con
    là mất công thức ở đầu mục khi đoạn con là dòng "trong đó: … là …" (đo 2026-10-01:
    QTKĐ 1.159 mục 6.3.1, công thức M ở ký tự 348, đoạn con ở 3 449); chỉ lấy đầu mục là
    mất fact ở cuối (QTKĐ 1.071 mục 5.3, "± 0,1 %" ở ký tự 3 458 / 3 513). Nhiều đoạn neo
    (``child`` là danh sách, theo thứ hạng): QTKĐ 1.159 mục 6.3.2, đoạn đại diện là định
    nghĩa $A_{0s}$ ở ký tự 1 997, công thức diện tích hiệu dụng (10) ở 3 967 ngay sau
    đoạn khớp thứ hai.
    Khúc cắt theo dòng (``_snap``) để không đưa cho model một công thức LaTeX bị cắt dở.
    """
    anchors = [child] if isinstance(child, str) else child
    tail = get_settings().llm.context.lead_in_tail_chars
    spans = []  # (đầu, cuối, câu dẫn?) theo thứ hạng
    for text in anchors:
        pos = _find(parent, text)
        if pos >= 0 and all(not (a <= pos < b) for a, b, _ in spans):
            spans.append((pos, pos + len(text), text.rstrip().endswith(":")))

    def need(span) -> int:
        # Câu dẫn ("… được tính từ công thức sau:") cần cả phần nó dẫn vào phía sau.
        return span[1] + (tail if span[2] else 0)

    def covered(span, head: int) -> bool:
        # Đoạn neo bắt đầu trong nửa đầu (đoạn con dài) thì phần đầu mục đã chứa nó.
        return need(span) <= head or (not span[2] and span[0] < head // 2)

    # Có đoạn neo ở ngoài thì phần đầu co lại còn một phần chia, nên xét lại các đoạn
    # neo còn lại cho tới khi ổn định.
    outside = [s for s in spans if not covered(s, budget)]
    if not outside:
        start, end = _snap(parent, 0, budget, None)
        return parent[start:end] + "…"
    while True:
        share = budget // (len(outside) + 1)
        grown = [s for s in spans if s in outside or not covered(s, share)]
        if len(grown) == len(outside):
            break
        outside = grown
    pieces = [(0, share, None)]
    for a, b, lead_in in sorted(outside):
        back = 0 if lead_in else max(0, share - (b - a)) // 2
        start = max(pieces[-1][1], a - back)
        start = min(start, len(parent) - share, a)
        pieces.append((start, start + share, (a, b)))
    merged: list[tuple[int, int]] = []
    for start, end, keep in pieces:
        start, end = _snap(parent, start, min(end, len(parent)), keep)
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    out = "\n…\n".join(parent[a:b] for a, b in merged)
    return out + ("…" if merged[-1][1] < len(parent) else "")


def _block_budgets(lengths: list[int], total: int, floor: int, cap: int) -> list[int]:
    """Ngân sách ký tự từng nguồn (water-filling): nguồn ngắn lấy đúng độ dài của nó,
    phần dư chia đều cho các nguồn dài hơn, kể cả nguồn đứng TRƯỚC; mỗi nguồn trong
    [floor, cap]. Nguồn top dài (QTKĐ 1.159 mục 6.3.2, 5 623 ký tự) không còn bị cắt ở
    phần chia đều khi các nguồn sau ngắn."""
    budgets = [0] * len(lengths)
    remaining = total
    order = sorted(range(len(lengths)), key=lengths.__getitem__)
    for k, i in enumerate(order):
        fair = remaining // (len(lengths) - k)
        budgets[i] = min(lengths[i], cap, max(floor, fair))
        remaining -= budgets[i]
    return budgets


def build_context_and_citations(results: list[dict]) -> tuple[str, str]:
    """Dựng (context_str cho system prompt, citations_md cho UI) từ kết quả retrieve.

    Context dùng PARENT text (đủ ngữ cảnh) với ngân sách ``_block_budgets`` trong trần
    tổng ``total_context_chars`` (vừa num_ctx cùng prompt và câu trả lời) và trần mỗi
    nguồn ``max_block_chars``: ngữ cảnh ~18-20k ký tự từng chôn fact (đo 2026-06-10).
    Nguồn dài hơn ngân sách lấy cửa sổ quanh các đoạn neo (``window``). Citations dùng
    snippet CHILD (cap 220). Đánh số [n] khớp 1:1 giữa hai phần và với results[n-1].
    """
    llm = get_settings().llm
    texts = [(r.get("parent_payload") or r["payload"])["text"] for r in results]
    budgets = _block_budgets(
        [len(t) for t in texts],
        llm.total_context_chars,
        llm.context.min_block_chars,
        llm.context.max_block_chars,
    )

    ctx_parts: list[str] = []
    cite_parts: list[str] = []
    for i, (r, ctx_text, budget) in enumerate(zip(results, texts, budgets, strict=True), 1):
        p = r["payload"]
        file_stem = p["file_stem"]
        section_path = p["section_path"]
        child_text = p["text"]
        if len(ctx_text) > budget:
            ctx_text = window(ctx_text, r.get("anchor_texts") or child_text, budget)

        ctx_parts.append(f"[{i}] Nguồn: {file_stem} — {section_path}\n---\n{ctx_text}")

        snippet = child_text[:220].replace("\n", " ")
        if len(child_text) > 220:
            snippet += "…"
        cite_parts.append(f"**[{i}]** `{file_stem}` • {section_path}\n> {snippet}")

    context_str = "\n\n---\n\n".join(ctx_parts)
    citations_md = "\n\n---\n\n**📎 Nguồn tham khảo:**\n\n" + "\n\n".join(cite_parts)
    return context_str, citations_md
