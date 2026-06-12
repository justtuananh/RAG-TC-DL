"""Ngữ nghĩa chấm điểm eval — eval.run_eval (thuần, KHÔNG service).

KHÓA toán metric mà không viết lại nó: recall@k, MRR, và khớp section theo tiền tố.
"""

import pytest

from eval.run_eval import _hit_rank, _matches, compute_metrics


def test_recall_at_k():
    m = compute_metrics([1, 2, None, 3], [1, 3, 5])
    assert m["recall@1"] == pytest.approx(0.25)
    assert m["recall@3"] == pytest.approx(0.75)
    assert m["recall@5"] == pytest.approx(0.75)
    assert m["n"] == 4
    assert m["found"] == 3
    assert m["miss"] == 1


def test_mrr():
    m = compute_metrics([1, 2, 4], [5])
    assert m["MRR"] == pytest.approx((1 + 0.5 + 0.25) / 3)


def test_matches_requires_same_file_and_prefix_section():
    exp = {"file_stem": "QTKD_1.061", "section_path": "6 Tiến hành"}
    assert _matches({"file_stem": "QTKD_1.061", "section_path": "6 Tiến hành > 6.3 Đo"}, exp)
    assert _matches({"file_stem": "QTKD_1.061", "section_path": "6 Tiến hành"}, exp)
    assert not _matches({"file_stem": "QTKD_1.062", "section_path": "6 Tiến hành"}, exp)


def test_hit_rank_returns_first_match_or_none():
    results = [
        {"payload": {"file_stem": "A", "section_path": "1 X"}},
        {"payload": {"file_stem": "B", "section_path": "2 Y > 2.1 Z"}},
    ]
    assert _hit_rank(results, [{"file_stem": "B", "section_path": "2 Y"}]) == 2
    assert _hit_rank(results, [{"file_stem": "Z", "section_path": "9"}]) is None
