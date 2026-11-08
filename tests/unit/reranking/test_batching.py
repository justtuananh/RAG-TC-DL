"""Chia lô gọi reranker: lô nhỏ, tự chia đôi khi service lỗi (CUDA OOM), giữ đúng thứ tự điểm."""

import json

import pytest
import responses

from core.settings_loader import get_settings
from reranking import reranker
from reranking.reranker import make_batches, score_documents


@pytest.fixture(autouse=True)
def _reset_state():
    reranker._state.update(cap=None, ok_streak=0, fails=0)


def test_make_batches_respects_count_and_chars():
    docs = ["a" * 10] * 7
    assert make_batches(docs, 3, 10_000) == [[0, 1, 2], [3, 4, 5], [6]]
    assert make_batches(docs, 100, 25) == [[0, 1], [2, 3], [4, 5], [6]]
    assert make_batches([], 4, 100) == []


@responses.activate
def test_scores_keep_input_order_across_batches():
    sizes = []

    def cb(req):
        docs = json.loads(req.body)["documents"]
        sizes.append(len(docs))
        return (200, {}, json.dumps({"results": [{"index": i, "relevance_score": float(d)} for i, d in enumerate(docs)]}))

    responses.add_callback(responses.POST, get_settings().services.rerank_url, callback=cb, content_type="application/json")
    docs = [str(i) for i in range(20)]
    assert score_documents("q", docs) == [float(i) for i in range(20)]
    assert max(sizes) <= get_settings().reranking.batch_size and len(sizes) >= 3


@responses.activate
def test_failed_batch_is_halved_until_service_accepts():
    def cb(req):
        docs = json.loads(req.body)["documents"]
        if len(docs) > 2:  # giả lập OOM với lô lớn
            return (500, {}, "oom")
        return (200, {}, json.dumps({"results": [{"index": i, "relevance_score": float(d)} for i, d in enumerate(docs)]}))

    responses.add_callback(responses.POST, get_settings().services.rerank_url, callback=cb, content_type="application/json")
    docs = [str(i) for i in range(8)]
    assert score_documents("q", docs) == [float(i) for i in range(8)]
    assert reranker._state["cap"] == 2  # lần sau dùng ngay lô nhỏ


@responses.activate
def test_single_doc_failure_retried_as_pair():
    def cb(req):
        docs = json.loads(req.body)["documents"]
        if len(docs) == 1:
            return (500, {}, "oom")
        return (200, {}, json.dumps({"results": [{"index": i, "relevance_score": 0.5} for i in range(len(docs))]}))

    responses.add_callback(responses.POST, get_settings().services.rerank_url, callback=cb, content_type="application/json")
    assert score_documents("q", ["only"]) == [0.5]


@responses.activate
def test_documents_truncated_to_max_doc_chars():
    seen = []

    def cb(req):
        docs = json.loads(req.body)["documents"]
        seen.extend(len(d) for d in docs)
        return (200, {}, json.dumps({"results": [{"index": i, "relevance_score": 0.1} for i in range(len(docs))]}))

    responses.add_callback(responses.POST, get_settings().services.rerank_url, callback=cb, content_type="application/json")
    score_documents("q", ["x" * 5000])
    assert seen == [get_settings().reranking.max_doc_chars]
