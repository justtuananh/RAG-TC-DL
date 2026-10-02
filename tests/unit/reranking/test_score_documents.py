"""score_documents - lời gọi HTTP cross-encoder tách riêng để cache theo cặp.

Mock service bằng thư viện responses, không chạm mạng thật.
"""

import json

import pytest
import requests
import responses

from core.settings_loader import get_settings
from reranking.reranker import score_documents


@responses.activate
def test_results_realigned_to_input_order():
    def callback(req):
        docs = json.loads(req.body)["documents"]
        # Service trả LỘN thứ tự: index 2, 1, 0.
        results = [{"index": i, "relevance_score": 0.1 * i} for i in reversed(range(len(docs)))]
        return (200, {}, json.dumps({"results": results}))

    responses.add_callback(
        responses.POST,
        get_settings().services.rerank_url,
        callback=callback,
        content_type="application/json",
    )

    scores = score_documents("q", ["d0", "d1", "d2"])

    assert scores == pytest.approx([0.0, 0.1, 0.2])


@responses.activate
def test_http_error_raises():
    responses.add(responses.POST, get_settings().services.rerank_url, status=500)
    with pytest.raises(requests.HTTPError):
        score_documents("q", ["d0"])


def test_empty_documents_returns_empty_without_calling_service():
    # Không có responses → mọi lời gọi mạng sẽ bị network-guard chặn.
    assert score_documents("q", []) == []


@responses.activate
def test_missing_result_raises_instead_of_scoring_zero():
    # Service trả thiếu điểm cho một document: không được lặng lẽ cho điểm 0.
    body = {"results": [{"index": 0, "relevance_score": 0.9}]}
    responses.add(responses.POST, get_settings().services.rerank_url, json=body)
    with pytest.raises(ValueError):
        score_documents("q", ["d0", "d1"])
