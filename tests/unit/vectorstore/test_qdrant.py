"""Lớp truy cập Qdrant: client duy nhất, collection + URL lấy từ settings."""

from types import SimpleNamespace

from vectorstore import qdrant


class _FakeClient:
    def __init__(self):
        self.calls = []

    def query_points(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(points=[SimpleNamespace(id=1, score=0.9, payload={"text": "t"})])


def test_get_client_is_singleton_with_configured_url(monkeypatch, settings_override):
    settings_override({"services.qdrant_url": "http://q.test:6333"})
    created = []
    monkeypatch.setattr(qdrant, "QdrantClient", lambda url: created.append(url) or object())
    monkeypatch.setattr(qdrant, "_client", None)
    assert qdrant.get_client() is qdrant.get_client()
    assert created == ["http://q.test:6333"]


def test_dense_search_filters_children_and_file(monkeypatch, settings_override):
    settings_override({"vectorstore.collection": "c_test", "retrieval.top_k": 7})
    fake = _FakeClient()
    monkeypatch.setattr(qdrant, "get_client", lambda: fake)
    hits = qdrant.dense_search([0.0], file_stem="QTKD_1.159")
    call = fake.calls[0]
    assert call["collection_name"] == "c_test"
    assert call["limit"] == 7
    assert [c.key for c in call["query_filter"].must] == ["is_parent", "file_stem"]
    assert hits == [{"id": 1, "score": 0.9, "payload": {"text": "t"}}]


def test_collection_vector_size_none_when_missing(monkeypatch):
    fake = SimpleNamespace(get_collections=lambda: SimpleNamespace(collections=[]))
    monkeypatch.setattr(qdrant, "get_client", lambda: fake)
    assert qdrant.collection_vector_size("qtkd_rag") is None
