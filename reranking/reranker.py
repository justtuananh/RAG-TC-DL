"""Cross-encoder reranker: chấm lại ứng viên trên text section CHA (bge-reranker-v2-m3).

Document đưa vào cross-encoder được dựng bởi build_rerank_doc (tiền tố breadcrumb +
cửa sổ neo child); hit trả về kèm parent_payload để tầng trên dựng ngữ cảnh.
"""

from __future__ import annotations

import logging

import requests

from core.settings_loader import get_settings
from vectorstore import qdrant

logger = logging.getLogger(__name__)


def build_rerank_doc(payload: dict, parent: dict | None) -> str:
    """Dựng document cho cross-encoder từ một ứng viên (chỉ dùng lúc rerank,
    KHÔNG lưu vào store — text trong payload/Qdrant giữ nguyên).

    Hai cơ chế đo được trên bộ MISS (2026-06-11):
    1. Tiền tố "file — breadcrumb": mục tiêu đề-đúng nhưng body không nhắc tên
       thiết bị (4.1 Điều kiện kiểm định = bullet đơn vị) bị cross-encoder chấm
       thua mục anh em giàu chữ có tên thiết bị → thêm cùng tiền tố cho MỌI ứng
       viên thì tín hiệu tên file/thiết bị cân bằng (Q12: 8→2, Q18: 8→2, Q22: 5→3).
    2. Cửa sổ neo theo CHILD: section dài (6.3.3 của 1.159 ≈ 7,6k ký tự) bị server
       cắt ở 512 token TRƯỚC khi thấy nội dung trả lời — lấy cửa sổ quanh vị trí
       child match thay vì đầu section (Q39: 9→1, Q48: 7→1; công thức của Q48 nằm
       ở ký tự 1857, ngoài cửa sổ cũ).
    """
    cfg = get_settings().reranking
    text = parent["text"] if parent else payload["text"]
    if len(text) > cfg.doc_cap_chars:
        child = payload["text"]
        idx = text.find(child[:80])
        if idx < 0:
            idx = 0
        heading = text.split("\n", 1)[0]
        start = max(0, idx - cfg.doc_back_chars)
        window = text[start : start + cfg.doc_cap_chars]
        text = (heading + "\n…" + window) if start > 0 else window
    return f"{payload['file_stem']} — {payload['section_path']}\n{text}"


def rerank_hits(query: str, hits: list[dict], top_n: int | None = None) -> list[dict]:
    """Rerank on PARENT section text for richer context; attach parent_payload.

    Deduplicates by parent_id (one child per section), fetches parent text,
    scores with bge-reranker-v2-m3, returns top_n child hits ordered by
    parent relevance.  Falls back to child text when parent is unavailable.
    Documents are built by build_rerank_doc (breadcrumb prefix + child-anchored window).
    """
    settings = get_settings()
    if top_n is None:
        top_n = settings.retrieval.top_n
    if not hits:
        return []

    # One representative child per parent (hits are pre-sorted by RRF score)
    seen: dict = {}
    for h in hits:
        pid = h["payload"].get("parent_id")
        if pid not in seen:
            seen[pid] = h
    unique_hits = list(seen.values())

    # Fetch parent text for each unique section
    parent_payloads: list[dict | None] = []
    documents: list[str] = []
    for h in unique_hits:
        pid = h["payload"].get("parent_id")
        parent = qdrant.fetch_parent(pid) if pid else None
        parent_payloads.append(parent)
        documents.append(build_rerank_doc(h["payload"], parent))

    try:
        resp = requests.post(
            settings.services.rerank_url,
            json={"query": query, "documents": documents, "top_n": len(documents)},
            timeout=settings.reranking.timeout_s,
        )
        resp.raise_for_status()
        results = resp.json()["results"]
    except Exception as exc:
        # Reranker unavailable — fall back to RRF ordering
        logger.warning("Reranker failed (%s), falling back to RRF order", exc)
        out = []
        for i, h in enumerate(unique_hits[:top_n]):
            h2 = dict(h)
            h2["rerank_score"] = h2.get("rrf_score", 0.0)
            h2["parent_payload"] = parent_payloads[i]
            out.append(h2)
        return out

    results.sort(key=lambda x: x["relevance_score"], reverse=True)

    out = []
    for r in results[:top_n]:
        idx = r["index"]
        h = dict(unique_hits[idx])
        h["rerank_score"] = r["relevance_score"]
        h["parent_payload"] = parent_payloads[idx]
        out.append(h)
    return out
