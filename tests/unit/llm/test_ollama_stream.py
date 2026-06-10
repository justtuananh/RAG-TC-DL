"""Stream SSE từ Ollama — generation.stream_ollama.

Chỉ yield content delta; bỏ dòng rỗng, dòng không 'data: ', [DONE], và delta rỗng.
Mock requests.post trả response giả có iter_lines (không chạm mạng).
"""

import generation


class _FakeResp:
    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        pass

    def iter_lines(self):
        yield from self._lines


def test_yields_only_content_deltas(monkeypatch):
    lines = [
        b'data: {"choices":[{"delta":{"content":"Xin"}}]}',
        b"",  # rỗng → bỏ
        b'data: {"choices":[{"delta":{"content":" chao"}}]}',
        b"rac khong phai data",  # không 'data: ' → bỏ
        b'data: {"choices":[{"delta":{}}]}',  # không content → bỏ
        b"data: [DONE]",  # kết thúc → bỏ
    ]
    monkeypatch.setattr(generation.requests, "post", lambda *a, **k: _FakeResp(lines))
    out = list(generation.stream_ollama([{"role": "user", "content": "hi"}]))
    assert out == ["Xin", " chao"]


def test_malformed_json_is_skipped(monkeypatch):
    lines = [
        b"data: {khong-phai-json}",
        b'data: {"choices":[{"delta":{"content":"OK"}}]}',
    ]
    monkeypatch.setattr(generation.requests, "post", lambda *a, **k: _FakeResp(lines))
    assert list(generation.stream_ollama([])) == ["OK"]


def test_empty_stream(monkeypatch):
    monkeypatch.setattr(generation.requests, "post", lambda *a, **k: _FakeResp([]))
    assert list(generation.stream_ollama([])) == []
