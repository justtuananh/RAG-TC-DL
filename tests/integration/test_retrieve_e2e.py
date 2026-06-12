"""Tầng integration: pipeline retrieve thật (dense+BM25+RRF+rerank+parent) trên Qdrant."""


def test_retrieve_returns_parent_and_score(require_services):
    require_services("qdrant", "embedding", "reranker")
    from retrieval.retriever import retrieve

    results = retrieve(
        "Sai số cho phép của áp suất chỉnh đặt van an toàn là bao nhiêu?",
        top_k=20,
        top_n=5,
    )
    assert results, "retrieve trả về rỗng — Qdrant đã index chưa? (make index)"
    assert all("parent_payload" in h and "rerank_score" in h for h in results)
    assert any(h["payload"]["file_stem"] == "QTKD_1.061_2021_ND_V2" for h in results)
