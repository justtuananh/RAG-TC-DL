"""Reciprocal Rank Fusion — retrieval.hybrid_retriever.rrf_fuse.

score(d) = Σ 1/(k + rank_i(d)); k lấy từ settings (mặc định 60). Hợp nhất theo
payload.chunk_id.
"""

import pytest

from retrieval.hybrid_retriever import rrf_fuse


def _hit(cid):
    return {"payload": {"chunk_id": cid, "text": cid}}


def test_shared_id_ranks_first_and_scores_sum():
    dense = [_hit("a"), _hit("b")]  # b ở rank 1 (index 1)
    bm25 = [_hit("b"), _hit("c")]  # b ở rank 0 (index 0)
    fused = rrf_fuse(dense, bm25, k=60)

    cids = [h["payload"]["chunk_id"] for h in fused]
    assert cids[0] == "b"

    b_score = next(h["rrf_score"] for h in fused if h["payload"]["chunk_id"] == "b")
    assert b_score == pytest.approx(1 / 62 + 1 / 61)


def test_union_dedup_and_score_key():
    dense = [_hit("a"), _hit("b")]
    bm25 = [_hit("b"), _hit("c")]
    fused = rrf_fuse(dense, bm25)
    assert sorted(h["payload"]["chunk_id"] for h in fused) == ["a", "b", "c"]
    assert all("rrf_score" in h for h in fused)


def test_sorted_descending():
    fused = rrf_fuse([_hit("a"), _hit("b"), _hit("c")], [])
    scores = [h["rrf_score"] for h in fused]
    assert scores == sorted(scores, reverse=True)


def test_default_k_is_60():
    # rank-0-only hit: score == 1/(k+1). Mặc định k=60 → 1/61.
    fused = rrf_fuse([_hit("a")], [])
    assert fused[0]["rrf_score"] == pytest.approx(1 / 61)


def test_empty_inputs():
    assert rrf_fuse([], []) == []


def test_rrf_k_comes_from_settings(settings_override):
    settings_override({"retrieval.rrf_k": 1})
    fused = rrf_fuse([{"id": 1, "score": 1.0, "payload": {"chunk_id": "a"}}], [])
    assert fused[0]["rrf_score"] == 1.0 / (1 + 0 + 1)  # 1/(k + rank + 1), rank từ 0
