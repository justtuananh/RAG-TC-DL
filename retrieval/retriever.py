"""QTKĐ retrieval pipeline: embed → dense search → rerank → parent fetch.

Services (all local Docker, already running):
  Embedding : POST http://localhost:8010/v1/embeddings  (bge-m3, 1024 dims)
  Reranker  : POST http://localhost:8011/v1/rerank      (bge-reranker-v2-m3)
  Qdrant    : http://localhost:6333                     collection: qtkd_rag
"""
from __future__ import annotations

import os
import requests
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

EMBED_URL  = os.getenv("EMBED_URL",  "http://localhost:8010/v1/embeddings")
RERANK_URL = os.getenv("RERANK_URL", "http://localhost:8011/v1/rerank")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = "qtkd_rag"
EMBED_TIMEOUT = 120
RERANK_TIMEOUT = 60

# Funnel widths (Phase 3): search deeper, let reranker decide.
TOP_K = 50          # candidates from dense + BM25 each
RERANK_POOL = 60    # max candidates fed into reranker after RRF + noise filter

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL)
    return _client


def embed_query(text: str) -> list[float]:
    resp = requests.post(
        EMBED_URL,
        json={"input": [text], "model": "model"},
        timeout=EMBED_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    data.sort(key=lambda x: x["index"])
    return data[0]["embedding"]


def dense_search(
    vec: list[float],
    top_k: int = TOP_K,
    file_stem: str | None = None,
) -> list[dict]:
    """Search child chunks, optionally filtered to a specific file_stem."""
    client = _get_client()
    conditions = [FieldCondition(key="is_parent", match=MatchValue(value=False))]
    if file_stem:
        conditions.append(FieldCondition(key="file_stem", match=MatchValue(value=file_stem)))
    hits = client.search(
        collection_name=COLLECTION,
        query_vector=vec,
        query_filter=Filter(must=conditions),
        limit=top_k,
        with_payload=True,
    )
    return [{"id": h.id, "score": h.score, "payload": h.payload} for h in hits]


_LEXICON: dict[str, str] = {
    # Cầu nối từ vựng: trigger (substring, lowercase) → cụm đồng nghĩa nối thêm vào
    # truy vấn embed + BM25 (reranker vẫn nhận query gốc). Nhắm khẩu ngữ/paraphrase
    # và thuật ngữ song ngữ Việt–Anh trong các QTKĐ áp suất.
    "điều kiện môi trường": "điều kiện kiểm định nhiệt độ độ ẩm áp suất khí quyển",
    "sai số cho phép": "sai số giới hạn dung sai độ chính xác cấp chính xác",
    "thời gian quay tự do": "thời gian quay tự do píttông kiểm tra kỹ thuật độ nhớt",
    "độ chênh áp": "độ chênh áp blowdown chênh lệch áp suất đóng áp suất chỉnh đặt",
    "áp suất chỉnh đặt": "áp suất chỉnh đặt set pressure áp suất mở van",
    "thử thủy tĩnh": "thử thủy tĩnh kiểm tra độ kín chịu tải thời gian tối thiểu",
    "kẹp chì": "kẹp chì niêm phong dấu niêm phong kiểm tra bên ngoài",
    "thiết bị chuẩn": "phương tiện kiểm định thiết bị chuẩn áp kế chuẩn",
    "số lần đo": "số lần đo số loạt đo số điểm đo chu trình kiểm định",
    "chu kỳ kiểm định": "chu kỳ kiểm định định kỳ thời hạn tháng xử lý chung",
    "diện tích hiệu dụng": "diện tích hiệu dụng píttông xác định đo lường",
    "van xả áp": "van an toàn van xả áp suất safety valve",
}


def _expand_query(query: str) -> str:
    """Append domain synonyms to bridge vocabulary gaps in embed + BM25.

    Reranker still receives the original query — expanded text degrades
    cross-encoder performance (arXiv 2311.09175).
    """
    q_lower = query.lower()
    extras = [exp for trigger, exp in _LEXICON.items() if trigger in q_lower]
    return (query + " " + " ".join(extras)) if extras else query


def rerank_hits(query: str, hits: list[dict], top_n: int = 5) -> list[dict]:
    """Rerank on PARENT section text for richer context; attach parent_payload.

    Deduplicates by parent_id (one child per section), fetches parent text,
    scores with bge-reranker-v2-m3, returns top_n child hits ordered by
    parent relevance.  Falls back to child text when parent is unavailable.
    """
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
        parent = fetch_parent(pid) if pid else None
        parent_payloads.append(parent)
        documents.append(parent["text"] if parent else h["payload"]["text"])

    resp = requests.post(
        RERANK_URL,
        json={"query": query, "documents": documents, "top_n": len(documents)},
        timeout=RERANK_TIMEOUT,
    )
    resp.raise_for_status()
    results = resp.json()["results"]
    results.sort(key=lambda x: x["relevance_score"], reverse=True)

    out = []
    for r in results[:top_n]:
        idx = r["index"]
        h = dict(unique_hits[idx])
        h["rerank_score"] = r["relevance_score"]
        h["parent_payload"] = parent_payloads[idx]
        out.append(h)
    return out


def fetch_parent(parent_id_hex: str) -> dict | None:
    """Fetch full parent section payload by its chunk_id (hex → uint64 point ID)."""
    if not parent_id_hex:
        return None
    client = _get_client()
    try:
        point_id = int(parent_id_hex, 16)
        results = client.retrieve(
            collection_name=COLLECTION,
            ids=[point_id],
            with_payload=True,
        )
        if results:
            return results[0].payload
    except Exception:
        pass
    return None


from retrieval._constants import (
    NOISE_PATH_MARKERS as _NOISE_PATH_MARKERS,
    is_noise_path as _is_noise_path,
)


def _filter_noise(hits: list[dict]) -> list[dict]:
    """Remove boilerplate form/template sections before reranking."""
    return [
        h for h in hits
        if not _is_noise_path(h["payload"].get("section_path", ""))
    ]


def rrf_fuse(
    dense_hits: list[dict],
    bm25_hits: list[dict],
    k: int = 60,
) -> list[dict]:
    """Reciprocal Rank Fusion of dense and BM25 lists.

    Standard RRF: score(d) = Σ 1/(k + rank_i(d))  for each list i.
    Returns unified list sorted by RRF score descending.
    """
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


def retrieve(query: str, top_k: int = TOP_K, top_n: int = 5) -> list[dict]:
    """Full hybrid pipeline: route → expand → embed + BM25 → RRF → rerank → parent.

    Returns list of top_n hit dicts, each with:
      payload        : child chunk payload (text, section_path, file_stem, kind)
      rerank_score   : float (from bge-reranker, scored on parent text)
      rrf_score      : float (pre-rerank fusion score)
      parent_payload : parent section payload (attached by rerank_hits)
    """
    from .bm25_index import bm25_search
    from .router import route

    expanded = _expand_query(query)
    vec = embed_query(expanded)
    file_stem = route(query)

    dense_hits = dense_search(vec, top_k=top_k, file_stem=file_stem)
    bm25_hits = bm25_search(expanded, top_k=top_k, file_stem=file_stem)

    # Safety fallback: if routing narrowed to too few candidates, retry full corpus
    if file_stem and (len(dense_hits) + len(bm25_hits) < 6):
        dense_hits = dense_search(vec, top_k=top_k)
        bm25_hits = bm25_search(expanded, top_k=top_k)

    fused = _filter_noise(rrf_fuse(dense_hits, bm25_hits))[:RERANK_POOL]
    # rerank_hits now reranks on parent text and attaches parent_payload
    return rerank_hits(query, fused, top_n=top_n)
