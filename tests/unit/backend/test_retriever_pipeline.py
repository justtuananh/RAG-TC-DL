"""Pipeline hybrid đầy đủ — retrieval.retriever.retrieve (mock toàn bộ I/O).

Mock: embed_query, dense_search, bm25_search (import-trong-hàm → patch symbol GỐC),
router.route, fetch_parent; stub HTTP rerank :8011. Không chạm mạng thật.
"""

import json

import responses

import retrieval.retriever as R
from retrieval.retriever import RERANK_URL


def _child(cid, pid, section="6 Tiến hành > 6.1 X"):
    return {
        "id": cid,
        "score": 1.0,
        "payload": {
            "chunk_id": cid,
            "parent_id": pid,
            "section_path": section,
            "text": f"child-{cid}",
            "file_stem": "QTKD_1.061_2021_ND_V2",
            "kind": "paragraph",
        },
    }


def _rerank_callback(req):
    n = len(json.loads(req.body)["documents"])
    results = [{"index": i, "relevance_score": 1.0 - i * 0.1} for i in range(n)]
    return (200, {}, json.dumps({"results": results}))


@responses.activate
def test_pipeline_dedups_by_parent_and_sorts(monkeypatch):
    dense = [_child("c1", "p1"), _child("c2", "p2")]
    bm25 = [_child("c1", "p1"), _child("c3", "p2")]  # c3 cùng parent p2 với c2
    monkeypatch.setattr(R, "embed_query", lambda q: [0.0] * 1024)
    monkeypatch.setattr(R, "dense_search", lambda vec, top_k=50, file_stem=None: dense)
    monkeypatch.setattr(
        "retrieval.bm25_index.bm25_search", lambda q, top_k=50, file_stem=None: bm25
    )
    monkeypatch.setattr("retrieval.router.route", lambda q: None)
    monkeypatch.setattr(
        R,
        "fetch_parent",
        lambda pid: {
            "text": f"parent-{pid}",
            "section_path": "6 Tiến hành",
            "file_stem": "QTKD_1.061_2021_ND_V2",
        },
    )
    responses.add_callback(
        responses.POST, RERANK_URL, callback=_rerank_callback, content_type="application/json"
    )

    out = R.retrieve("câu hỏi", top_k=50, top_n=5)

    # 3 chunk_id (c1,c2,c3) → dedup theo parent_id (p1,p2) → 2 kết quả.
    assert len(out) == 2
    assert all("parent_payload" in h and "rerank_score" in h for h in out)
    scores = [h["rerank_score"] for h in out]
    assert scores == sorted(scores, reverse=True)


@responses.activate
def test_routing_fallback_when_too_few_hits(monkeypatch):
    calls = {"dense": [], "bm25": []}

    def dense_search(vec, top_k=50, file_stem=None):
        calls["dense"].append(file_stem)
        if file_stem:
            return [_child("c1", "p1")]  # quá ít → kích fallback
        return [_child(f"c{i}", f"p{i}") for i in range(4)]

    def bm25_search(q, top_k=50, file_stem=None):
        calls["bm25"].append(file_stem)
        return [] if file_stem else [_child("c9", "p9")]

    monkeypatch.setattr(R, "embed_query", lambda q: [0.0] * 1024)
    monkeypatch.setattr(R, "dense_search", dense_search)
    monkeypatch.setattr("retrieval.bm25_index.bm25_search", bm25_search)
    monkeypatch.setattr("retrieval.router.route", lambda q: "QTKD_1.061_2021_ND_V2")
    monkeypatch.setattr(
        R, "fetch_parent", lambda pid: {"text": "p", "section_path": "s", "file_stem": "f"}
    )
    responses.add_callback(
        responses.POST, RERANK_URL, callback=_rerank_callback, content_type="application/json"
    )

    R.retrieve("van an toàn 1.061", top_k=50, top_n=5)

    assert calls["dense"][0] == "QTKD_1.061_2021_ND_V2"  # lần đầu có lọc file
    assert None in calls["dense"]  # fallback: tìm lại toàn corpus
    assert None in calls["bm25"]


def test_rerank_hits_empty_returns_empty():
    # Không gọi mạng (return sớm) — an toàn dưới network-guard.
    assert R.rerank_hits("q", []) == []
