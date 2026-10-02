"""Phần lai của truy hồi: tìm dense + BM25, hợp nhất RRF, lọc nhiễu boilerplate,
ghép kết quả đa-file.

search_both gọi Qdrant (dense) và chỉ mục BM25; rrf_fuse hợp nhất hai danh sách theo
payload.chunk_id và sắp theo điểm RRF. filter_noise, rrf_fuse, merge_per_file thuần CPU.
"""

from __future__ import annotations

from core.settings_loader import get_settings
from vectorstore import hybrid_index, qdrant
from vectorstore.noise import is_noise_path


def filter_noise(hits: list[dict]) -> list[dict]:
    """Remove boilerplate form/template sections before reranking."""
    return [h for h in hits if not is_noise_path(h["payload"].get("section_path", ""))]


def rrf_fuse(
    dense_hits: list[dict],
    bm25_hits: list[dict],
    k: int | None = None,
) -> list[dict]:
    """Reciprocal Rank Fusion of dense and BM25 lists.

    Standard RRF: score(d) = Σ 1/(k + rank_i(d))  for each list i.
    Returns unified list sorted by RRF score descending.
    """
    k = k or get_settings().retrieval.rrf_k
    scores: dict[str, float] = {}
    all_hits: dict[str, dict] = {}

    for rank, h in enumerate(dense_hits):
        cid = h["payload"]["chunk_id"]
        all_hits[cid] = h
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)

    for rank, h in enumerate(bm25_hits):
        cid = h["payload"]["chunk_id"]
        if cid not in all_hits:
            all_hits[cid] = h
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)

    sorted_ids = sorted(scores, key=scores.__getitem__, reverse=True)
    fused: list[dict] = []
    for cid in sorted_ids:
        h = dict(all_hits[cid])
        h["rrf_score"] = scores[cid]
        fused.append(h)
    return fused


def merge_per_file(reranked: list[dict], stems: frozenset[str], top_n: int) -> list[dict]:
    """Ghép kết quả đã rerank cho câu hỏi đa-file: BẢO ĐẢM mỗi file có đại diện.

    Cross-encoder chấm điểm theo độ khớp bề mặt nên file có cụm từ vựng trùng
    câu hỏi nhiều hơn vẫn có thể chiếm hết top_n - quota tối thiểu mỗi file
    (top_n // số file, ≥1) lấy theo thứ tự rerank trong file đó; phần dư bù bằng
    thứ tự rerank toàn cục; cuối cùng sắp lại theo rerank_score để [n] ổn định.
    """
    by_file: dict[str, list[dict]] = {}
    for h in reranked:
        by_file.setdefault(h["payload"]["file_stem"], []).append(h)

    quota = max(1, top_n // max(len(stems), 1))
    chosen: list[dict] = []
    chosen_ids: set[int] = set()
    for s in sorted(stems):
        for h in by_file.get(s, [])[:quota]:
            chosen.append(h)
            chosen_ids.add(id(h))
    for h in reranked:
        if len(chosen) >= top_n:
            break
        if id(h) not in chosen_ids:
            chosen.append(h)
            chosen_ids.add(id(h))
    chosen.sort(key=lambda h: h.get("rerank_score", 0.0), reverse=True)
    return chosen[:top_n]


def search_both(
    vec: list[float], expanded_query: str, *, top_k: int, file_stem: str | None = None
) -> tuple[list[dict], list[dict]]:
    """Một lượt dense + BM25 trên cùng phạm vi (toàn kho hoặc một file)."""
    dense = qdrant.dense_search(vec, top_k=top_k, file_stem=file_stem)
    sparse = hybrid_index.bm25_search(expanded_query, top_k=top_k, file_stem=file_stem)
    return dense, sparse
