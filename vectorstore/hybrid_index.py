"""Nửa thưa của chỉ mục lai: BM25 trong bộ nhớ, dựng lười từ payload chunk con trong Qdrant.

Built lazily on first call to bm25_search(). Tokenizer keeps technical
codes/units intact (e.g. 1.061:2021, MPa, bar, DN50, 0.05%).
"""
from __future__ import annotations

from typing import Optional

from rank_bm25 import BM25Okapi

from core.settings_loader import get_settings
from embedding.sparse_embedder import sparse_document_text, tokenize
from retrieval.noise import (
    NOISE_PATH_MARKERS as _NOISE_PATH_MARKERS,
    is_noise_path as _is_noise_path,
)
from vectorstore import qdrant

_bm25: Optional[BM25Okapi] = None
_chunks: Optional[list[dict]] = None   # child chunk payloads in corpus order


# ── index build ───────────────────────────────────────────────────────────────

def _is_noise(payload: dict) -> bool:
    return _is_noise_path(payload.get("section_path", ""))


def _ensure_index() -> tuple[BM25Okapi, list[dict]]:
    global _bm25, _chunks
    if _bm25 is None:
        raw = qdrant.scroll_child_payloads()
        # Exclude boilerplate "Mẫu biên bản" / "(Quy định)" sections from BM25
        _chunks = [c for c in raw if not _is_noise(c)]
        corpus = [tokenize(sparse_document_text(c)) for c in _chunks]
        _bm25 = BM25Okapi(corpus)
    return _bm25, _chunks


def invalidate() -> None:
    """Drop the cached index so the next bm25_search() rebuilds it from Qdrant.

    Call after upserting new chunks (e.g. a document upload) — _ensure_index()
    otherwise never re-scrolls Qdrant once built.
    """
    global _bm25, _chunks
    _bm25, _chunks = None, None


# ── public API ────────────────────────────────────────────────────────────────

def bm25_search(
    query: str,
    top_k: int | None = None,
    file_stem: str | None = None,
) -> list[dict]:
    """Return top_k BM25 hits: {id, bm25_score, payload}.

    When file_stem is given, only chunks from that file are returned.
    Scans the full sorted list to find enough file-specific hits.
    """
    top_k = top_k or get_settings().retrieval.top_k
    bm25, chunks = _ensure_index()
    tokens = tokenize(query)
    scores = bm25.get_scores(tokens)

    indexed = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    hits: list[dict] = []
    # When filtering by file_stem we scan the whole list; otherwise stop at top_k*3.
    scan_limit = len(indexed) if file_stem else top_k * 3
    for idx in indexed[:scan_limit]:
        if scores[idx] <= 0:
            break
        chunk = chunks[idx]
        if file_stem and chunk.get("file_stem") != file_stem:
            continue
        hits.append({
            "id": idx,
            "bm25_score": float(scores[idx]),
            "payload": chunk,
        })
        if len(hits) >= top_k:
            break
    return hits
