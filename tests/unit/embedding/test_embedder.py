"""Client service embedding: một chỗ duy nhất gọi /v1/embeddings."""

import json

import responses

from embedding import embedder


@responses.activate
def test_embed_texts_orders_by_index_and_posts_to_configured_url(settings_override):
    settings_override({"services.embedding_url": "http://emb.test/v1/embeddings"})
    responses.post(
        "http://emb.test/v1/embeddings",
        json={"data": [{"index": 1, "embedding": [2.0]}, {"index": 0, "embedding": [1.0]}]},
    )
    assert embedder.embed_texts(["a", "b"]) == [[1.0], [2.0]]
    assert json.loads(responses.calls[0].request.body) == {"input": ["a", "b"], "model": "model"}


@responses.activate
def test_embed_query_returns_single_vector(settings_override):
    settings_override({"services.embedding_url": "http://emb.test/v1/embeddings"})
    responses.post(
        "http://emb.test/v1/embeddings", json={"data": [{"index": 0, "embedding": [0.5, 0.5]}]}
    )
    assert embedder.embed_query("câu hỏi") == [0.5, 0.5]
