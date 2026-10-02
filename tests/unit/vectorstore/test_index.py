"""Indexing — vectorstore.index (mock embedding service + Qdrant client).

Kiểm: sort theo index, batch theo BATCH_SIZE, prefix QTKĐ, indexed_files, upsert batch.
"""

import json

import responses

from core.schema import Chunk
from core.settings_loader import get_settings
from embedding.batch_embed import _qtkd_prefix, embed_chunks_batched
from vectorstore.index import (
    UPSERT_BATCH,
    VECTOR_SIZE,
    index_chunks,
    indexed_files,
    upsert,
)


@responses.activate
def test_embed_texts_sorts_by_index(settings_override):
    settings_override({"services.embedding_url": "http://emb.test/v1/embeddings"})

    def cb(req):
        texts = json.loads(req.body)["input"]
        # Trả về ĐẢO thứ tự để chứng minh embed_texts tự sort theo "index".
        data = [{"index": i, "embedding": [float(i)] * 4} for i in range(len(texts))][::-1]
        return (200, {}, json.dumps({"data": data}))

    responses.add_callback(
        responses.POST,
        "http://emb.test/v1/embeddings",
        callback=cb,
        content_type="application/json",
    )
    from embedding.embedder import embed_texts

    assert embed_texts(["a", "b", "c"]) == [[0.0] * 4, [1.0] * 4, [2.0] * 4]


def test_qtkd_prefix():
    assert _qtkd_prefix("QTKD_1.061_2021_ND_V2") == "QTKĐ 1.061 Van an toàn: "
    assert _qtkd_prefix("khong_co_ma") == ""


def test_embed_chunks_batched_respects_batch_size(monkeypatch):
    seen_sizes = []

    def fake_embed(texts, *, timeout=None):
        seen_sizes.append(len(texts))
        return [[0.0] * VECTOR_SIZE for _ in texts]

    monkeypatch.setattr("embedding.embedder.embed_texts", fake_embed)
    chunks = [
        Chunk(
            chunk_id=f"{i:016x}",
            parent_id=None,
            is_parent=False,
            kind="paragraph",
            text=f"t{i}",
            section_path="s",
            file_stem="QTKD_1.061",
        )
        for i in range(20)
    ]
    vecs = embed_chunks_batched(chunks)
    assert len(vecs) == 20
    batch_size = get_settings().embedding.batch_size
    assert seen_sizes == [batch_size, batch_size, 20 - 2 * batch_size]  # 8, 8, 4


def test_indexed_files_returns_unique_stems():
    class _Pt:
        def __init__(self, fs):
            self.payload = {"file_stem": fs}

    class _Client:
        def scroll(self, **kwargs):
            return ([_Pt("A"), _Pt("B"), _Pt("A")], None)

    assert indexed_files(_Client()) == {"A", "B"}


def test_indexed_files_swallows_errors():
    class _Bad:
        def scroll(self, **kwargs):
            raise RuntimeError("qdrant down")

    assert indexed_files(_Bad()) == set()


def test_upsert_batches_by_upsert_batch():
    class _Client:
        def __init__(self):
            self.calls = 0

        def upsert(self, **kwargs):
            self.calls += 1

    c = _Client()
    upsert(c, list(range(130)))  # 64 + 64 + 2
    assert c.calls == 3
    assert UPSERT_BATCH == 64


class _FakeQdrant:
    """Ghi nhận delete/upsert; delete xóa điểm theo payload ``file_stem``."""

    def __init__(self):
        self.points: dict[int, dict] = {}
        self.calls: list[tuple] = []

    def delete(self, collection_name, points_selector):
        stem = points_selector.filter.must[0].match.value
        self.calls.append(("delete", stem))
        self.points = {k: v for k, v in self.points.items() if v["file_stem"] != stem}

    def upsert(self, collection_name, points):
        self.calls.append(("upsert", len(points)))
        for p in points:
            self.points[p.id] = p.payload


def _chunk(i: int, text: str, stem: str = "QTKD_X") -> Chunk:
    return Chunk(
        chunk_id=f"{i:016x}",
        parent_id=None,
        is_parent=False,
        kind="paragraph",
        text=text,
        section_path="s",
        file_stem=stem,
    )


def test_index_chunks_replaces_existing_points_for_file(monkeypatch):
    """B11: nhúng lại cùng file chỉ còn tập chunk mới, không cộng dồn chunk cũ."""
    monkeypatch.setattr(
        "embedding.batch_embed.embed_chunks_batched",
        lambda chunks: [[0.0] * VECTOR_SIZE for _ in chunks],
    )
    client = _FakeQdrant()

    index_chunks(client, [_chunk(i, f"cũ {i}") for i in range(3)])
    index_chunks(client, [_chunk(i + 100, f"mới {i}") for i in range(2)])

    assert len(client.points) == 2
    assert {p["text"] for p in client.points.values()} == {"mới 0", "mới 1"}
    assert client.calls == [
        ("delete", "QTKD_X"),
        ("upsert", 3),
        ("delete", "QTKD_X"),
        ("upsert", 2),
    ]


def test_index_chunks_deletes_each_file_stem_once(monkeypatch):
    """Tập chunk nhiều file: xóa đúng từng file_stem trước khi ghi."""
    monkeypatch.setattr(
        "embedding.batch_embed.embed_chunks_batched",
        lambda chunks: [[0.0] * VECTOR_SIZE for _ in chunks],
    )
    client = _FakeQdrant()

    index_chunks(client, [_chunk(1, "a", "F1"), _chunk(2, "b", "F2"), _chunk(3, "c", "F1")])

    assert sorted(c for c in client.calls if c[0] == "delete") == [
        ("delete", "F1"),
        ("delete", "F2"),
    ]
    assert client.calls[-1] == ("upsert", 3)
