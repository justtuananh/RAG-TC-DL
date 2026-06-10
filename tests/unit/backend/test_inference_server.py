"""Inference server FastAPI — docker/inference/server.py.

Inject một `sentence_transformers` GIẢ vào sys.modules TRƯỚC khi import server, nên
test chạy KHÔNG cần torch/GPU/tải model. Dùng TestClient (ASGI in-process, no socket).
docker/inference/ không phải package → chèn vào sys.path rồi import server.
"""

import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402


class _FakeArray(list):
    def tolist(self):
        return list(self)


@pytest.fixture
def server_mod(monkeypatch):
    fake = types.ModuleType("sentence_transformers")

    class FakeSentenceTransformer:
        def __init__(self, *a, **k):
            pass

        def encode(self, texts, **k):
            return [_FakeArray([0.1, 0.2, 0.3, 0.4]) for _ in texts]

        def get_sentence_embedding_dimension(self):
            return 4

    class FakeCrossEncoder:
        def __init__(self, *a, **k):
            pass

        def predict(self, pairs, **k):
            return _FakeArray([0.1 * (i + 1) for i in range(len(pairs))])

    fake.SentenceTransformer = FakeSentenceTransformer
    fake.CrossEncoder = FakeCrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)

    server_dir = Path(__file__).resolve().parents[3] / "docker" / "inference"
    monkeypatch.syspath_prepend(str(server_dir))
    sys.modules.pop("server", None)
    import server  # noqa: E402

    yield server
    sys.modules.pop("server", None)


def test_health_reports_mode(server_mod):
    client = TestClient(server_mod.app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mode"] == server_mod.MODE


def test_embeddings_openai_shape(server_mod):
    server_mod._embedder = server_mod.SentenceTransformer()
    client = TestClient(server_mod.app)
    r = client.post("/v1/embeddings", json={"input": ["a", "b"]})
    assert r.status_code == 200
    data = r.json()["data"]
    assert [d["index"] for d in data] == [0, 1]
    assert len(data[0]["embedding"]) == 4


def test_embeddings_accepts_bare_string(server_mod):
    server_mod._embedder = server_mod.SentenceTransformer()
    client = TestClient(server_mod.app)
    r = client.post("/v1/embeddings", json={"input": "solo"})
    assert len(r.json()["data"]) == 1


def test_embeddings_503_when_not_loaded(server_mod):
    server_mod._embedder = None
    client = TestClient(server_mod.app)
    r = client.post("/v1/embeddings", json={"input": ["a"]})
    assert r.status_code == 503


def test_rerank_sorts_and_applies_top_n(server_mod):
    server_mod._reranker = server_mod.CrossEncoder()
    client = TestClient(server_mod.app)
    r = client.post("/v1/rerank", json={"query": "q", "documents": ["d0", "d1", "d2"], "top_n": 2})
    results = r.json()["results"]
    assert len(results) == 2
    scores = [x["relevance_score"] for x in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0]["index"] == 2  # điểm cao nhất là doc cuối


def test_rerank_empty_documents(server_mod):
    server_mod._reranker = server_mod.CrossEncoder()
    client = TestClient(server_mod.app)
    r = client.post("/v1/rerank", json={"query": "q", "documents": []})
    assert r.json()["results"] == []
