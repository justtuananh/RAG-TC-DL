"""Spike E — Eval script: recall@k + nDCG@k + MRR for hybrid vs dense-only retrieval.

Usage:
  python -m eval.run_eval [--mode hybrid|dense|both] [--top-k 5] [--eval-file eval/eval_set.jsonl]

Requires: all Docker services running (embedding :8010, reranker :8011, qdrant :6333).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from retrieval.retriever import (
    TOP_K,
    RERANK_POOL,
    embed_query,
    dense_search,
    rerank_hits,
    rrf_fuse,
    _filter_noise,
    _expand_query,
)
from retrieval.bm25_index import bm25_search
from retrieval.router import route


# ── match logic ───────────────────────────────────────────────────────────────

def _matches(result_payload: dict, expected: dict) -> bool:
    """A hit matches if file_stem equals AND section_path starts with expected."""
    if result_payload.get("file_stem") != expected["file_stem"]:
        return False
    expected_path = expected["section_path"]
    result_path = result_payload.get("section_path", "")
    # Exact match OR result section is the expected section or a child of it
    return result_path == expected_path or result_path.startswith(expected_path)


def _hit_rank(results: list[dict], expected_list: list[dict]) -> int | None:
    """Return 1-based rank of first matching result, or None if not found."""
    for rank, r in enumerate(results, 1):
        p = r["payload"]
        for exp in expected_list:
            if _matches(p, exp):
                return rank
    return None


# ── retrieval pipelines ───────────────────────────────────────────────────────

def run_hybrid(query: str, top_n: int = 10) -> list[dict]:
    """Hybrid pipeline = ĐÚNG đường production (qua production_retrieve) — chống drift.

    Trước đây hàm này viết lại phễu với top_k=50; nay gọi thẳng retrieve() của app
    (top_k=20) nên `make eval` đo đúng recall mà người dùng nhận. `_debug_miss` bên
    dưới vẫn soi từng stage (cố ý nhân bản phễu CHỈ để chẩn đoán).
    """
    from eval._pipeline import production_retrieve
    return production_retrieve(query, top_n=top_n)


def run_dense(query: str, top_n: int = 10) -> list[dict]:
    """Dense-only pipeline (no routing) for comparison."""
    vec = embed_query(query)
    hits = dense_search(vec, top_k=TOP_K)
    return rerank_hits(query, hits, top_n=top_n)


def _debug_miss(query: str, expected: list[dict]) -> None:
    """Print stage-by-stage rank of expected hit for failed queries."""
    expanded = _expand_query(query)
    vec = embed_query(expanded)
    file_stem = route(query)

    dense_hits = dense_search(vec, top_k=TOP_K, file_stem=file_stem)
    bm25_hits = bm25_search(expanded, top_k=TOP_K, file_stem=file_stem)
    if file_stem and (len(dense_hits) + len(bm25_hits) < 6):
        dense_hits = dense_search(vec, top_k=TOP_K)
        bm25_hits = bm25_search(expanded, top_k=TOP_K)

    fused = _filter_noise(rrf_fuse(dense_hits, bm25_hits))
    reranked = rerank_hits(query, fused[:RERANK_POOL], top_n=10)

    d_rank = _hit_rank(dense_hits, expected)
    b_rank = _hit_rank(bm25_hits, expected)
    f_rank = _hit_rank(fused, expected)
    r_rank = _hit_rank(reranked, expected)
    exp = expected[0]
    router_label = file_stem if file_stem else "None"
    print(f"    DEBUG router={router_label} "
          f"dense={d_rank} bm25={b_rank} fused={f_rank} rerank={r_rank}")
    print(f"    expected: {exp['file_stem']} | {exp['section_path']}")


# ── metrics ───────────────────────────────────────────────────────────────────

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


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Spike E — recall@k eval")
    parser.add_argument("--mode", choices=["hybrid", "dense", "both"], default="both")
    parser.add_argument("--top-k", type=int, default=5, help="k for recall@k (primary)")
    parser.add_argument("--eval-file", default="eval/eval_set.jsonl")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--debug-miss", action="store_true",
                        help="For each MISS, re-run and print stage-by-stage ranks")
    args = parser.parse_args()

    eval_path = Path(args.eval_file)
    if not eval_path.exists():
        print(f"ERROR: {eval_path} not found", file=sys.stderr)
        sys.exit(1)

    items = [json.loads(line) for line in eval_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"Loaded {len(items)} eval pairs from {eval_path}\n")

    modes = ["hybrid", "dense"] if args.mode == "both" else [args.mode]
    all_ranks: dict[str, list[int | None]] = {m: [] for m in modes}
    all_file_stems = [item["expected"][0]["file_stem"] for item in items]

    for i, item in enumerate(items, 1):
        q = item["question"]
        expected = item["expected"]
        print(f"[{i:02d}/{len(items)}] {q[:60]}…")

        for mode in modes:
            t0 = time.time()
            try:
                results = run_hybrid(q, top_n=10) if mode == "hybrid" else run_dense(q, top_n=10)
                rank = _hit_rank(results, expected)
                all_ranks[mode].append(rank)
                elapsed = time.time() - t0
                status = f"rank={rank}" if rank else "MISS"
                print(f"  [{mode}] {status} ({elapsed:.1f}s)")
                if args.verbose and rank:
                    top = results[rank - 1]["payload"]
                    print(f"    → {top['file_stem']} | {top['section_path']}")
            except Exception as e:
                print(f"  [{mode}] ERROR: {e}")
                all_ranks[mode].append(None)

        # Debug pass: show per-stage ranks for hybrid misses
        if args.debug_miss and "hybrid" in modes:
            hybrid_rank = all_ranks["hybrid"][-1]
            if hybrid_rank is None or hybrid_rank > args.top_k:
                try:
                    _debug_miss(q, expected)
                except Exception as de:
                    print(f"    DEBUG ERROR: {de}")

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    ks = [1, 3, args.top_k, 10]
    ks = sorted(set(k for k in ks if k <= 10))

    for mode in modes:
        m = compute_metrics(all_ranks[mode], ks)
        mean_r = f"{m['mean_rank']:.1f}" if not math.isnan(m["mean_rank"]) else "n/a"
        print(f"\n[{mode.upper()}]  n={m['n']}  found={m['found']}  miss={m['miss']}  mean_rank={mean_r}")
        for k in ks:
            bar = "█" * round(m[f"recall@{k}"] * 20)
            print(f"  recall@{k:2d}: {m[f'recall@{k}']:.3f}  nDCG@{k}: {m[f'ndcg@{k}']:.3f}  {bar}")
        print(f"  MRR:      {m['MRR']:.3f}")

    if args.mode == "both":
        print("\n[HYBRID vs DENSE delta]")
        for k in ks:
            h = compute_metrics(all_ranks["hybrid"], [k])[f"recall@{k}"]
            d = compute_metrics(all_ranks["dense"], [k])[f"recall@{k}"]
            sign = "+" if h >= d else "-"
            print(f"  recall@{k:2d}: {sign}{abs(h-d):.3f}  (hybrid={h:.3f} dense={d:.3f})")

    # Per-file recall@5 breakdown (hybrid only)
    primary_k = args.top_k
    if "hybrid" in modes:
        print(f"\n[PER-FILE recall@{primary_k} — hybrid]")
        by_file: dict[str, list] = defaultdict(list)
        for stem, rank in zip(all_file_stems, all_ranks["hybrid"]):
            by_file[stem].append(rank)
        _stem_num = re.compile(r'QTKD_(\d+\.\d+)')
        for stem in sorted(by_file):
            file_ranks = by_file[stem]
            hits = sum(1 for r in file_ranks if r is not None and r <= primary_k)
            m2 = _stem_num.search(stem)
            label = f"QTKD_{m2.group(1)}" if m2 else stem
            print(f"  {label}: {hits}/{len(file_ranks)} ({hits/len(file_ranks):.2f})")

    # Goal check
    if "hybrid" in modes:
        goal = 0.85
        r5 = compute_metrics(all_ranks["hybrid"], [primary_k])[f"recall@{primary_k}"]
        status = "✅ PASS" if r5 >= goal else "❌ FAIL"
        print(f"\nGoal: recall@{primary_k} ≥ {goal}  →  {r5:.3f}  {status}")


if __name__ == "__main__":
    main()
