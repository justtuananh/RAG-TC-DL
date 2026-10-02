"""Ghi chunk đã nhúng vào Qdrant (point id = chunk_id hex → uint64, nên index lại là idempotent)."""

from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from core.schema import Chunk
from core.settings_loader import get_settings
from embedding import batch_embed
from vectorstore import qdrant


def upsert_points(client: QdrantClient, points: list[PointStruct]) -> None:
    upsert_batch = get_settings().vectorstore.upsert_batch
    for i in range(0, len(points), upsert_batch):
        batch = points[i: i + upsert_batch]
        client.upsert(collection_name=qdrant.collection_name(), points=batch)


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
            for row in db.query(Document)
            .filter(Document.file_stem.in_({c.file_stem for c in chunks}))
            .all()
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
        qdrant.delete_file_chunks(client, stem)
    upsert_points(client, points)
    return len(points)
