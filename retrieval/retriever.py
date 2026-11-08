"""Truy hồi lai đầy đủ: định tuyến → mở rộng truy vấn → dense + BM25 → RRF → lọc nhiễu
→ rerank (cross-encoder trên section cha) → trả chunk con kèm section cha.

Mỗi hit trả về có: payload (chunk con), rerank_score, rrf_score, parent_payload.
"""

from __future__ import annotations

from core.settings_loader import get_settings
from embedding import embedder
from reranking import reranker
from retrieval import hybrid_retriever as hybrid
from retrieval import reference_lookup, router, subsection
from retrieval.normalize import fold, semantic_query
from retrieval.query_expansion import expand_query


def _section_pool(hits: list[dict], limit: int) -> list[dict]:
    """Cap distinct sections, retaining all matched child anchors of each section."""
    chosen = set()
    out = []
    for hit in hits:
        payload = hit['payload']
        key = (payload['file_stem'], payload.get('parent_id') or payload['chunk_id'])
        if key not in chosen:
            if len(chosen) >= limit:
                continue
            chosen.add(key)
        out.append(hit)
    return out


def annotate_subsections(hits: list[dict]) -> list[dict]:
    """Gắn ``cited_section_path`` (đường dẫn tới MỤC CON chứa đoạn khớp nhất) cho từng hit.

    Chỉ thêm khóa, không đổi payload/thứ hạng; tắt bằng retrieval.locate_subsection=false.
    """
    cfg = get_settings().retrieval
    if not cfg.locate_subsection:
        return hits
    for hit in hits:
        payload = hit["payload"]
        parent = hit.get("parent_payload")
        if not parent or "cited_section_path" in hit:
            continue
        anchors = hit.get("anchor_texts") or [payload["text"]]
        hit["cited_section_path"] = subsection.locate(
            payload.get("section_path", ""),
            parent.get("text", ""),
            anchors[0],
            max_title_chars=cfg.subsection_title_chars,
        )
    return hits


def retrieve(query: str, top_k: int | None = None, top_n: int | None = None) -> list[dict]:
    return annotate_subsections(_retrieve(query, top_k, top_n))


def _retrieve(query: str, top_k: int | None = None, top_n: int | None = None) -> list[dict]:
    settings = get_settings()
    multi = settings.llm.multi_document
    if multi.enabled and multi.extractive_enabled and reference_lookup.is_reference_query(query):
        references = reference_lookup.lookup(query, router.known_files())
        if references:
            return references
    cfg = get_settings().retrieval
    top_k = top_k or cfg.top_k
    top_n = top_n or cfg.top_n
    stems = router.route_files(query)
    topic = semantic_query(query) if len(stems) >= 2 else query
    expanded = expand_query(topic)
    ranking_query = expanded if fold(topic) == topic.lower() else topic
    vec = embedder.embed_query(expanded)
    if len(stems) >= 2:
        return _retrieve_per_file(ranking_query, vec, expanded, stems, top_k=top_k, top_n=top_n)
    if not stems and cfg.coverage_per_file > 0:
        covered = _retrieve_coverage(ranking_query, vec, expanded, top_k=top_k)
        if covered:
            return covered
    file_stem = next(iter(stems)) if stems else None
    dense, sparse = hybrid.search_both(vec, expanded, top_k=top_k, file_stem=file_stem)
    # Định tuyến thu hẹp quá ít ứng viên: tìm lại toàn kho.
    if file_stem and len(dense) + len(sparse) < cfg.min_routed_candidates:
        dense, sparse = hybrid.search_both(vec, expanded, top_k=top_k)
    fused = _section_pool(hybrid.filter_noise(hybrid.rrf_fuse(dense, sparse)), cfg.rerank_pool)
    return reranker.rerank_hits(ranking_query, fused, top_n=top_n)


def _retrieve_per_file(
    query: str, vec: list[float], expanded: str, stems: frozenset[str], *, top_k: int, top_n: int
) -> list[dict]:
    """Câu so sánh ≥2 thiết bị: chạy phễu RIÊNG cho từng file rồi rerank chung.

    Một phễu toàn kho bị cụm từ vựng áp đảo (3 file áp kế píttông) đè bẹp file thiểu
    số; đo Q115/Q116: top-5 mất hết chunk 'van an toàn' → model từ chối oan.
    Mỗi file được ``top_n_per_file`` nguồn thay vì chia ``top_n``: đo Q115, chia 5 nguồn
    cho 2 file làm mất mục 5.1 của 1.159 (thứ 4 trong file) và model gán giá trị của
    1.061 cho 1.159.
    """
    cfg = get_settings().retrieval
    top_n = max(top_n, cfg.top_n_per_file * len(stems))
    pool = max(top_n * 2, cfg.rerank_pool // len(stems))
    fused: list[dict] = []
    for stem in sorted(stems):
        dense, sparse = hybrid.search_both(vec, expanded, top_k=top_k, file_stem=stem)
        fused.extend(_section_pool(hybrid.filter_noise(hybrid.rrf_fuse(dense, sparse)), pool))
    reranked = reranker.rerank_hits(query, fused, top_n=len(fused))
    return hybrid.merge_per_file(reranked, stems, top_n)


def _retrieve_coverage(query: str, vec: list[float], expanded: str, *, top_k: int) -> list[dict]:
    """Câu hỏi KHÔNG nêu thiết bị/QTKĐ nào: phễu riêng cho từng tài liệu, rerank chung, giữ
    ``coverage_per_file`` mục tốt nhất mỗi tài liệu.

    Một phễu toàn kho bị vài tài liệu cùng từ vựng áp đảo nên top-N thiếu hẳn tài liệu khác
    (đo bộ 200 câu: câu hỏi chung chung chỉ có nguồn của 5/7 tài liệu) và model chỉ trả lời
    một vài tài liệu. Tài liệu không liên quan có điểm rerank thấp nên bị ``filter_by_confidence``
    loại sau đó; trả [] (rơi về phễu toàn kho) khi có < 2 tài liệu.
    """
    cfg = get_settings().retrieval
    files = sorted(router.known_files())
    if len(files) < 2:
        return []
    fused: list[dict] = []
    for stem in files:
        dense, sparse = hybrid.search_both(vec, expanded, top_k=top_k, file_stem=stem)
        fused.extend(
            _section_pool(
                hybrid.filter_noise(hybrid.rrf_fuse(dense, sparse)), cfg.coverage_pool_per_file
            )
        )
    if not fused:
        return []
    reranked = reranker.rerank_hits(query, fused, top_n=len(fused))
    taken: dict[str, int] = {}
    out: list[dict] = []
    for hit in reranked:
        stem = hit["payload"]["file_stem"]
        if taken.get(stem, 0) < cfg.coverage_per_file:
            taken[stem] = taken.get(stem, 0) + 1
            out.append(hit)
        if len(out) >= cfg.coverage_max_sources:
            break
    return out
