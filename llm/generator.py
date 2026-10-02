"""Client stream câu trả lời từ Ollama (native /api/chat).

Một chỗ duy nhất map URL OpenAI-compat sang native và đọc cấu hình LLM từ
``config/settings.yaml``. Model: tham số ``model``, không có thì ``models.llm_chat``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import requests

from core.settings_loader import get_settings


def native_chat_url(url: str) -> str:
    """Map URL OpenAI-compat (.../v1/chat/completions) → Ollama native /api/chat.

    Giữ nguyên host từ env cũ (.env / docker-compose đặt OLLAMA_URL dạng /v1);
    URL đã là /api/chat thì giữ nguyên.
    """
    return url.replace("/v1/chat/completions", "/api/chat")


def stream_ollama(messages: list[dict], *, model: str | None = None) -> Iterator[str]:
    """Stream từ Ollama NATIVE /api/chat (JSON lines), yield từng content delta.

    VÌ SAO không dùng /v1/chat/completions: endpoint OpenAI-compat BỎ QUA trường
    "options" → num_ctx/num_predict chưa bao giờ tới server; model chạy ctx mặc định
    4096 (xác nhận qua /api/ps trong lúc eval đang gửi 8192). Prompt ~4,3k token bị
    Ollama CẮT TỪ ĐẦU - mất system prompt + nguồn [1][2] → citation hỏng, fact đầu
    ngữ cảnh biến mất, 500 cận biên. /api/chat tôn trọng options per-request.
    Model: tham số ``model``, không có thì ``models.llm_chat``.
    """
    settings = get_settings()
    chat = settings.llm.chat
    resp = requests.post(
        native_chat_url(settings.llm_url("chat")),
        json={
            "model": model or settings.llm_model("chat"),
            "messages": messages,
            "stream": True,
            # Giữ model trong RAM giữa các request - mặc định 5m hay bị evict giữa
            # phiên/lô dài; mỗi lần reload 7b dưới áp lực RAM là một cửa sổ dễ bị
            # OOM-kill → Ollama 500 (đo: 42 lần 500/4h, log 'signal: killed').
            "keep_alive": chat.keep_alive,
            "options": {
                "num_ctx": chat.num_ctx,
                "num_predict": chat.max_new_tokens,
                "temperature": chat.temperature,
            },
        },
        stream=True,
        timeout=chat.timeout_s,
    )
    resp.raise_for_status()
    for line in resp.iter_lines():
        if not line:
            continue
        try:
            chunk = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError:
            continue
        delta = (chunk.get("message") or {}).get("content", "")
        if delta:
            yield delta
        if chunk.get("done"):
            break
