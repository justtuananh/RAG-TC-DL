"""Phần lai của truy hồi: tìm dense + BM25, hợp nhất RRF, lọc nhiễu boilerplate,
ghép kết quả đa-file.

search_both gọi Qdrant (dense) và chỉ mục BM25; rrf_fuse hợp nhất hai danh sách theo
payload.chunk_id và sắp theo điểm RRF. filter_noise, rrf_fuse, merge_per_file thuần CPU.
"""

from __future__ import annotations

import re

from core.settings_loader import get_settings
from retrieval import doc_profile
from retrieval.normalize import fold
from vectorstore import hybrid_index, qdrant
from vectorstore.noise import is_noise_path

_APPENDIX_LABEL_RE = re.compile(r"^(Phụ lục\s+[A-Z])\b")
_PARENTHESES_RE = re.compile(r"\([^)]*\)")


def _is_content_appendix(payload: dict) -> bool:
    """Phụ lục mang nội dung thật (bảng sai số "Bình định mức - Yêu cầu chung"), không phải mẫu biểu.

    ``is_noise_path`` loại mọi phụ lục có tiêu đề trần ("Phụ lục C") hoặc "(Quy định)" vì mẫu biên bản /
    giấy chứng nhận nằm ở đó; nhưng nhiều QTKĐ đặt bảng yêu cầu kỹ thuật trong phụ lục quy định. Tên thật
    của phụ lục (dòng sau tiêu đề, ``doc_profile``) phân biệt hai loại: có chữ "Mẫu" mới là mẫu biểu.
    """
    match = _APPENDIX_LABEL_RE.match(payload.get("section_path", ""))
    if not match:
        return False
    profile = doc_profile.profile_for(payload.get("file_stem", ""))
    if profile is None:
        return False
    number = match.group(1).lower()
    for section in profile.sections:
        if section.number.lower() == number:
            title = fold(_PARENTHESES_RE.sub("", section.title))
            return bool(title.strip()) and "mau" not in title.split()
    return False


def filter_noise(hits: list[dict]) -> list[dict]:
    """Remove boilerplate form/template sections before reranking (giữ phụ lục có nội dung thật)."""
    return [
        h
        for h in hits
        if not is_noise_path(h["payload"].get("section_path", "")) or _is_content_appendix(h["payload"])
    ]


def rrf_fuse(
    dense_hits: list[dict],
    bm25_hits: list[dict],
    k: int | None = None,
    *,
    w_dense: float | None = None,
    w_bm25: float | None = None,
) -> list[dict]:
    """Reciprocal Rank Fusion có trọng số cho dense và BM25.

    score(d) = w_dense / (k + rank_dense(d) + 1) + w_bm25 / (k + rank_bm25(d) + 1).
    ``k`` và hai trọng số mặc định đọc từ settings LÚC GỌI; nhân cả hai trọng số với
    cùng một hằng số không đổi thứ tự nên chỉ TỶ LỆ dense/BM25 có tác dụng.
    Trả danh sách hợp nhất sắp theo điểm RRF giảm dần.
    """
    cfg = get_settings().retrieval
    k = k or cfg.rrf_k
    if w_dense is None:
        w_dense = cfg.rrf_weight_dense
    if w_bm25 is None:
        w_bm25 = cfg.rrf_weight_bm25
    scores: dict[str, float] = {}
    all_hits: dict[str, dict] = {}

    for rank, h in enumerate(dense_hits):
        cid = h["payload"]["chunk_id"]
        all_hits[cid] = h
        scores[cid] = scores.get(cid, 0.0) + w_dense / (k + rank + 1)

    for rank, h in enumerate(bm25_hits):
        cid = h["payload"]["chunk_id"]
        if cid not in all_hits:
            all_hits[cid] = h
        scores[cid] = scores.get(cid, 0.0) + w_bm25 / (k + rank + 1)

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
