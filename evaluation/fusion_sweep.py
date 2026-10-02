"""Công cụ quét lưới trọng số RRF dense/BM25 + ``rrf_k`` trên bộ eval thật.

Mục đích: đo ảnh hưởng của tỷ lệ trọng số dense/BM25 trong RRF tới chất lượng
truy hồi, rồi chọn cấu hình tốt nhất theo một LUẬT CHỌN CỐ ĐỊNH viết trước.

Chống drift: công cụ KHÔNG chép lại phễu truy hồi. Mỗi cấu hình gọi đúng
``retrieval.retriever.retrieve`` của production; chỉ thay các hàm I/O bằng bản
có cache ở cấp thuộc tính module để không gọi lại service cho mỗi cấu hình.

Chạy: ``python -m evaluation.fusion_sweep`` (cần 3 service Docker đang chạy).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

# Cho phép chạy từ thư mục gốc repo.
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.settings_loader import overridden
from scoring.retrieval_metrics import compute_metrics, hit_rank

# ── lưới mặc định ────────────────────────────────────────────────────────────
DEFAULT_ALPHAS = [round(0.1 * i, 1) for i in range(11)]  # 0.0 .. 1.0
DEFAULT_KS = [10, 20, 40, 60, 100]
BASELINE_ALPHA = 0.5
BASELINE_K = 60
COMBINED_N = 65
TOP_CONFIGS = 10


# ── luật chọn (hàm thuần, test được) ─────────────────────────────────────────


@dataclass
class Decision:
    """Kết quả luật chọn: cấu hình thắng, có đổi production không, lý do."""

    winner: dict
    change: bool
    reason: str


@dataclass
class _Row:
    """Một hàng kết quả của lưới, đã bung sẵn các cột dùng cho luật chọn."""

    alpha: float
    k: int
    tune_recall5: float
    holdout_recall5: float
    combined_recall5: float
    combined_mrr: float
    combined_rrf_recall5: float
    combined_pool_recall: float
    misses: set = field(default_factory=set)
    raw: dict = field(default_factory=dict)


def _row_from_dict(d: dict) -> _Row:
    return _Row(
        alpha=float(d["alpha"]),
        k=int(d["k"]),
        tune_recall5=float(d["tune_recall@5"]),
        holdout_recall5=float(d["holdout_recall@5"]),
        combined_recall5=float(d["combined_recall@5"]),
        combined_mrr=float(d["combined_MRR"]),
        combined_rrf_recall5=float(d["combined_rrf_recall@5"]),
        combined_pool_recall=float(d["combined_pool_recall"]),
        misses=set(d.get("combined_miss_ids", [])),
        raw=d,
    )


def pick_winner(rows: list[dict], baseline: dict) -> Decision:
    """Áp luật chọn cố định (mục 3e của plan) lên kết quả lưới.

    1. loại cấu hình có recall@5 bộ tinh chỉnh < 0.85 (gate dự án);
    2. loại cấu hình có recall@5 bộ giữ lại thấp hơn mốc;
    3. xếp hạng theo recall@5 gộp, MRR gộp, rrf_recall@5 gộp, pool_recall gộp,
       rồi ưu tiên gần mốc (|alpha-0.5| rồi |k-60|);
    4. cao nguyên: láng giềng (alpha±0.1 cùng k, k liền kề cùng alpha) kém
       không quá 1 câu ở recall@5 gộp; không qua thì xét cấu hình kế tiếp;
    5. chỉ đổi production khi hơn mốc ≥ 2 câu ở recall@5 gộp, HOẶC bằng
       recall@5 gộp nhưng MRR gộp cao hơn ≥ 0.02, VÀ không làm trượt câu nào
       mà mốc đang trúng ở recall@5.
    """
    rws = [_row_from_dict(r) for r in rows]
    base = _row_from_dict(baseline)
    n = base.raw.get("combined_n", COMBINED_N)

    cands = [r for r in rws if r.tune_recall5 >= 0.85 and r.holdout_recall5 >= base.holdout_recall5]
    if not cands:
        return Decision(base.raw, False, "không cấu hình nào qua cổng gate/bộ giữ lại")

    def _rank_key(r: _Row):
        return (
            -r.combined_recall5,
            -r.combined_mrr,
            -r.combined_rrf_recall5,
            -r.combined_pool_recall,
            abs(r.alpha - BASELINE_ALPHA),
            abs(r.k - BASELINE_K),
        )

    ordered = sorted(cands, key=_rank_key)
    by_key = {(r.alpha, r.k): r for r in cands}

    def _lost_questions(winner: _Row, neigh: _Row) -> float:
        """Số câu recall@5 gộp mà láng giềng kém cấu hình thắng."""
        return round((winner.combined_recall5 - neigh.combined_recall5) * n)

    def _neighbours(r: _Row) -> list[_Row]:
        found: list[_Row] = []
        for da in (-0.1, 0.1):
            a = round(r.alpha + da, 1)
            if 0.0 <= a <= 1.0 and (a, r.k) in by_key:
                found.append(by_key[(a, r.k)])
        ks = sorted({row.k for row in cands})
        i = ks.index(r.k)
        for j in (i - 1, i + 1):
            if 0 <= j < len(ks) and (r.alpha, ks[j]) in by_key:
                found.append(by_key[(r.alpha, ks[j])])
        return found

    challenger: _Row | None = None
    for r in ordered:
        if r.alpha == BASELINE_ALPHA and r.k == BASELINE_K:
            return Decision(r.raw, False, "mốc alpha=0.5, k=60 đứng đầu theo xếp hạng")
        if all(_lost_questions(r, neigh) <= 1 for neigh in _neighbours(r)):
            challenger = r
            break
    if challenger is None:
        return Decision(base.raw, False, "mọi ứng viên đều trượt kiểm tra cao nguyên")

    recall_gain = challenger.combined_recall5 - base.combined_recall5
    mrr_gain = challenger.combined_mrr - base.combined_mrr
    regressed = challenger.misses - base.misses

    if recall_gain > 0:
        if round(recall_gain * n) >= 2 and not regressed:
            return Decision(
                challenger.raw,
                True,
                f"recall@5 gộp hơn mốc {round(recall_gain * n)} câu (≥2), không câu nào trượt",
            )
        if regressed:
            return Decision(base.raw, False, "ứng viên làm trượt câu mốc đang trúng rec@5")
        return Decision(
            base.raw,
            False,
            f"recall@5 gộp chỉ hơn mốc {round(recall_gain * n)} câu (<2, dưới ngưỡng đổi production)",
        )
    if recall_gain == 0.0 and mrr_gain >= 0.02 - 1e-9 and not regressed:
        return Decision(
            challenger.raw,
            True,
            f"bằng recall@5 gộp nhưng MRR gộp hơn {mrr_gain:.3f} (≥0.02), không câu nào trượt",
        )
    if regressed:
        return Decision(base.raw, False, "ứng viên làm trượt câu mốc đang trúng rec@5")
    return Decision(base.raw, False, "ứng viên không hơn mốc đủ ngưỡng đổi production")


# ── cache I/O theo cấp thuộc tính module (chống drift) ────────────────────────


class RerankDocCache:
    """Cache điểm cross-encoder theo TỪNG cặp (query, document).

    Chỉ gửi service các document CHƯA có trong cache, MỘT lời gọi cho cả nhóm
    thiếu. Điểm trả về theo đúng thứ tự ``documents``.
    """

    def __init__(self, real_score_fn):
        self._real = real_score_fn
        self._cache: dict[tuple[str, str], float] = {}
        self.service_calls = 0
        self.docs_sent = 0

    def __call__(self, query: str, documents: list[str]) -> list[float]:
        missing = [d for d in documents if (query, d) not in self._cache]
        # Giữ thứ tự, bỏ trùng trong cùng một lô.
        seen: set[str] = set()
        unique_missing = []
        for d in missing:
            if d not in seen:
                seen.add(d)
                unique_missing.append(d)
        if unique_missing:
            scores = self._real(query, unique_missing)
            self.service_calls += 1
            self.docs_sent += len(unique_missing)
            for d, s in zip(unique_missing, scores, strict=True):
                self._cache[(query, d)] = s
        return [self._cache[(query, d)] for d in documents]


@contextmanager
def cached_io():
    """Thay các hàm I/O của phễu production bằng bản cache, khôi phục khi thoát.

    Bảng thay thế (mục 3b của plan):
      - embedding.embedder.embed_query          → cache theo chuỗi truy vấn
      - retrieval.hybrid_retriever.search_both  → cache theo (expanded_query, top_k, file_stem)
      - vectorstore.qdrant.fetch_parent         → cache theo parent_id
      - reranking.reranker.score_documents      → cache theo từng cặp (query, document)
      - reranking.reranker.rerank_hits          → ghi lại hits đầu vào (pool sau RRF) rồi gọi bản gốc

    ``retrieval.retriever`` gọi các hàm qua module nên patch cấp module là đủ.
    """
    from embedding import embedder
    from reranking import reranker
    from retrieval import hybrid_retriever
    from vectorstore import qdrant

    embed_cache: dict[str, list[float]] = {}
    search_cache: dict[tuple, tuple] = {}
    parent_cache: dict[str, dict | None] = {}
    recorded_hits: dict[int, list[dict]] = {}
    counters = {"rerank_hits": 0}

    real_embed = embedder.embed_query
    real_search = hybrid_retriever.search_both
    real_fetch = qdrant.fetch_parent
    real_rerank_hits = reranker.rerank_hits
    real_score = reranker.score_documents

    def cached_embed(query: str):
        if query not in embed_cache:
            embed_cache[query] = real_embed(query)
        return embed_cache[query]

    def cached_search(vec, expanded_query: str, *, top_k: int, file_stem=None):
        key = (expanded_query, top_k, file_stem)
        if key not in search_cache:
            search_cache[key] = real_search(vec, expanded_query, top_k=top_k, file_stem=file_stem)
        return search_cache[key]

    def cached_fetch(parent_id):
        if parent_id not in parent_cache:
            parent_cache[parent_id] = real_fetch(parent_id)
        return parent_cache[parent_id]

    score_cache = RerankDocCache(real_score)

    def recording_rerank_hits(query: str, hits: list[dict], top_n=None):
        recorded_hits[id(hits)] = list(hits)
        counters["rerank_hits"] += 1
        return real_rerank_hits(query, hits, top_n=top_n)

    embedder.embed_query = cached_embed
    hybrid_retriever.search_both = cached_search
    qdrant.fetch_parent = cached_fetch
    reranker.score_documents = score_cache
    reranker.rerank_hits = recording_rerank_hits
    try:
        yield {
            "recorded_hits": recorded_hits,
            "counters": counters,
            "score_cache": score_cache,
        }
    finally:
        embedder.embed_query = real_embed
        hybrid_retriever.search_both = real_search
        qdrant.fetch_parent = real_fetch
        reranker.score_documents = real_score
        reranker.rerank_hits = real_rerank_hits


# ── số đo trước rerank ───────────────────────────────────────────────────────


def dedupe_pool_by_parent(hits: list[dict]) -> list[dict]:
    """Dedupe pool theo parent_id, GIỮ thứ tự RRF (hit đầu tiên của mỗi mục)."""
    seen: set = set()
    out: list[dict] = []
    for h in hits:
        pid = h["payload"].get("parent_id")
        if pid not in seen:
            seen.add(pid)
            out.append(h)
    return out


# ── chạy một cấu hình ────────────────────────────────────────────────────────


def load_items(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def run_config(alpha: float, k: int, items: list[dict], io) -> dict:
    """Chạy phễu production cho mọi câu hỏi dưới một cấu hình RRF."""
    from evaluation.pipeline import production_retrieve

    ranks: list[int | None] = []
    pool_recalls: list[int] = []
    rrf_ranks: list[int | None] = []
    miss_ids: list = []
    recorded = io["recorded_hits"]
    recorded.clear()

    for item in items:
        q = item["question"]
        expected = item["expected"]
        results = production_retrieve(q, top_n=10)
        rank = hit_rank(results, expected)
        ranks.append(rank)

        # hits ghi lại ở lần rerank CUỐI (khớp với kết quả trả về).
        hits = None
        if recorded:
            hits = recorded[max(recorded)]
        if hits is not None:
            pool_recalls.append(1 if hit_rank(hits, expected) is not None else 0)
            rrf_ranks.append(hit_rank(dedupe_pool_by_parent(hits)[:5], expected))
        else:
            pool_recalls.append(0)
            rrf_ranks.append(None)

        qid = item.get("id", f"ext-{len(ranks)}")
        if rank is None or rank > 5:
            miss_ids.append(qid)
    return {
        "ranks": ranks,
        "pool_recall": sum(pool_recalls) / len(pool_recalls) if pool_recalls else 0.0,
        "rrf_ranks": rrf_ranks,
        "miss_ids": miss_ids,
    }


def _metrics(ranks: list[int | None]) -> dict:
    return compute_metrics(ranks, [1, 3, 5, 10])


def run_grid(
    alphas: list[float], ks: list[int], tune: list[dict], holdout: list[dict]
) -> list[dict]:
    """Chạy toàn lưới, trả một dict số đo cho mỗi cấu hình."""
    rows: list[dict] = []
    total = len(alphas) * len(ks)
    idx = 0
    for k in ks:
        for alpha in alphas:
            idx += 1
            print(f"[{idx:02d}/{total}] alpha={alpha} k={k} …", flush=True)
            t0 = time.time()
            with overridden(
                {
                    "retrieval.rrf_weight_dense": alpha,
                    "retrieval.rrf_weight_bm25": round(1.0 - alpha, 10),
                    "retrieval.rrf_k": k,
                }
            ):
                with cached_io() as io:
                    tune_r = run_config(alpha, k, tune, io)
                    hold_r = run_config(alpha, k, holdout, io)
                    calls = io["counters"]["rerank_hits"]
                    svc_calls = io["score_cache"].service_calls
                    docs_sent = io["score_cache"].docs_sent
            combined_ranks = tune_r["ranks"] + hold_r["ranks"]
            combined_rrf = tune_r["rrf_ranks"] + hold_r["rrf_ranks"]
            tm = _metrics(tune_r["ranks"])
            hm = _metrics(hold_r["ranks"])
            cm = _metrics(combined_ranks)
            cm_rrf = _metrics(combined_rrf)
            pool = (tune_r["pool_recall"] * len(tune) + hold_r["pool_recall"] * len(holdout)) / (
                len(tune) + len(holdout)
            )
            row = {
                "alpha": alpha,
                "k": k,
                "tune_recall@1": tm["recall@1"],
                "tune_recall@3": tm["recall@3"],
                "tune_recall@5": tm["recall@5"],
                "tune_recall@10": tm["recall@10"],
                "tune_MRR": tm["MRR"],
                "tune_ndcg@5": tm["ndcg@5"],
                "holdout_recall@1": hm["recall@1"],
                "holdout_recall@3": hm["recall@3"],
                "holdout_recall@5": hm["recall@5"],
                "holdout_recall@10": hm["recall@10"],
                "holdout_MRR": hm["MRR"],
                "holdout_ndcg@5": hm["ndcg@5"],
                "combined_recall@1": cm["recall@1"],
                "combined_recall@3": cm["recall@3"],
                "combined_recall@5": cm["recall@5"],
                "combined_recall@10": cm["recall@10"],
                "combined_MRR": cm["MRR"],
                "combined_ndcg@5": cm["ndcg@5"],
                "combined_rrf_recall@5": cm_rrf["recall@5"],
                "combined_pool_recall": pool,
                "combined_n": len(combined_ranks),
                "combined_miss_ids": tune_r["miss_ids"] + hold_r["miss_ids"],
                "rerank_hits_calls": calls,
                "service_score_calls": svc_calls,
                "docs_sent": docs_sent,
                "seconds": round(time.time() - t0, 2),
            }
            rows.append(row)
            print(
                f"    recall@5 gộp={cm['recall@5']:.3f} MRR={cm['MRR']:.3f} "
                f"({row['seconds']}s; rerank_hits={calls}, score_calls={svc_calls})",
                flush=True,
            )
    return rows


# ── đầu ra ───────────────────────────────────────────────────────────────────


def write_outputs(out_dir: Path, rows: list[dict], decision: Decision) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    import csv

    with (out_dir / "results.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    ordered = sorted(
        rows,
        key=lambda r: (
            -r["combined_recall@5"],
            -r["combined_MRR"],
            -r["combined_rrf_recall@5"],
            -r["combined_pool_recall"],
            abs(r["alpha"] - BASELINE_ALPHA),
            abs(r["k"] - BASELINE_K),
        ),
    )

    lines = ["# Kết quả quét lưới RRF có trọng số", "", "## Top 10 cấu hình", ""]
    lines.append("| # | alpha | k | recall@5 gộp | MRR gộp | rrf_recall@5 | pool_recall |")
    lines.append("|---|-------|---|--------------|---------|--------------|-------------|")
    for i, r in enumerate(ordered[:TOP_CONFIGS], 1):
        lines.append(
            f"| {i} | {r['alpha']:.1f} | {r['k']} | {r['combined_recall@5']:.3f} | "
            f"{r['combined_MRR']:.3f} | {r['combined_rrf_recall@5']:.3f} | "
            f"{r['combined_pool_recall']:.3f} |"
        )

    for label, col in (("recall@5 gộp", "combined_recall@5"), ("MRR gộp", "combined_MRR")):
        lines += ["", f"## Lưới alpha x k - {label}", ""]
        header = "| alpha \\\\ k | " + " | ".join(str(k) for k in DEFAULT_KS) + " |"
        lines.append(header)
        lines.append("|" + "---|" * (len(DEFAULT_KS) + 1))
        by = {(r["alpha"], r["k"]): r for r in rows}
        for a in sorted({r["alpha"] for r in rows}):
            cells = []
            for k in DEFAULT_KS:
                r = by.get((a, k))
                cells.append(f"{r[col]:.3f}" if r else "-")
            lines.append(f"| {a:.1f} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## Quyết định",
        "",
        f"- Cấu hình thắng: alpha={decision.winner['alpha']}, k={decision.winner['k']}",
        f"- Đổi production: {'CÓ' if decision.change else 'KHÔNG'}",
        f"- Lý do: {decision.reason}",
    ]
    (out_dir / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    with (out_dir / "per_question.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(
                json.dumps(
                    {
                        "alpha": r["alpha"],
                        "k": r["k"],
                        "miss_ids": r["combined_miss_ids"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


# ── main ─────────────────────────────────────────────────────────────────────


def _parse_list(raw: str, cast) -> list:
    return [cast(x) for x in raw.split(",") if x.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Quét lưới trọng số RRF dense/BM25")
    parser.add_argument("--alphas", default=",".join(str(a) for a in DEFAULT_ALPHAS))
    parser.add_argument("--ks", default=",".join(str(k) for k in DEFAULT_KS))
    parser.add_argument("--tune-file", default="evaluation/eval_set.jsonl")
    parser.add_argument("--holdout-file", default="evaluation/eval_set_ext.jsonl")
    parser.add_argument("--out-dir", default="logs/fusion_sweep")
    args = parser.parse_args(argv)

    alphas = _parse_list(args.alphas, float)
    ks = _parse_list(args.ks, int)
    tune = load_items(Path(args.tune_file))
    holdout = load_items(Path(args.holdout_file))
    print(f"Bộ tinh chỉnh: {len(tune)} câu; bộ giữ lại: {len(holdout)} câu\n")

    rows = run_grid(alphas, ks, tune, holdout)
    baseline = next(
        (r for r in rows if r["alpha"] == BASELINE_ALPHA and r["k"] == BASELINE_K), None
    )
    if baseline is None:
        print("LỖI: lưới không chứa mốc alpha=0.5, k=60", file=sys.stderr)
        return 1

    decision = pick_winner(rows, baseline)
    out_dir = Path(args.out_dir)
    write_outputs(out_dir, rows, decision)
    print(f"\nCấu hình thắng: alpha={decision.winner['alpha']}, k={decision.winner['k']}")
    print(f"Đổi production: {'CÓ' if decision.change else 'KHÔNG'} - {decision.reason}")
    print(f"Đã ghi {out_dir}/results.csv, results.md, per_question.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
