"""QTKDReranking — kotaemon reranker adapter for the project's bge-reranker-v2-m3.

The project reranker at :8011/v1/rerank uses Cohere-style format:
    POST {"query": str, "documents": list[str], "top_n": int}
    → {"results": [{"index": int, "relevance_score": float}]}

kotaemon's built-in TeiFastReranking uses TEI format ({"query","texts"} → list of
{index, score}) which is incompatible. This adapter matches the Cohere/Jina format
that retriever.py already uses successfully.
"""
from __future__ import annotations

import requests

from kotaemon.base import Document
from kotaemon.rerankings.base import BaseReranking


class QTKDReranking(BaseReranking):
    endpoint_url: str = "http://localhost:8011/v1/rerank"
    timeout: int = 60

    def run(self, documents: list[Document], query: str) -> list[Document]:
        if not documents:
            return []

        texts = [doc.text for doc in documents]
        resp = requests.post(
            self.endpoint_url,
            json={"query": query, "documents": texts, "top_n": len(texts)},
            timeout=self.timeout,
        )
        resp.raise_for_status()

        results = resp.json()["results"]
        results.sort(key=lambda r: r["relevance_score"], reverse=True)

        reranked: list[Document] = []
        for r in results:
            doc = documents[r["index"]]
            doc.metadata["reranking_score"] = r["relevance_score"]
            reranked.append(doc)
        return reranked
