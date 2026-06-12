"""Tầng integration: tripwire eval nhanh trên eval_tiny.jsonl (4 câu).

Tái dùng run_hybrid + _hit_rank + compute_metrics của eval/run_eval (KHÔNG viết lại
toán). Đây CHỈ là dây bẫy nhanh — gate chuẩn vẫn là `make eval` (recall@5 ≥ 0.85,
đủ 55 câu).
"""

import json

import pytest

from eval.run_eval import _hit_rank, compute_metrics, run_hybrid


@pytest.mark.slow
def test_eval_tiny_recall(require_services, data_dir):
    require_services("qdrant", "embedding", "reranker")
    lines = (data_dir / "eval_tiny.jsonl").read_text(encoding="utf-8").splitlines()
    items = [json.loads(ln) for ln in lines if ln.strip()]

    ranks = [_hit_rank(run_hybrid(it["question"], top_n=10), it["expected"]) for it in items]
    m = compute_metrics(ranks, [5])

    # Ngưỡng nới cho bộ tripwire nhỏ; gate chuẩn là `make eval` ≥ 0.85.
    assert m["recall@5"] >= 0.6, (
        f"recall@5={m['recall@5']:.2f} trên {len(items)} câu tripwire — "
        f"chạy `make eval` để kiểm tra đầy đủ."
    )
