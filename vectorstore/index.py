"""Embed QTKĐ chunks and upsert into Qdrant collection `qtkd_rag`.

Services used (all local Docker, already running):
  - Embedding: POST http://localhost:8010/v1/embeddings  → 1024-dim vectors
  - Qdrant:    http://localhost:6333                     → collection qtkd_rag

Run:
  python -m vectorstore.index [--md-dir build/spike_a] [--force]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from embedding import batch_embed, embedder
from ingestion.chunker import Chunk, parse_directory

# ── Config ────────────────────────────────────────────────────────────────────
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = "qtkd_rag"
VECTOR_SIZE = 1024
UPSERT_BATCH = 64        # points per Qdrant upsert call


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


def delete_file_chunks(client: QdrantClient, file_stem: str) -> None:
    """B11: xóa mọi điểm đã lưu của ``file_stem`` trước khi nhúng lại.

    ``chunk_id`` ổn định nên upsert ghi đè được chunk trùng, nhưng chunk không
    còn tồn tại ở bản mới (hoặc chunk hỏng của lần trích lỗi trước) vẫn nằm
    lại. Xóa theo payload ``file_stem`` để kết quả đúng bằng tập chunk mới.
    """
    client.delete(
        collection_name=COLLECTION,
        points_selector=FilterSelector(
            filter=Filter(must=[FieldCondition(key="file_stem", match=MatchValue(value=file_stem))])
        ),
    )


def index_chunks(client: QdrantClient, chunks: list[Chunk]) -> int:
    """Embed + upsert one list of chunks (single file or full corpus). Returns point count."""
    vectors = batch_embed.embed_chunks_batched(chunks)
    document_ids: dict[str, str] = {}
    try:
        from db import SessionLocal
        from db.models import Document
        db = SessionLocal()
        document_ids = {
            row.file_stem: row.id
            for row in db.query(Document).filter(Document.file_stem.in_({c.file_stem for c in chunks})).all()
        }
        db.close()
    except Exception:
        # Indexing legacy corpora remains possible before the document migration.
        document_ids = {}
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
                "document_id": document_ids.get(chunk.file_stem),
            },
        ))
    # B11: nhúng lại một file phải THAY THẾ, không cộng dồn: xóa điểm cũ ngay
    # trước khi ghi tập mới (sau khi embed xong, tránh mất dữ liệu nếu embed lỗi).
    for stem in {c.file_stem for c in chunks}:
        delete_file_chunks(client, stem)
    upsert(client, points)
    return len(points)


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

        n_points = index_chunks(client, chunks)
        elapsed = time.time() - t0
        print(f"  ✓ {n_points} points in {elapsed:.1f}s")
        stats["files_indexed"] += 1
        stats["chunks_added"] += n_points

    total = client.get_collection(COLLECTION).points_count
    stats["total_points"] = total
    print(f"\nDone. Collection '{COLLECTION}' now has {total} points.")
    return stats


# ── Smoke-test query ──────────────────────────────────────────────────────────

def query(text: str, top_k: int = 5, parents_only: bool = False) -> None:
    client = QdrantClient(url=QDRANT_URL)
    vec = embedder.embed_texts([text])[0]

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
