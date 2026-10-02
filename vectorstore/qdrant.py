"""Truy cập Qdrant: một client cho cả index lẫn truy hồi, collection lấy từ settings."""

from __future__ import annotations

import hashlib

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    VectorParams,
)

from core.settings_loader import get_settings

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=get_settings().services.qdrant_url)
    return _client


def collection_name() -> str:
    return get_settings().vectorstore.collection


def collection_vector_size(name: str) -> int | None:
    """Số chiều vector của collection; None nếu collection chưa tồn tại."""
    client = get_client()
    if name not in {c.name for c in client.get_collections().collections}:
        return None
    return client.get_collection(name).config.params.vectors.size


def ensure_collection(client: QdrantClient) -> None:
    """Create collection if it does not exist."""
    collection = collection_name()
    vector_size = get_settings().models.embedding.vector_size
    existing = [c.name for c in client.get_collections().collections]
    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        print(f"Created collection '{collection}' (cosine, {vector_size} dims)")
    else:
        info = client.get_collection(collection)
        count = info.points_count
        print(f"Collection '{collection}' exists ({count} points)")


def _file_hash(file_stem: str) -> str:
    return hashlib.sha256(file_stem.encode()).hexdigest()[:12]


def indexed_files(client: QdrantClient) -> set[str]:
    """Return set of file_stems already in the collection."""
    # Scroll all points and collect unique file_stems (fast for small corpora)
    try:
        results, _ = client.scroll(
            collection_name=collection_name(),
            limit=10000,
            with_payload=["file_stem"],
            with_vectors=False,
        )
        return {r.payload.get("file_stem", "") for r in results}
    except Exception:
        return set()


def delete_file_chunks(client: QdrantClient, file_stem: str) -> None:
    """B11: xóa mọi điểm đã lưu của ``file_stem`` trước khi nhúng lại.

    ``chunk_id`` ổn định nên upsert ghi đè được chunk trùng, nhưng chunk không
    còn tồn tại ở bản mới (hoặc chunk hỏng của lần trích lỗi trước) vẫn nằm
    lại. Xóa theo payload ``file_stem`` để kết quả đúng bằng tập chunk mới.
    """
    client.delete(
        collection_name=collection_name(),
        points_selector=FilterSelector(
            filter=Filter(must=[FieldCondition(key="file_stem", match=MatchValue(value=file_stem))])
        ),
    )


def dense_search(
    vec: list[float],
    top_k: int | None = None,
    file_stem: str | None = None,
) -> list[dict]:
    """Search child chunks, optionally filtered to a specific file_stem."""
    top_k = top_k or get_settings().retrieval.top_k
    client = get_client()
    conditions = [FieldCondition(key="is_parent", match=MatchValue(value=False))]
    if file_stem:
        conditions.append(FieldCondition(key="file_stem", match=MatchValue(value=file_stem)))
    result = client.query_points(
        collection_name=collection_name(),
        query=vec,
        query_filter=Filter(must=conditions),
        limit=top_k,
        with_payload=True,
    )
    return [{"id": h.id, "score": h.score, "payload": h.payload} for h in result.points]


def fetch_parent(parent_id_hex: str) -> dict | None:
    """Fetch full parent section payload by its chunk_id (hex → uint64 point ID)."""
    if not parent_id_hex:
        return None
    client = get_client()
    try:
        point_id = int(parent_id_hex, 16)
        results = client.retrieve(
            collection_name=collection_name(),
            ids=[point_id],
            with_payload=True,
        )
        if results:
            return results[0].payload
    except Exception:
        pass
    return None


def scroll_child_payloads() -> list[dict]:
    """Scroll every child chunk payload out of the collection (for the BM25 index)."""
    client = get_client()
    child_filter = Filter(must=[FieldCondition(key="is_parent", match=MatchValue(value=False))])
    payloads: list[dict] = []
    offset = None
    while True:
        results, next_offset = client.scroll(
            collection_name=collection_name(),
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
