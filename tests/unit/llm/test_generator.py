"""Stream từ Ollama native /api/chat - llm.generator.stream_ollama.

JSON lines {"message":{"content":...},"done":bool}; chỉ yield content delta, dừng
ở done. Mock requests.post (không chạm mạng) + pin payload: "options" PHẢI mang
num_ctx/num_predict/temperature - /v1 OpenAI-compat từng nuốt mất options khiến
model chạy ctx 4096 và cắt prompt từ đầu (mất system prompt + nguồn [1][2]).
"""

from core.settings_loader import get_settings
from llm import generator


class _FakeResp:
    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        pass

    def iter_lines(self):
        yield from self._lines


def test_yields_only_content_deltas(monkeypatch):
    lines = [
        b'{"message":{"content":"Xin"},"done":false}',
        b"",  # rỗng → bỏ
        b'{"message":{"content":" chao"},"done":false}',
        b'{"message":{},"done":false}',  # không content → bỏ
        b'{"message":{"content":""},"done":true}',  # done → dừng
        b'{"message":{"content":"KHONG DUOC THAY"},"done":false}',
    ]
    monkeypatch.setattr(generator.requests, "post", lambda *a, **k: _FakeResp(lines))
    out = list(generator.stream_ollama([{"role": "user", "content": "hi"}]))
    assert out == ["Xin", " chao"]


def test_malformed_json_is_skipped(monkeypatch):
    lines = [
        b"{khong-phai-json}",
        b'{"message":{"content":"OK"},"done":false}',
    ]
    monkeypatch.setattr(generator.requests, "post", lambda *a, **k: _FakeResp(lines))
    assert list(generator.stream_ollama([])) == ["OK"]


def test_empty_stream(monkeypatch):
    monkeypatch.setattr(generator.requests, "post", lambda *a, **k: _FakeResp([]))
    assert list(generator.stream_ollama([])) == []


def test_request_targets_native_api_with_options(monkeypatch):
    captured = {}

    def _fake_post(url, **kw):
        captured["url"] = url
        captured["json"] = kw.get("json")
        return _FakeResp([])

    monkeypatch.setattr(generator.requests, "post", _fake_post)
    list(generator.stream_ollama([{"role": "user", "content": "hi"}]))

    assert captured["url"].endswith("/api/chat")  # KHÔNG phải /v1 (nuốt options)
    chat = get_settings().llm.chat
    opts = captured["json"]["options"]
    assert opts["num_ctx"] == chat.num_ctx
    assert opts["num_predict"] == chat.max_new_tokens
    assert opts["temperature"] == chat.temperature


def test_native_url_mapping():
    assert (
        generator.native_chat_url("http://ollama:11434/v1/chat/completions")
        == "http://ollama:11434/api/chat"
    )
    assert generator.native_chat_url("http://x:1/api/chat") == "http://x:1/api/chat"


def test_stream_ollama_uses_explicit_model_and_settings(monkeypatch, settings_override):
    settings_override(
        {"services.ollama_url": "http://o.test/v1/chat/completions", "llm.chat.num_ctx": 4096}
    )
    seen = {}

    def fake_post(url, json, stream, timeout):
        seen.update(url=url, body=json)
        return _FakeResp([b'{"message": {"content": "x"}, "done": true}'])

    monkeypatch.setattr(generator.requests, "post", fake_post)
    out = "".join(generator.stream_ollama([{"role": "user", "content": "q"}], model="m-test"))
    assert out == "x"
    assert seen["url"] == "http://o.test/api/chat"
    assert seen["body"]["model"] == "m-test"
    assert seen["body"]["options"]["num_ctx"] == 4096
