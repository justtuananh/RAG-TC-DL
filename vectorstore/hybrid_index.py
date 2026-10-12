"""Nửa thưa của chỉ mục lai: BM25 trong bộ nhớ, dựng lười từ payload chunk con trong Qdrant.

Built lazily on first call to bm25_search(); after that ingestion refreshes only
the files it touched (``refresh_files``) instead of re-scrolling the whole
collection. Tokenizer keeps technical codes/units intact (e.g. 1.061:2021, MPa,
bar, DN50, 0.05%).
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from core.settings_loader import get_settings
from embedding.sparse_embedder import sparse_document_text, tokenize
from vectorstore import qdrant
from vectorstore.noise import (
    is_noise_path as _is_noise_path,
)


@dataclass(frozen=True)
class _Index:
    """Ảnh chụp bất biến của chỉ mục: thay cả khối, nên luồng đọc không thấy trạng thái nửa vời."""

    bm25: BM25Okapi | None  # None khi kho rỗng (BM25Okapi không nhận corpus rỗng)
    chunks: tuple[dict, ...]  # child chunk payloads, theo point id tăng dần như Qdrant scroll
    corpus: tuple[list[str], ...]  # token của từng chunk, giữ lại để cập nhật không token hóa lại


_index: _Index | None = None
# Chỉ tuần tự hóa việc DỰNG chỉ mục; tìm kiếm đọc ``_index`` một lần, không cần khóa.
_build_lock = threading.Lock()


# ── index build ───────────────────────────────────────────────────────────────


def _is_noise(payload: dict) -> bool:
    return _is_noise_path(payload.get("section_path", ""))


def _point_order(payload: dict) -> int:
    """Thứ tự point id của Qdrant (chunk_id hex → uint64) để mọi cách dựng cho cùng kết quả."""
    return int(payload["chunk_id"], 16)


def _make_index(entries: list[tuple[dict, list[str]]]) -> _Index:
    entries = sorted(entries, key=lambda entry: _point_order(entry[0]))
    chunks = tuple(chunk for chunk, _ in entries)
    corpus = tuple(tokens for _, tokens in entries)
    return _Index(bm25=BM25Okapi(list(corpus)) if corpus else None, chunks=chunks, corpus=corpus)


def _entries(payloads: list[dict]) -> list[tuple[dict, list[str]]]:
    # Exclude boilerplate "Mẫu biên bản" / "(Quy định)" sections from BM25
    return [(c, tokenize(sparse_document_text(c))) for c in payloads if not _is_noise(c)]


def _ensure_index() -> _Index:
    global _index
    current = _index
    if current is not None:
        return current
    with _build_lock:
        if _index is None:
            _index = _make_index(_entries(qdrant.scroll_child_payloads()))
        return _index


def refresh_files(file_stems: Iterable[str]) -> None:
    """Nạp lại chunk của các file vừa nhúng/xóa, giữ nguyên phần còn lại của chỉ mục.

    Chỉ quét Qdrant cho đúng các file đó; file đã bị xóa thì không còn chunk nào
    và tự rơi khỏi chỉ mục. Chưa dựng chỉ mục thì không làm gì: lần tìm đầu tiên
    sẽ dựng từ đầu.
    """
    global _index
    stems = frozenset(file_stems)
    if not stems:
        return
    with _build_lock:
        current = _index
        if current is None:
            return
        kept = [
            (chunk, tokens)
            for chunk, tokens in zip(current.chunks, current.corpus, strict=True)
            if chunk.get("file_stem") not in stems
        ]
        fresh = _entries(qdrant.scroll_child_payloads(file_stems=stems))
        _index = _make_index(kept + fresh)


def invalidate() -> None:
    """Drop the cached index so the next bm25_search() rebuilds it from Qdrant."""
    global _index
    with _build_lock:
        _index = None


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
    index = _ensure_index()
    bm25, chunks = index.bm25, index.chunks
    if bm25 is None:
        return []
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
        hits.append(
            {
                "id": idx,
                "bm25_score": float(scores[idx]),
                "payload": chunk,
            }
        )
        if len(hits) >= top_k:
            break
    return hits
