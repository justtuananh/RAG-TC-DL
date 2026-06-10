"""Spike E2 — Eval CHẤT LƯỢNG CÂU TRẢ LỜI (không chỉ retrieval).

Chạy ĐÚNG đường production cho từng câu: production_retrieve → build_context →
build_messages → stream_ollama, rồi chấm bằng eval.scoring (key-fact coverage +
citation + refusal + ảo giác). So sánh nhiều model cạnh nhau để tách lỗi-do-model
(1.5b vs 7b) khỏi lỗi-do-pipeline.

Usage:
  python -m eval.answer_eval [--model qwen2.5:1.5b,qwen2.5:7b]
                             [--answer-file eval/answer_set.jsonl]
                             [--category multi_section] [--limit N] [-v]

Requires: 4 service Docker (embedding :8010, reranker :8011, qdrant :6333, ollama :11434)
+ model đã pull. Chạy bằng kotaemon/.venv (qdrant-client, requests, rank_bm25).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests  # noqa: E402

import generation  # noqa: E402
from eval import scoring  # noqa: E402
from eval._pipeline import production_retrieve  # noqa: E402


# ── service / model helpers ───────────────────────────────────────────────────

def _services_up() -> bool:
    from scripts.healthcheck import wait_for

    status = wait_for(["embedding", "reranker", "qdrant", "ollama"], timeout=120)
    return all(status.values())


def _available_models() -> set[str]:
    base = generation.OLLAMA_URL.split("/v1/")[0]
    try:
        resp = requests.get(base + "/api/tags", timeout=10)
        resp.raise_for_status()
        return {m["name"] for m in resp.json().get("models", [])}
    except Exception:
        return set()


def _answer(query: str, retrieved: list[dict], model: str) -> str:
    """Sinh câu trả lời cho model chỉ định, dùng cùng ngữ cảnh đã retrieve."""
    context_str, _ = generation.build_context_and_citations(retrieved)
    messages = generation.build_messages(query, context_str, [])
    generation.OLLAMA_MODEL = model  # stream_ollama đọc biến module này
    return "".join(generation.stream_ollama(messages))


# ── tổng hợp báo cáo ──────────────────────────────────────────────────────────

def _aggregate(records: list[dict]) -> dict:
    """Gộp list record (cùng 1 model) thành metric theo category + tổng."""
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r)

    def _metrics(rs: list[dict]) -> dict:
        covs = [r["coverage"] for r in rs if r["coverage"] is not None]
        cite_strict = [r["citation"]["accuracy_strict"] for r in rs if r["citation"]["present_with_source"]]
        cite_lenient = [r["citation"]["accuracy_lenient"] for r in rs if r["citation"]["present_with_source"]]
        refus = [r for r in rs if r["expected_refusal"]]
        refus_ok = sum(1 for r in refus if r["refusal_correct"])
        wrong_refusal = sum(1 for r in rs if not r["expected_refusal"] and r["refused"])
        hall = sum(1 for r in rs if r["hallucination"]["count"] > 0)
        return {
            "n": len(rs),
            "coverage": sum(covs) / len(covs) if covs else float("nan"),
            "citation_strict": sum(cite_strict) / len(cite_strict) if cite_strict else float("nan"),
            "citation_lenient": sum(cite_lenient) / len(cite_lenient) if cite_lenient else float("nan"),
            "refusal_acc": refus_ok / len(refus) if refus else float("nan"),
            "wrong_refusal": wrong_refusal,
            "hallucination_rate": hall / len(rs) if rs else float("nan"),
        }

    return {
        "overall": _metrics(records),
        "by_category": {cat: _metrics(rs) for cat, rs in sorted(by_cat.items())},
    }


def _fmt(x: float) -> str:
    return "  n/a" if x != x else f"{x:.3f}"  # x!=x → NaN


def _print_model_report(model: str, agg: dict) -> None:
    print(f"\n{'=' * 64}\n[{model}]\n{'=' * 64}")
    header = f"{'category':<14} {'n':>3} {'cov':>6} {'cite_s':>7} {'cite_l':>7} {'refuse':>7} {'halluc':>7}"
    print(header)
    print("-" * len(header))
    for cat, m in agg["by_category"].items():
        print(
            f"{cat:<14} {m['n']:>3} {_fmt(m['coverage']):>6} {_fmt(m['citation_strict']):>7} "
            f"{_fmt(m['citation_lenient']):>7} {_fmt(m['refusal_acc']):>7} {_fmt(m['hallucination_rate']):>7}"
        )
    o = agg["overall"]
    print("-" * len(header))
    print(
        f"{'OVERALL':<14} {o['n']:>3} {_fmt(o['coverage']):>6} {_fmt(o['citation_strict']):>7} "
        f"{_fmt(o['citation_lenient']):>7} {_fmt(o['refusal_acc']):>7} {_fmt(o['hallucination_rate']):>7}"
    )
    if o["wrong_refusal"]:
        print(f"  ⚠ từ chối nhầm (in-scope mà vẫn 'không tìm thấy'): {o['wrong_refusal']}")


def _print_side_by_side(aggs: dict[str, dict]) -> None:
    models = list(aggs)
    if len(models) < 2:
        return
    print(f"\n{'=' * 64}\n[SO SÁNH MODEL — overall]\n{'=' * 64}")
    metrics = ["coverage", "citation_strict", "citation_lenient", "refusal_acc", "hallucination_rate"]
    head = f"{'metric':<18}" + "".join(f"{m.split(':')[-1]:>12}" for m in models) + f"{'Δ':>10}"
    print(head)
    print("-" * len(head))
    for met in metrics:
        vals = [aggs[m]["overall"][met] for m in models]
        delta = (vals[-1] - vals[0]) if all(v == v for v in vals) else float("nan")
        row = f"{met:<18}" + "".join(f"{_fmt(v):>12}" for v in vals) + f"{_fmt(delta):>10}"
        print(row)
    print(
        "\nĐọc: 7b≫1.5b ở coverage nhưng cả hai thấp ở citation/refusal ⇒ lỗi pipeline/prompt; "
        "cả hai thấp ở multi_section/cross_file ⇒ ngân sách ngữ cảnh/router."
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Eval chất lượng câu trả lời QTKĐ")
    parser.add_argument("--model", default="qwen2.5:1.5b,qwen2.5:7b",
                        help="Danh sách model (phân tách dấu phẩy) để so sánh.")
    parser.add_argument("--answer-file", default="eval/answer_set.jsonl")
    parser.add_argument("--category", default=None, help="Chỉ chạy 1 category.")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số câu (smoke).")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    eval_path = Path(args.answer_file)
    if not eval_path.exists():
        print(f"ERROR: {eval_path} not found", file=sys.stderr)
        sys.exit(1)

    if not _services_up():
        print("❌ Service chưa sẵn sàng. Chạy `make up` trước.", file=sys.stderr)
        sys.exit(1)

    items = [json.loads(ln) for ln in eval_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if args.category:
        items = [it for it in items if it.get("category") == args.category]
    if args.limit:
        items = items[: args.limit]
    print(f"Loaded {len(items)} câu eval từ {eval_path}")

    requested = [m.strip() for m in args.model.split(",") if m.strip()]
    avail = _available_models()
    models = [m for m in requested if m in avail]
    skipped = [m for m in requested if m not in avail]
    for m in skipped:
        print(f"⚠ bỏ qua model chưa pull: {m}  (chạy `make pull-model` / `make pull-model-7b`)")
    if not models:
        print("❌ Không có model nào sẵn sàng.", file=sys.stderr)
        sys.exit(1)

    # Retrieve MỘT lần/câu, tái dùng cho mọi model (retrieval không phụ thuộc model).
    print("\n🔍 Retrieve ngữ cảnh (1 lần/câu)…")
    retrieved_by_id: dict = {}
    for it in items:
        t0 = time.time()
        retrieved_by_id[it["id"]] = production_retrieve(it["question"], top_n=5)
        if args.verbose:
            print(f"  [{it['id']}] {it['question'][:50]}… ({time.time() - t0:.1f}s)")

    aggs: dict[str, dict] = {}
    for model in models:
        print(f"\n💬 Sinh câu trả lời với {model}…")
        records: list[dict] = []
        for it in items:
            retrieved = retrieved_by_id[it["id"]]
            t0 = time.time()
            try:
                ans = _answer(it["question"], retrieved, model)
            except Exception as e:
                print(f"  [{it['id']}] LỖI sinh: {e}")
                ans = ""
            rec = scoring.score_question(it, ans, retrieved)
            records.append(rec)
            if args.verbose:
                cov = "—" if rec["coverage"] is None else f"{rec['coverage']:.2f}"
                print(f"  [{it['id']}] {it['category']:<13} cov={cov} "
                      f"refuse_ok={rec['refusal_correct']} halluc={rec['hallucination']['count']} "
                      f"({time.time() - t0:.1f}s)")
        agg = _aggregate(records)
        aggs[model] = agg
        _print_model_report(model, agg)

    _print_side_by_side(aggs)


if __name__ == "__main__":
    main()
