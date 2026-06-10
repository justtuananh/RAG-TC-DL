"""Tầng integration: smoke end-to-end — retrieve → build context → LLM trả lời thật.

Cần cả 4 service + model đã pull (make pull-model). Đây là test "cả hệ thống có
trả lời không" duy nhất.
"""

import requests


def test_end_to_end_answer(require_services):
    require_services()  # cả 4, gồm ollama
    import app
    from retrieval.retriever import retrieve

    q = "Sai số cho phép của áp suất chỉnh đặt van an toàn là bao nhiêu?"
    results = retrieve(q, top_k=20, top_n=5)
    assert results, "retrieve rỗng — đã `make index` chưa?"

    context_str, _ = app._build_context_and_citations(results)
    messages = app._build_messages(q, context_str, [])

    import pytest

    try:
        answer = "".join(app._stream_ollama(messages))
    except requests.HTTPError as e:
        pytest.skip(f"Ollama lỗi — có thể chưa `make pull-model`: {e}")

    assert answer.strip(), "LLM trả lời rỗng"
