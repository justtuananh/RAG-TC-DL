"""Client của service embedding (OpenAI-compat /v1/embeddings, bge-m3 1024 chiều).

Trước đây có hai bản sao (retrieval/retriever.embed_query + index/embed_store.embed_texts)
khác nhau mỗi timeout; nay là một client, timeout tách theo việc dùng.
"""

from __future__ import annotations

import requests

from core.settings_loader import get_settings

# Service chỉ phục vụ một model; trường "model" của giao thức OpenAI chỉ để request hợp lệ.
_PROTOCOL_MODEL_FIELD = "model"


def embed_texts(texts: list[str], *, timeout: float | None = None) -> list[list[float]]:
    """Nhúng một lô văn bản, trả vector theo đúng thứ tự đầu vào."""
    settings = get_settings()
    resp = requests.post(
        settings.services.embedding_url,
        json={"input": texts, "model": _PROTOCOL_MODEL_FIELD},
        timeout=timeout or settings.embedding.batch_timeout_s,
    )
    resp.raise_for_status()
    data = sorted(resp.json()["data"], key=lambda item: item["index"])
    return [item["embedding"] for item in data]


def embed_query(text: str) -> list[float]:
    """Nhúng một câu hỏi (timeout ngắn hơn lô index)."""
    return embed_texts([text], timeout=get_settings().embedding.query_timeout_s)[0]
