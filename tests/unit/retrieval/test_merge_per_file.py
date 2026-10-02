"""_merge_per_file — quota đại diện mỗi file cho câu hỏi so sánh đa-file."""

from retrieval.retriever import _merge_per_file


def _h(file_stem, score):
    return {"payload": {"file_stem": file_stem}, "rerank_score": score}


def test_minority_file_guaranteed_representation():
    # File B chỉ có điểm thấp — một phễu thuần điểm sẽ loại sạch B khỏi top-5.
    reranked = [
        _h("A", 0.9),
        _h("A", 0.8),
        _h("A", 0.7),
        _h("A", 0.6),
        _h("A", 0.5),
        _h("B", 0.3),
        _h("B", 0.2),
    ]
    out = _merge_per_file(reranked, frozenset({"A", "B"}), top_n=5)
    files = [h["payload"]["file_stem"] for h in out]
    assert len(out) == 5
    assert files.count("B") == 2  # quota = 5 // 2 = 2
    assert files.count("A") == 3


def test_output_sorted_by_score_for_stable_citation_numbers():
    reranked = [_h("A", 0.9), _h("B", 0.95), _h("A", 0.5), _h("B", 0.1)]
    out = _merge_per_file(reranked, frozenset({"A", "B"}), top_n=4)
    scores = [h["rerank_score"] for h in out]
    assert scores == sorted(scores, reverse=True)


def test_three_files_each_get_one():
    reranked = [
        _h("A", 0.9),
        _h("A", 0.8),
        _h("A", 0.7),
        _h("B", 0.4),
        _h("C", 0.2),
    ]
    out = _merge_per_file(reranked, frozenset({"A", "B", "C"}), top_n=5)
    files = {h["payload"]["file_stem"] for h in out}
    assert files == {"A", "B", "C"}


def test_missing_file_in_results_is_tolerated():
    reranked = [_h("A", 0.9), _h("A", 0.8)]
    out = _merge_per_file(reranked, frozenset({"A", "B"}), top_n=5)
    assert [h["payload"]["file_stem"] for h in out] == ["A", "A"]
