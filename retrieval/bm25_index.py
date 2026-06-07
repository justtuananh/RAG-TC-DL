"""BM25 in-memory index over QTKĐ child chunks, loaded from Qdrant.

Built lazily on first call to bm25_search(). Tokenizer keeps technical
codes/units intact (e.g. 1.061:2021, MPa, bar, DN50, 0.05%).
"""
from __future__ import annotations

import os
import re
from typing import Optional

from rank_bm25 import BM25Okapi
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = "qtkd_rag"

_bm25: Optional[BM25Okapi] = None
_chunks: Optional[list[dict]] = None   # child chunk payloads in corpus order


# ── tokenizer ─────────────────────────────────────────────────────────────────

_SPLIT_RE = re.compile(r'[\s,;!()\[\]{}<>"\'\\|]+')


def tokenize(text: str) -> list[str]:
    """Lowercase split preserving codes like 1.061:2021, MPa, bar, DN≤50."""
    tokens = _SPLIT_RE.split(text.lower())
    return [t for t in tokens if t]


# ── index build ───────────────────────────────────────────────────────────────

_NOISE_PATH_MARKERS = (
    "Mẫu biên bản", "Mẫu Biên bản",
    "Mẫu giấy", "Mẫu Giấy",
    "(Quy định)",
)


def _is_noise(payload: dict) -> bool:
    sp = payload.get("section_path", "")
    return any(m in sp for m in _NOISE_PATH_MARKERS)


def _corpus_text(payload: dict) -> str:
    """Include file_stem + section_path so BM25 can match QTKĐ numbers (e.g. 1.062, 1.063)."""
    parts = [
        payload.get("file_stem", ""),
        payload.get("section_path", ""),
        payload.get("text", ""),
    ]
    return " ".join(p for p in parts if p)


def _scroll_child_chunks() -> list[dict]:
    client = QdrantClient(url=QDRANT_URL)
    child_filter = Filter(
        must=[FieldCondition(key="is_parent", match=MatchValue(value=False))]
    )
    payloads: list[dict] = []
    offset = None
    while True:
        results, next_offset = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=child_filter,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        payloads.extend(r.payload for r in results)
        if next_offset is None:
            break
        offset = next_offset
    return payloads


def _ensure_index() -> tuple[BM25Okapi, list[dict]]:
    global _bm25, _chunks
    if _bm25 is None:
        raw = _scroll_child_chunks()
        # Exclude boilerplate "Mẫu biên bản" / "(Quy định)" sections from BM25
        _chunks = [c for c in raw if not _is_noise(c)]
        corpus = [tokenize(_corpus_text(c)) for c in _chunks]
        _bm25 = BM25Okapi(corpus)
    return _bm25, _chunks


# ── public API ────────────────────────────────────────────────────────────────

def bm25_search(
    query: str,
    top_k: int = 20,
    file_stem: str | None = None,
) -> list[dict]:
    """Return top_k BM25 hits: {id, bm25_score, payload}.

    When file_stem is given, only chunks from that file are returned.
    Scans the full sorted list to find enough file-specific hits.
    """
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
