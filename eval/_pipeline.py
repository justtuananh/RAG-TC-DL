"""Phễu retrieve DUY NHẤT mà mọi eval dùng chung — chống drift eval↔production.

`app.py:bot_fn` và `api_server.py` giờ gọi `retrieve(query)` không truyền top_k,
nên phễu lấy thẳng từ `settings.retrieval` (top_k=50 như API). Cả `run_eval.py`
và `answer_eval.py` đều đi qua đây để đo đúng cái người dùng nhận.
"""

from __future__ import annotations

from retrieval.retriever import retrieve


def production_retrieve(query: str, top_n: int | None = None) -> list[dict]:
    """Đúng đường retrieve của production (route→expand→embed+BM25→RRF→rerank→parent)."""
    return retrieve(query, top_n=top_n)
