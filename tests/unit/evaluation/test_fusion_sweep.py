"""Test đơn vị cho fusion_sweep: luật chọn, cache reranker, dedupe pool theo parent.

Không gọi service: các hàm thuần + cache dùng hàm service giả.
"""

from evaluation.fusion_sweep import (
    RerankDocCache,
    cached_io,
    dedupe_pool_by_parent,
    pick_winner,
)


def _row(
    alpha, k, *, tune5=0.90, hold5=1.0, comb5=0.90, mrr=0.85, rrf5=0.80, pool=0.95, misses=None
):
    return {
        "alpha": alpha,
        "k": k,
        "tune_recall@5": tune5,
        "holdout_recall@5": hold5,
        "combined_recall@5": comb5,
        "combined_MRR": mrr,
        "combined_rrf_recall@5": rrf5,
        "combined_pool_recall": pool,
        "combined_n": 65,
        "combined_miss_ids": misses or [],
    }


# ── pick_winner ──────────────────────────────────────────────────────────────


def test_pick_blocks_on_tune_gate():
    rows = [
        _row(0.5, 60, comb5=0.90),
        _row(0.3, 60, tune5=0.80, comb5=0.95),  # <0.85 → loại
    ]
    d = pick_winner(rows, rows[0])
    assert d.winner["alpha"] == 0.5
    assert d.change is False


def test_pick_blocks_on_holdout_below_baseline():
    rows = [
        _row(0.5, 60, comb5=0.90, hold5=1.0),
        _row(0.3, 60, comb5=0.95, hold5=0.90),  # bộ giữ lại thấp hơn mốc
    ]
    d = pick_winner(rows, rows[0])
    assert d.winner["alpha"] == 0.5
    assert d.change is False


def test_pick_keeps_baseline_when_gain_below_threshold():
    # Hơn 1 câu trên 65 (<2) → không đổi, và giữ mốc.
    rows = [
        _row(0.5, 60, comb5=0.90),
        _row(0.4, 60, comb5=0.90 + 1 / 65, mrr=0.86),
    ]
    d = pick_winner(rows, rows[0])
    assert d.change is False
    assert d.winner["alpha"] == 0.5


def test_pick_changes_on_two_question_gain():
    # Ứng viên alpha=0.2 hơn mốc 2 câu; láng giềng 0.1/0.3 cùng k chỉ kém ≤1 câu
    # (mốc alpha=0.5 không phải láng giềng vì cách 3 bước).
    rows = [
        _row(0.5, 60, comb5=0.90),
        _row(0.2, 60, comb5=0.90 + 2 / 65),
        _row(0.1, 60, comb5=0.90 + 1 / 65),
        _row(0.3, 60, comb5=0.90 + 1 / 65),
    ]
    d = pick_winner(rows, rows[0])
    assert d.change is True
    assert d.winner["alpha"] == 0.2


def test_pick_changes_on_mrr_when_recall_tied():
    # alpha=0.3 bằng recall@5, MRR cao hơn mốc; láng giềng 0.2/0.4 cùng k bằng recall.
    rows = [
        _row(0.5, 60, comb5=0.90, mrr=0.85),
        _row(0.3, 60, comb5=0.90, mrr=0.88),
        _row(0.2, 60, comb5=0.90, mrr=0.86),
        _row(0.4, 60, comb5=0.90, mrr=0.86),
    ]
    d = pick_winner(rows, rows[0])
    assert d.change is True
    assert d.winner["alpha"] == 0.3


def test_pick_refuses_change_that_regresses_baseline_hit():
    # alpha=0.2 hơn 2 câu nhưng làm trượt câu 7 mà mốc đang trúng → không đổi.
    rows = [
        _row(0.5, 60, comb5=0.90, misses=[]),
        _row(0.2, 60, comb5=0.90 + 2 / 65, misses=[7]),
        _row(0.1, 60, comb5=0.90 + 1 / 65, misses=[7]),
        _row(0.3, 60, comb5=0.90 + 1 / 65, misses=[7]),
    ]
    d = pick_winner(rows, rows[0])
    assert d.change is False
    assert d.winner["alpha"] == 0.5


def test_pick_tie_prefers_closer_to_baseline():
    rows = [
        _row(0.5, 60, comb5=0.95),
        _row(0.4, 60, comb5=0.95),
        _row(0.6, 60, comb5=0.95),
    ]
    d = pick_winner(rows, rows[0])
    # alpha=0.5 là mốc → đứng đầu xếp hạng (hòa hết, gần mốc nhất).
    assert d.winner["alpha"] == 0.5
    assert d.change is False


def test_pick_skips_plateau_neighbour_failure():
    # alpha=0.4 hơn 3 câu nhưng láng giềng alpha=0.3 kém 3 câu (>1) → loại,
    # chọn alpha=0.5 (mốc, không đổi).
    rows = [
        _row(0.5, 60, comb5=0.90),
        _row(0.4, 60, comb5=0.90 + 3 / 65),
        _row(0.3, 60, comb5=0.90),
    ]
    d = pick_winner(rows, rows[0])
    assert d.winner["alpha"] == 0.5
    assert d.change is False


# ── RerankDocCache ───────────────────────────────────────────────────────────


def test_score_cache_only_sends_new_documents_and_keeps_order():
    calls = []

    def fake_service(query, documents):
        calls.append((query, list(documents)))
        return [float(len(d)) for d in documents]

    cache = RerankDocCache(fake_service)
    first = cache("q", ["a", "b"])
    assert first == [1.0, 1.0]
    second = cache("q", ["b", "c"])
    assert second == [1.0, 1.0]
    assert calls == [("q", ["a", "b"]), ("q", ["c"])]  # chỉ gửi b chưa có
    assert cache.service_calls == 2
    # Khác query → cache riêng.
    cache("q2", ["a"])
    assert calls[-1] == ("q2", ["a"])


def test_score_cache_dedupes_documents_within_batch():
    calls = []

    def fake_service(query, documents):
        calls.append(list(documents))
        return [1.0] * len(documents)

    cache = RerankDocCache(fake_service)
    assert cache("q", ["a", "a", "b"]) == [1.0, 1.0, 1.0]
    assert calls == [["a", "b"]]


# ── dedupe_pool_by_parent ────────────────────────────────────────────────────


def test_dedupe_pool_keeps_first_of_each_parent_in_order():
    def h(cid, pid):
        return {"payload": {"chunk_id": cid, "parent_id": pid}}

    pool = [h("c1", "p1"), h("c2", "p2"), h("c3", "p1"), h("c4", "p3")]
    out = dedupe_pool_by_parent(pool)
    assert [x["payload"]["chunk_id"] for x in out] == ["c1", "c2", "c4"]


# ── cached_io: đi đúng đường + cache giảm lời gọi ─────────────────────────────


def test_cached_io_reduces_service_calls_across_configs(monkeypatch):
    """Lượt chạy sau chỉ gọi service cho cặp (query, document) chưa có."""
    from embedding import embedder
    from reranking import reranker
    from retrieval import hybrid_retriever
    from vectorstore import qdrant

    counts = {"embed": 0, "search": 0, "fetch": 0, "score": 0, "hits": 0}

    def fake_embed(q):
        counts["embed"] += 1
        return [0.0]

    def fake_search(vec, expanded_query, *, top_k, file_stem=None):
        counts["search"] += 1
        return [], []

    def fake_fetch(pid):
        counts["fetch"] += 1
        return {"text": "p"}

    def fake_score(query, documents):
        counts["score"] += 1
        return [1.0] * len(documents)

    def fake_rerank(query, hits, top_n=None):
        counts["hits"] += 1
        return hits

    monkeypatch.setattr(embedder, "embed_query", fake_embed)
    monkeypatch.setattr(hybrid_retriever, "search_both", fake_search)
    monkeypatch.setattr(qdrant, "fetch_parent", fake_fetch)
    monkeypatch.setattr(reranker, "score_documents", fake_score)
    monkeypatch.setattr(reranker, "rerank_hits", fake_rerank)

    def one_pass():
        embedder.embed_query("q")
        hybrid_retriever.search_both([0.0], "q", top_k=50, file_stem=None)
        qdrant.fetch_parent("p1")
        reranker.score_documents("q", ["d1", "d2"])
        reranker.rerank_hits("q", [{"payload": {"parent_id": "p1"}}], top_n=5)

    with cached_io():
        one_pass()
        one_pass()

    # Lượt thứ hai dùng cache: mỗi hàm thật chỉ được gọi đúng một lần.
    assert counts == {"embed": 1, "search": 1, "fetch": 1, "score": 1, "hits": 2}
    # Bản gốc được khôi phục sau khi thoát context manager.
    assert reranker.score_documents is fake_score
    assert embedder.embed_query is fake_embed
