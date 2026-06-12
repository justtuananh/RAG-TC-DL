"""Phễu retrieve DUY NHẤT mà mọi eval dùng chung — chống drift eval↔production.

`app.py:bot_fn` gọi `retrieve(query, top_k=20, top_n=5)`. Trước đây `run_eval.run_hybrid`
viết lại phễu với `top_k=50, top_n=10` → eval đo một đường khác production. Cả
`run_eval.py` và `answer_eval.py` đều đi qua đây để đo đúng cái người dùng nhận.

Đổi `TOP_K_PROD` ở MỘT chỗ này (đồng bộ với app.py) nếu cần nới phễu.
"""
from __future__ import annotations

from retrieval.retriever import retrieve

# Phải khớp app.py:bot_fn — sửa thì sửa cả hai nơi.
TOP_K_PROD = 20


def production_retrieve(query: str, top_n: int = 5) -> list[dict]:
    """Đúng đường retrieve của production (route→expand→embed+BM25→RRF→rerank→parent)."""
    return retrieve(query, top_k=TOP_K_PROD, top_n=top_n)
