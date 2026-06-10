"""Indexing — index.embed_store (mock embedding service + Qdrant client).

Kiểm: sort theo index, batch theo BATCH_SIZE, prefix QTKĐ, indexed_files, upsert batch.
"""

import json

import responses

import index.embed_store as ES
from index.chunker import Chunk
from index.embed_store import (
    BATCH_SIZE,
    EMBED_URL,
    UPSERT_BATCH,
    VECTOR_SIZE,
    _qtkd_prefix,
    embed_chunks_batched,
    embed_texts,
    indexed_files,
    upsert,
)


@responses.activate
def test_embed_texts_sorts_by_index():
    def cb(req):
        texts = json.loads(req.body)["input"]
        # Trả về ĐẢO thứ tự để chứng minh embed_texts tự sort theo "index".
        data = [{"index": i, "embedding": [float(i)] * 4} for i in range(len(texts))][::-1]
        return (200, {}, json.dumps({"data": data}))

    responses.add_callback(responses.POST, EMBED_URL, callback=cb, content_type="application/json")
    assert embed_texts(["a", "b", "c"]) == [[0.0] * 4, [1.0] * 4, [2.0] * 4]


def test_qtkd_prefix():
    assert _qtkd_prefix("QTKD_1.061_2021_ND_V2") == "QTKĐ 1.061 Van an toàn: "
    assert _qtkd_prefix("khong_co_ma") == ""


def test_embed_chunks_batched_respects_batch_size(monkeypatch):
    seen_sizes = []

    def fake_embed(texts):
        seen_sizes.append(len(texts))
        return [[0.0] * VECTOR_SIZE for _ in texts]

    monkeypatch.setattr(ES, "embed_texts", fake_embed)
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
    assert seen_sizes == [BATCH_SIZE, BATCH_SIZE, 20 - 2 * BATCH_SIZE]  # 8, 8, 4


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
