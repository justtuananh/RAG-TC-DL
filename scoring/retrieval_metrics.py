"""Số đo truy hồi thuần (không service): khớp section, thứ hạng hit, recall@k/nDCG/MRR.

Tách từ `run_eval.py` để `evaluation.run_eval` và test dùng chung một nguồn,
tránh viết lại toán metric ở nhiều nơi.
"""

from __future__ import annotations

import math


def matches(result_payload: dict, expected: dict) -> bool:
    """A hit matches if file_stem equals AND section_path starts with expected."""
    if result_payload.get("file_stem") != expected["file_stem"]:
        return False
    expected_path = expected["section_path"]
    result_path = result_payload.get("section_path", "")
    # Exact match OR result section is the expected section or a child of it
    return result_path == expected_path or result_path.startswith(expected_path)


def hit_rank(results: list[dict], expected_list: list[dict]) -> int | None:
    """Return 1-based rank of first matching result, or None if not found."""
    for rank, r in enumerate(results, 1):
        p = r["payload"]
        for exp in expected_list:
            if matches(p, exp):
                return rank
    return None


def compute_metrics(ranks: list[int | None], ks: list[int]) -> dict:
    n = len(ranks)
    metrics: dict = {}
    found_ranks = [r for r in ranks if r is not None]
    for k in ks:
        hits_k = [r for r in found_ranks if r <= k]
        metrics[f"recall@{k}"] = len(hits_k) / n
        metrics[f"ndcg@{k}"] = sum(1.0 / math.log2(r + 1) for r in hits_k) / n
    metrics["MRR"] = sum(1 / r for r in found_ranks) / n
    metrics["n"] = n
    metrics["found"] = len(found_ranks)
    metrics["miss"] = n - len(found_ranks)
    metrics["mean_rank"] = sum(found_ranks) / len(found_ranks) if found_ranks else float("nan")
    return metrics
