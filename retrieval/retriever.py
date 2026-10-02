"""Truy hồi lai đầy đủ: định tuyến → mở rộng truy vấn → dense + BM25 → RRF → lọc nhiễu
→ rerank (cross-encoder trên section cha) → trả chunk con kèm section cha.

Mỗi hit trả về có: payload (chunk con), rerank_score, rrf_score, parent_payload.
"""

from __future__ import annotations

from core.settings_loader import get_settings
from embedding import embedder
from reranking import reranker
from retrieval import hybrid_retriever as hybrid
from retrieval import router
from retrieval.query_expansion import expand_query


def retrieve(query: str, top_k: int | None = None, top_n: int | None = None) -> list[dict]:
    cfg = get_settings().retrieval
    top_k = top_k or cfg.top_k
    top_n = top_n or cfg.top_n
    expanded = expand_query(query)
    vec = embedder.embed_query(expanded)
    stems = router.route_files(query)
    if len(stems) >= 2:
        return _retrieve_per_file(query, vec, expanded, stems, top_k=top_k, top_n=top_n)
    file_stem = next(iter(stems)) if stems else None
    dense, sparse = hybrid.search_both(vec, expanded, top_k=top_k, file_stem=file_stem)
    # Định tuyến thu hẹp quá ít ứng viên: tìm lại toàn kho.
    if file_stem and len(dense) + len(sparse) < cfg.min_routed_candidates:
        dense, sparse = hybrid.search_both(vec, expanded, top_k=top_k)
    fused = hybrid.filter_noise(hybrid.rrf_fuse(dense, sparse))[: cfg.rerank_pool]
    return reranker.rerank_hits(query, fused, top_n=top_n)


def _retrieve_per_file(
    query: str, vec: list[float], expanded: str, stems: frozenset[str], *, top_k: int, top_n: int
) -> list[dict]:
    """Câu so sánh ≥2 thiết bị: chạy phễu RIÊNG cho từng file rồi rerank chung.

    Một phễu toàn kho bị cụm từ vựng áp đảo (3 file áp kế píttông) đè bẹp file thiểu
    số; đo Q115/Q116: top-5 mất hết chunk 'van an toàn' → model từ chối oan.
    """
    pool = max(top_n * 2, get_settings().retrieval.rerank_pool // len(stems))
    fused: list[dict] = []
    for stem in sorted(stems):
        dense, sparse = hybrid.search_both(vec, expanded, top_k=top_k, file_stem=stem)
        fused.extend(hybrid.filter_noise(hybrid.rrf_fuse(dense, sparse))[:pool])
    reranked = reranker.rerank_hits(query, fused, top_n=len(fused))
    return hybrid.merge_per_file(reranked, stems, top_n)
