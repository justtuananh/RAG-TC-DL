"""Client stream câu trả lời từ Ollama (native /api/chat).

Một chỗ duy nhất map URL OpenAI-compat sang native và đọc cấu hình LLM từ
``config/settings.yaml``. Model: tham số ``model``, không có thì ``models.llm_chat``.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator

import requests

from core.settings_loader import get_settings

MAX_CHAT_ATTEMPTS = 2
CHAT_RETRY_DELAY_S = 3.0


def _open_chat_stream(url: str, body: dict, timeout_s: float, *, stream: bool = True):
    """POST tới Ollama; lỗi 5xx (thường là llama-server bị kill/crash khi nạp lại model) thử lại có giới hạn.

    Chỉ thử lại TRƯỚC khi có token đầu tiên (lỗi nằm ở ``raise_for_status``), nên
    không bao giờ phát lặp nội dung. Lỗi 4xx là lỗi yêu cầu, không thử lại.
    """
    for attempt in range(1, MAX_CHAT_ATTEMPTS + 1):
        resp = requests.post(url, json=body, stream=stream, timeout=timeout_s)
        try:
            resp.raise_for_status()
            return resp
        except requests.HTTPError as error:
            status = getattr(error.response, "status_code", None)
            close = getattr(resp, "close", None)
            if close is not None:
                close()
            if status is None or status < 500 or attempt == MAX_CHAT_ATTEMPTS:
                raise
            time.sleep(CHAT_RETRY_DELAY_S)
    raise AssertionError("unreachable")  # pragma: no cover


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
    body = {
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
    }
    resp = _open_chat_stream(native_chat_url(settings.llm_url("chat")), body, chat.timeout_s)
    try:
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
    finally:
        # Generator bị close (vd. lọc CJK ngắt sớm) -> đóng kết nối để Ollama ngừng sinh.
        close = getattr(resp, "close", None)
        if close is not None:
            close()


def chat_once(
    messages: list[dict],
    *,
    num_predict: int,
    timeout_s: float,
    json_mode: bool = False,
    model: str | None = None,
) -> str:
    """Một lượt gọi Ollama native /api/chat KHÔNG stream, nhiệt độ 0: trích số liệu, viết lại
    câu hỏi. ``json_mode`` ép đầu ra là JSON hợp lệ. Lỗi mạng/HTTP -> ngoại lệ cho nơi gọi xử lý."""
    settings = get_settings()
    chat = settings.llm.chat
    body: dict = {
        "model": model or settings.llm_model("chat"),
        "messages": messages,
        "stream": False,
        "keep_alive": chat.keep_alive,
        "options": {"num_ctx": chat.num_ctx, "num_predict": num_predict, "temperature": 0},
    }
    if json_mode:
        body["format"] = "json"
    resp = _open_chat_stream(native_chat_url(settings.llm_url("chat")), body, timeout_s, stream=False)
    return ((resp.json().get("message") or {}).get("content") or "").strip()
