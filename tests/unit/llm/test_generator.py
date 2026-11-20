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


class _ServerErrorResp:
    """Ollama trả 500 (OOM-kill khi nạp lại model dưới áp lực RAM)."""

    status_code = 500

    def raise_for_status(self):
        raise generator.requests.HTTPError("500 Server Error", response=self)

    def iter_lines(self):
        return iter(())

    def close(self):
        pass


def test_transient_500_is_retried_before_first_token(monkeypatch):
    responses = [_ServerErrorResp(), _FakeResp([b'{"message":{"content":"OK"},"done":true}'])]
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        return responses.pop(0)

    monkeypatch.setattr(generator.requests, "post", fake_post)
    monkeypatch.setattr(generator.time, "sleep", lambda s: None)
    assert list(generator.stream_ollama([{"role": "user", "content": "hi"}])) == ["OK"]
    assert len(calls) == 2


def test_chat_once_retries_a_transient_500_without_streaming(monkeypatch):
    class _JsonResp(_ServerErrorResp):
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": " Tóm tắt "}}

    responses = [_ServerErrorResp(), _JsonResp()]
    streams = []

    def fake_post(*args, **kwargs):
        streams.append(kwargs["stream"])
        return responses.pop(0)

    monkeypatch.setattr(generator.requests, "post", fake_post)
    monkeypatch.setattr(generator.time, "sleep", lambda s: None)
    assert generator.chat_once([], num_predict=10, timeout_s=5) == "Tóm tắt"
    assert streams == [False, False]


def test_persistent_500_raises_after_bounded_retries(monkeypatch):
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        return _ServerErrorResp()

    monkeypatch.setattr(generator.requests, "post", fake_post)
    monkeypatch.setattr(generator.time, "sleep", lambda s: None)
    try:
        list(generator.stream_ollama([]))
    except generator.requests.HTTPError:
        pass
    else:
        raise AssertionError("phải ném HTTPError sau khi hết lần thử lại")
    assert len(calls) == generator.MAX_CHAT_ATTEMPTS


def test_client_error_4xx_is_not_retried(monkeypatch):
    class _BadRequest(_ServerErrorResp):
        status_code = 400

    calls = []

    def fake_post(*args, **kwargs):
        calls.append(1)
        return _BadRequest()

    monkeypatch.setattr(generator.requests, "post", fake_post)
    monkeypatch.setattr(generator.time, "sleep", lambda s: None)
    try:
        list(generator.stream_ollama([]))
    except generator.requests.HTTPError:
        pass
    assert len(calls) == 1
