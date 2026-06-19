"""Embed QTKĐ chunks and upsert into Qdrant collection `qtkd_rag`.

Services used (all local Docker, already running):
  - Embedding: POST http://localhost:8010/v1/embeddings  → 1024-dim vectors
  - Qdrant:    http://localhost:6333                     → collection qtkd_rag

Run:
  python -m index.embed_store [--md-dir build/spike_a] [--force]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
import requests
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

import re

from .chunker import Chunk, parse_directory

# ── Config ────────────────────────────────────────────────────────────────────
EMBED_URL  = os.getenv("EMBED_URL",  "http://localhost:8010/v1/embeddings")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = "qtkd_rag"
VECTOR_SIZE = 1024
BATCH_SIZE = 8           # chunks per embedding request (bge-large CPU is slow)
UPSERT_BATCH = 64        # points per Qdrant upsert call
EMBED_TIMEOUT = 300      # seconds per batch


# ── Embedding ─────────────────────────────────────────────────────────────────

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Call embedding service, return list of 1024-dim vectors."""
    resp = requests.post(
        EMBED_URL,
        json={"input": texts, "model": "model"},
        timeout=EMBED_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    data.sort(key=lambda x: x["index"])
    return [d["embedding"] for d in data]


# Richer contextual blurb: QTKĐ number + equipment name (Phase 2 Contextual Retrieval).
# Extracted from §1 "Phạm vi áp dụng" of each source document.
_QTKD_TITLES: dict[str, str] = {
    "QTKD_1.061": "Van an toàn",
    "QTKD_1.062": "Bàn tạo áp",
    "QTKD_1.063": "Bình phân ly",
    "QTKD_1.071": "Áp kế pittông H3000",
    "QTKD_1.159": "Áp kế pittông tiêu chuẩn",
    "QTKD_1.160": "Thiết bị đo áp suất số AKKĐ",
    "QTKD_1.190": "DPI 610",
}


_QTKD_NUMBER_RE = re.compile(r'QTKD_(\d+\.\d+)')


def _qtkd_prefix(file_stem: str) -> str:
    """Return 'QTKĐ X.XXX TênThiếtBị: ' from any file_stem containing QTKD_X.XXX."""
    m = _QTKD_NUMBER_RE.search(file_stem)
    if m:
        number = m.group(1)
        title = _QTKD_TITLES.get(f"QTKD_{number}", "")
        suffix = f" {title}" if title else ""
        return f"QTKĐ {number}{suffix}: "
    return ""


def embed_chunks_batched(chunks: list[Chunk]) -> list[list[float]]:
    """Embed chunks in batches; child chunks get QTKĐ-number context prefix (Phase 2).

    Only the embedding input changes — payload text stays original so BM25
    and the UI still use the clean source text.
    """
    all_vectors: list[list[float]] = []
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i: i + BATCH_SIZE]
        texts = [
            # Phase 2 prefix DISABLED (A/B test 2026-06-07): recall@5 identical (0.709) with/without;
            # prefix gives +1.8pp recall@10 (0.836 vs 0.818). To restore: re-enable line below + --force.
            # (_qtkd_prefix(c.file_stem) + c.text) if not c.is_parent else c.text
            c.text
            for c in batch
        ]
        try:
            vecs = embed_texts(texts)
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 500:
                # GPU OOM or transient service error — retry one chunk at a time
                print(f"\n  [warn] batch {i // BATCH_SIZE} HTTP 500, retrying 1-by-1 …")
                time.sleep(2)
                vecs = []
                for j, text in enumerate(texts):
                    try:
                        vecs.extend(embed_texts([text]))
                    except Exception as inner:
                        print(f"\n  [warn] chunk {i + j} failed solo ({inner}), using zero vector")
                        vecs.append([0.0] * VECTOR_SIZE)
            else:
                raise
        all_vectors.extend(vecs)
        print(f"  embedded {min(i + BATCH_SIZE, len(chunks))}/{len(chunks)}", end="\r")
    print()
    return all_vectors


# ── Qdrant helpers ────────────────────────────────────────────────────────────

def ensure_collection(client: QdrantClient) -> None:
    """Create collection if it does not exist."""
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"Created collection '{COLLECTION}' (cosine, {VECTOR_SIZE} dims)")
    else:
        info = client.get_collection(COLLECTION)
        count = info.points_count
        print(f"Collection '{COLLECTION}' exists ({count} points)")


def _file_hash(file_stem: str) -> str:
    return hashlib.sha256(file_stem.encode()).hexdigest()[:12]


def indexed_files(client: QdrantClient) -> set[str]:
    """Return set of file_stems already in the collection."""
    # Scroll all points and collect unique file_stems (fast for small corpora)
    try:
        results, _ = client.scroll(
            collection_name=COLLECTION,
            limit=10000,
            with_payload=["file_stem"],
            with_vectors=False,
        )
        return {r.payload.get("file_stem", "") for r in results}
    except Exception:
        return set()


def upsert(client: QdrantClient, points: list[PointStruct]) -> None:
    for i in range(0, len(points), UPSERT_BATCH):
        batch = points[i: i + UPSERT_BATCH]
        client.upsert(collection_name=COLLECTION, points=batch)


# ── Main indexing logic ───────────────────────────────────────────────────────

def index_directory(md_dir: Path, force: bool = False) -> dict:
    client = QdrantClient(url=QDRANT_URL)
    ensure_collection(client)

    already = indexed_files(client) if not force else set()

    # Parse all files
    print(f"\nParsing Markdown from {md_dir} …")
    all_chunks = parse_directory(md_dir)

    # Group by file
    by_file: dict[str, list[Chunk]] = {}
    for c in all_chunks:
        by_file.setdefault(c.file_stem, []).append(c)

    stats = {"files_indexed": 0, "files_skipped": 0, "chunks_added": 0}

    for file_stem, chunks in by_file.items():
        if file_stem in already and not force:
            print(f"  SKIP (already indexed): {file_stem}")
            stats["files_skipped"] += 1
            continue

        print(f"\nIndexing {file_stem} ({len(chunks)} chunks) …")
        t0 = time.time()

        vectors = embed_chunks_batched(chunks)

        points = []
        for chunk, vec in zip(chunks, vectors):
            points.append(PointStruct(
                id=int(chunk.chunk_id, 16),  # Qdrant needs uint64
                vector=vec,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "parent_id": chunk.parent_id,
                    "is_parent": chunk.is_parent,
                    "kind": chunk.kind,
                    "text": chunk.text,
                    "section_path": chunk.section_path,
                    "file_stem": chunk.file_stem,
                },
            ))

        upsert(client, points)
        elapsed = time.time() - t0
        print(f"  ✓ {len(points)} points in {elapsed:.1f}s")
        stats["files_indexed"] += 1
        stats["chunks_added"] += len(points)

    total = client.get_collection(COLLECTION).points_count
    stats["total_points"] = total
    print(f"\nDone. Collection '{COLLECTION}' now has {total} points.")
    return stats


# ── Smoke-test query ──────────────────────────────────────────────────────────

def query(text: str, top_k: int = 5, parents_only: bool = False) -> None:
    client = QdrantClient(url=QDRANT_URL)
    vec = embed_texts([text])[0]

    filt = None
    if parents_only:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        filt = Filter(must=[FieldCondition(
            key="is_parent", match=MatchValue(value=True)
        )])

    result = client.query_points(
        collection_name=COLLECTION,
        query=vec,
        limit=top_k,
        query_filter=filt,
        with_payload=True,
    )
    hits = result.points

    print(f"\nQuery: '{text}'")
    print(f"{'─'*60}")
    for i, h in enumerate(hits, 1):
        p = h.payload
        snippet = p["text"][:120].replace("\n", " ")
        print(f"{i}. [{p['kind']}] score={h.score:.3f}")
        print(f"   file: {p['file_stem']}")
        print(f"   path: {p['section_path']}")
        print(f"   text: {snippet}…")
        print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Index QTKĐ Markdown into Qdrant")
    parser.add_argument("--md-dir", default="build/spike_a", help="Directory with *.md files")
    parser.add_argument("--force", action="store_true", help="Re-index even if already present")
    parser.add_argument("--query", help="Run a smoke-test query after indexing")
    args = parser.parse_args()

    md_dir = Path(args.md_dir)
    if not md_dir.exists():
        print(f"ERROR: {md_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    stats = index_directory(md_dir, force=args.force)
    print(json.dumps(stats, ensure_ascii=False, indent=2))

    if args.query:
        query(args.query)


if __name__ == "__main__":
    main()
