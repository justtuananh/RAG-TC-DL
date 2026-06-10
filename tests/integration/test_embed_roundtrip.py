"""Tầng integration: embedding service trả đúng 1024 chiều; reranker chấm điểm thật."""

import requests


def test_embed_query_dim_1024(require_services):
    require_services("embedding")
    from retrieval.retriever import embed_query

    vec = embed_query("áp suất van an toàn")
    assert isinstance(vec, list)
    assert len(vec) == 1024


def test_rerank_endpoint_scores(require_services):
    require_services("reranker")
    from retrieval.retriever import RERANK_URL

    r = requests.post(
        RERANK_URL,
        json={
            "query": "sai số van an toàn",
            "documents": ["áp suất chỉnh đặt", "màu sơn"],
            "top_n": 2,
        },
        timeout=30,
    )
    r.raise_for_status()
    results = r.json()["results"]
    assert len(results) == 2
    assert all("relevance_score" in x for x in results)
