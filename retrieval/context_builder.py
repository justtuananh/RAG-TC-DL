"""Dựng ngữ cảnh + trích dẫn cho LLM từ kết quả truy hồi.

Lọc đuôi nguồn điểm thấp, chia ngân sách ký tự theo thứ hạng nguồn, cắt nguồn dài quanh các
đoạn con khớp của nó (đoạn neo) rồi ghép thành context_str + citations_md đánh số [n].
"""

from __future__ import annotations

from core.settings_loader import get_settings
from retrieval import quote

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


def _render(parent: str, spans: list[tuple[int, int]], chosen: set[int]) -> str:
    """Các khối đã chọn theo thứ tự trong mục, nguyên văn cả khoảng trắng giữa các khối liền
    nhau; chỉ chỗ thật sự bỏ qua mới đánh dấu "…"."""
    runs: list[tuple[int, int]] = []
    for n in sorted(chosen):
        if runs and n == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], n)
        else:
            runs.append((n, n))
    out = "\n…\n".join(parent[spans[a][0] : spans[b][1]] for a, b in runs)
    if runs[0][0] > 0:
        out = "…\n" + out
    if runs[-1][1] < len(spans) - 1:
        out += "\n…"
    return out


def _anchor_units(texts: list[str], first: int, last: int) -> list[set[int]]:
    """Các phương án khối cho một đoạn neo, từ đầy đủ tới tối thiểu: kèm công thức nó nói tới
    và danh sách "trong đó" của công thức; chỉ kèm công thức; chỉ đoạn neo."""
    core = quote.expand_anchor(texts, first, last)
    full = core.union(*(quote.definitions_after(texts, i) for i in core))
    return [full, core, set(range(first, last + 1))]


def _grow(
    parent: str,
    spans: list[tuple[int, int]],
    chosen: set[int],
    extents: list[list[int]],
    budget: int,
) -> None:
    """Phần dư ngân sách: mở rộng từng khúc đã chọn ra khối kề (sau rồi trước), lần lượt theo
    thứ hạng đoạn neo, tới khi không thêm được khối trọn nào."""
    grown = True
    while grown:
        grown = False
        for extent in extents:
            for side, step in ((1, 1), (0, -1)):
                k = extent[side] + step
                while k in chosen:
                    k += step
                if 0 <= k < len(spans) and len(_render(parent, spans, chosen | {k})) <= budget:
                    chosen.add(k)
                    extent[side] = k
                    grown = True


def _trim(parent: str, anchors: list[str], budget: int) -> str:
    """Khối chứa đoạn neo dài hơn ngân sách (bảng lớn, mục không chia dòng trống): cắt ``budget``
    ký tự quanh đoạn neo đầu tiên tìm thấy, theo ranh giới dòng (``_snap``)."""
    for text in anchors:
        pos = _find(parent, text)
        if pos >= 0:
            break
    else:
        pos, text = 0, ""
    back = 0 if text.rstrip().endswith(":") else max(0, budget - len(text)) // 2
    start = max(0, min(pos - back, len(parent) - budget))
    keep = (pos, pos + len(text)) if text else None
    start, end = _snap(parent, start, min(start + budget, len(parent)), keep)
    return ("…\n" if start > 0 else "") + parent[start:end] + ("\n…" if end < len(parent) else "")


def window(parent: str, anchors: str | list[str], budget: int) -> str:
    """Tối đa ``budget`` ký tự của mục cha, dựng từ các khối quanh đoạn neo.

    Đoạn neo là các đoạn con khớp của mục, theo thứ hạng RRF (``anchor_texts``). Lần lượt theo
    thứ hạng, mỗi đoạn neo thêm khối của nó cùng công thức nó nói tới (``retrieval.quote``):
    câu dẫn ":" kéo công thức sau nó, dòng "trong đó" kéo công thức trên nó, công thức kéo
    danh sách "trong đó" của nó; không vừa thì thử bản rút gọn, rồi bỏ qua. Phần dư mở rộng
    quanh các khúc đã chọn. Chỉ lấy khối trọn nên không cắt dở công thức.
    QTKĐ 1.159 mục 6.3.2 (đo 2026-10-07): đoạn khớp thứ ba dẫn vào công thức kết luận $A_{0t}$
    ở cuối mục; cửa sổ cũ giữ 2 đoạn neo và luôn dành một phần cho đầu mục (bảng điểm áp
    suất, không liên quan) nên cắt mất công thức đó.
    """
    anchors = [anchors] if isinstance(anchors, str) else anchors
    spans = quote.section_blocks(parent)
    texts = [parent[a:b] for a, b in spans]
    located = [f for f in (quote.locate_anchor(parent, spans, a) for a in anchors) if f]
    if not located and spans:
        located = [(0, 0)]  # đoạn neo không có trong mục: lấy từ đầu mục
    chosen: set[int] = set()
    extents: list[list[int]] = []
    for first, last in located:
        for unit in _anchor_units(texts, first, last):
            if unit <= chosen:
                break
            if len(_render(parent, spans, chosen | unit)) <= budget:
                chosen |= unit
                extents.append([min(unit), max(unit)])
                break
    if not chosen:
        return _trim(parent, anchors, budget)
    _grow(parent, spans, chosen, extents, budget)
    return _render(parent, spans, chosen)


def _block_budgets(lengths: list[int], total: int, floor: int, cap: int) -> list[int]:
    """Ngân sách ký tự từng nguồn theo thứ hạng: nguồn xếp trên lấy đủ phần nó cần trước, mỗi
    nguồn xếp dưới vẫn được giữ chỗ ``floor`` (hoặc độ dài của nó nếu ngắn hơn). Trần ``cap``
    chỉ áp cho nguồn sau nguồn top: QTKĐ 1.159 mục 6.3.2 (5 623 ký tự, điểm rerank 0,999) bị
    cắt ở trần trong khi nguồn [5] điểm 0,68 vào trọn (đo 2026-10-07)."""
    floor = min(floor, total // max(len(lengths), 1))
    reserve = [min(n, floor) for n in lengths]
    budgets: list[int] = []
    remaining = total
    for i, n in enumerate(lengths):
        limit = n if i == 0 else min(n, cap)
        share = max(reserve[i], min(limit, remaining - sum(reserve[i + 1 :])))
        budgets.append(share)
        remaining -= share
    return budgets


_SOURCE_SEP = "\n\n---\n\n"


def build_context_and_citations(results: list[dict]) -> tuple[str, str]:
    """Dựng (context_str cho system prompt, citations_md cho UI) từ kết quả retrieve.

    Context dùng PARENT text (đủ ngữ cảnh) với ngân sách theo thứ hạng ``_block_budgets``
    trong trần tổng ``total_context_chars`` (vừa num_ctx cùng prompt và câu trả lời; tính cả
    đầu mục "[n] Nguồn: …" và dấu ngăn cách) và trần
    ``max_block_chars`` cho nguồn sau nguồn top: ngữ cảnh ~18-20k ký tự từng chôn fact (đo
    2026-06-10). Nguồn dài hơn ngân sách lấy cửa sổ quanh các đoạn neo (``window``). Citations dùng
    snippet CHILD (cap 220). Đánh số [n] khớp 1:1 giữa hai phần và với results[n-1].
    """
    llm = get_settings().llm
    texts = [(r.get("parent_payload") or r["payload"])["text"] for r in results]
    headers = [
        f"[{i}] Nguồn: {r['payload']['file_stem']} — {r['payload']['section_path']}\n---\n"
        for i, r in enumerate(results, 1)
    ]
    # Đầu mục nguồn và dấu ngăn cách cũng chiếm chỗ trong trần tổng.
    overhead = sum(map(len, headers)) + len(_SOURCE_SEP) * max(len(results) - 1, 0)
    budgets = _block_budgets(
        [len(t) for t in texts],
        llm.total_context_chars - overhead,
        llm.context.min_block_chars,
        llm.context.max_block_chars,
    )

    ctx_parts: list[str] = []
    cite_parts: list[str] = []
    for r, header, ctx_text, budget in zip(results, headers, texts, budgets, strict=True):
        p = r["payload"]
        child_text = p["text"]
        if len(ctx_text) > budget:
            ctx_text = window(ctx_text, r.get("anchor_texts") or child_text, budget)

        ctx_parts.append(header + ctx_text)

        snippet = child_text[:220].replace("\n", " ")
        if len(child_text) > 220:
            snippet += "…"
        i = len(cite_parts) + 1
        cite_parts.append(f"**[{i}]** `{p['file_stem']}` • {p['section_path']}\n> {snippet}")

    context_str = _SOURCE_SEP.join(ctx_parts)
    citations_md = "\n\n---\n\n**📎 Nguồn tham khảo:**\n\n" + "\n\n".join(cite_parts)
    return context_str, citations_md
