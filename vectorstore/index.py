"""Index QTKĐ Markdown chunks into Qdrant.

Services used (all local Docker, already running); URL và tên collection lấy từ
config/settings.yaml (services.embedding_url, services.qdrant_url, vectorstore.collection).

Run:
  python -m vectorstore.index [--force] [--query "..."]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from core.logging_setup import configure_logging
from core.settings_loader import get_settings
from embedding import embedder
from ingestion.chunker import Chunk, parse_directory
from vectorstore import qdrant, upsert

logger = logging.getLogger(__name__)


# ── Main indexing logic ───────────────────────────────────────────────────────


def index_directory(md_dir: Path | None = None, force: bool = False) -> dict:
    md_dir = md_dir or get_settings().paths.markdown_dir
    client = qdrant.get_client()
    qdrant.ensure_collection(client)

    already = qdrant.indexed_files(client) if not force else set()

    # Parse all files
    logger.info("Parsing Markdown from %s …", md_dir)
    all_chunks = parse_directory(md_dir)

    # Group by file
    by_file: dict[str, list[Chunk]] = {}
    for c in all_chunks:
        by_file.setdefault(c.file_stem, []).append(c)

    stats = {"files_indexed": 0, "files_skipped": 0, "chunks_added": 0}

    for file_stem, chunks in by_file.items():
        if file_stem in already and not force:
            logger.info("SKIP (already indexed): %s", file_stem)
            stats["files_skipped"] += 1
            continue

        logger.info("Indexing %s (%d chunks) …", file_stem, len(chunks))
        t0 = time.time()

        n_points = upsert.index_chunks(client, chunks)
        elapsed = time.time() - t0
        logger.info("  %d points in %.1fs", n_points, elapsed)
        stats["files_indexed"] += 1
        stats["chunks_added"] += n_points

    collection = qdrant.collection_name()
    total = client.get_collection(collection).points_count
    stats["total_points"] = total
    logger.info("Done. Collection '%s' now has %d points.", collection, total)
    return stats


# ── Smoke-test query ──────────────────────────────────────────────────────────


def query(text: str, top_k: int = 5, parents_only: bool = False) -> None:
    client = qdrant.get_client()
    vec = embedder.embed_texts([text])[0]

    filt = None
    if parents_only:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        filt = Filter(must=[FieldCondition(key="is_parent", match=MatchValue(value=True))])

    result = client.query_points(
        collection_name=qdrant.collection_name(),
        query=vec,
        limit=top_k,
        query_filter=filt,
        with_payload=True,
    )
    hits = result.points

    print(f"\nQuery: '{text}'")
    print(f"{'─' * 60}")
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
    configure_logging()
    parser = argparse.ArgumentParser(description="Index QTKĐ Markdown into Qdrant")
    parser.add_argument("--md-dir", default=None, help="Directory with *.md files")
    parser.add_argument("--force", action="store_true", help="Re-index even if already present")
    parser.add_argument("--query", help="Run a smoke-test query after indexing")
    args = parser.parse_args()

    md_dir = Path(args.md_dir) if args.md_dir else get_settings().paths.markdown_dir
    if not md_dir.exists():
        print(f"ERROR: {md_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    stats = index_directory(md_dir, force=args.force)
    logger.info("Index xong: %s", json.dumps(stats, ensure_ascii=False))

    if args.query:
        query(args.query)


if __name__ == "__main__":
    main()
