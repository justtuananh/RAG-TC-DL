"""Đo recall truy hồi trên một tệp câu hỏi có nguồn chuẩn (chỉ dùng bộ DEV).

Chạy TRONG container (cần Qdrant/embedding/reranker):
    docker exec -i qtkd-api-stg python - --gold /tmp/dev_gold.json --out /tmp/r.json < scripts/retrieval_eval.py

Tệp gold: danh sách {id, group, type, question, sources:[{file, section}]}.
Một nguồn gold khớp khi có hit cùng file_stem và đường dẫn mục có một thành phần (tách theo '>')
bằng số mục hoặc bắt đầu bằng "<mục> " / "<mục>." (cùng quy tắc secmatch của bộ chấm).
Câu multi_version cần khớp TẤT CẢ nguồn gold; các dạng khác chỉ cần một.

Ba mức đo: ``topn`` (hit trong kết quả retrieve()), ``shown`` (sau filter_by_confidence =
nguồn người dùng thấy) và ``loose`` (chẩn đoán: mục cha của hit CÓ dòng tiêu đề đánh số của
mục gold, dù mục con không tách chunk riêng). Thời gian mỗi retrieve() báo mean/p50/p95.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from collections import defaultdict


def secmatch(section_path: str | None, want: str) -> bool:
    parts = [p.strip() for p in (section_path or "").split(">")]
    return any(p == want or p.startswith(want + " ") or p.startswith(want + ".") for p in parts)


def hit_path(h: dict) -> str:
    """Đường dẫn mục người dùng thấy: ưu tiên mục con đã định vị (cited_section_path)."""
    return h.get("cited_section_path") or h["payload"].get("section_path") or ""


def contains_section(h: dict, want: str) -> bool:
    """Chẩn đoán: mục cha của hit có dòng tiêu đề đánh số ``want``."""
    text = (h.get("parent_payload") or h["payload"]).get("text", "")
    return re.search(r"(?m)^[#\s]*" + re.escape(want) + r"(?!\d)[.\s]", text) is not None


def _one(e: dict, hits: list[dict], loose: bool) -> bool:
    return any(
        h["payload"]["file_stem"] == e["file"]
        and (secmatch(hit_path(h), e["section"]) or (loose and contains_section(h, e["section"])))
        for h in hits
    )


def gold_hit(question: dict, hits: list[dict], loose: bool = False) -> bool:
    exp = question.get("sources") or []
    if not exp:
        return False
    results = [_one(e, hits, loose) for e in exp]
    return all(results) if question["type"] == "multi_version" else any(results)


def first_rank(question: dict, hits: list[dict]) -> int | None:
    exp = question.get("sources") or []
    for i, h in enumerate(hits, 1):
        if any(_one(e, [h], False) for e in exp):
            return i
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--warmup", type=int, default=2)
    args = ap.parse_args()

    from retrieval import retriever
    from retrieval.context_builder import filter_by_confidence

    import logging

    class _Count(logging.Handler):
        """Đếm lần reranker lỗi (rơi về thứ tự RRF) - số đo lúc đó không đại diện nên thử lại."""

        n = 0
        last = ""

        def emit(self, record):
            if "Reranker failed" in record.getMessage():
                _Count.n += 1
                _Count.last = record.getMessage()[:200]

    logging.getLogger("reranking.reranker").addHandler(_Count())

    from reranking import reranker as _rr

    calls = {"n": 0, "pairs": 0, "fail": 0}
    _orig_post = _rr._post_scores

    def _counting_post(query, documents):
        calls["n"] += 1
        calls["pairs"] += len(documents)
        try:
            return _orig_post(query, documents)
        except Exception:
            calls["fail"] += 1
            raise

    _rr._post_scores = _counting_post

    def timed_retrieve(question: str):
        for attempt in range(4):
            before = _Count.n
            t0 = time.perf_counter()
            hits = retriever.retrieve(question)
            dt = time.perf_counter() - t0
            if _Count.n == before:
                return hits, dt, attempt
            time.sleep(3)
        return hits, dt, attempt

    qs = json.load(open(args.gold, encoding="utf-8"))
    for q in qs[: args.warmup]:
        retriever.retrieve(q["question"])

    rows = []
    for q in qs:
        time.sleep(0.3)  # nghỉ ngắn giữa các câu: reranker dùng chung GPU
        hits, dt, retries = timed_retrieve(q["question"])
        shown = filter_by_confidence(hits)
        rows.append(
            {
                "id": q["id"],
                "group": q["group"],
                "type": q["type"],
                "hit_topn": gold_hit(q, hits),
                "hit_shown": gold_hit(q, shown),
                "hit_loose": gold_hit(q, hits, loose=True),
                "rank": first_rank(q, hits),
                "n_hits": len(hits),
                "seconds": round(dt, 3),
                "rerank_retries": retries,
                "top": [
                    f"{h['payload']['file_stem'][:18]}|{hit_path(h)[-60:]}|{h.get('rerank_score', 0):.3f}"
                    for h in hits[:6]
                ],
                "gold": q["sources"],
            }
        )

    def rate(sel, key):
        sel = list(sel)
        n = sum(r[key] for r in sel)
        return f"{n}/{len(sel)}={n / max(len(sel), 1):.3f}"

    print(
        "TOTAL  topn:", rate(rows, "hit_topn"), " shown:", rate(rows, "hit_shown"),
        " loose:", rate(rows, "hit_loose"),
    )
    for field in ("type", "group"):
        groups = defaultdict(list)
        for r in rows:
            groups[r[field]].append(r)
        for k in sorted(groups):
            print(
                f"  {field}={k:14s} topn {rate(groups[k], 'hit_topn')}  "
                f"shown {rate(groups[k], 'hit_shown')}  loose {rate(groups[k], 'hit_loose')}"
            )
    print(f"RERANK fallbacks seen: {_Count.n} (last: {_Count.last!r}); questions still on fallback: "
          f"{sum(r['rerank_retries'] >= 3 for r in rows)}")
    print(f"RERANK HTTP calls: {calls['n']} ({calls['pairs']} pairs, {calls['fail']} failed->split)")
    ts = sorted(r["seconds"] for r in rows)
    p95 = ts[min(len(ts) - 1, int(0.95 * len(ts)))]
    print(
        f"TIME retrieve(): mean {statistics.mean(ts):.3f}s  p50 {statistics.median(ts):.3f}s  "
        f"p95 {p95:.3f}s  max {ts[-1]:.3f}s"
    )
    for r in rows:
        if not r["hit_topn"]:
            tag = "(loose-ok)" if r["hit_loose"] else "(true-miss)"
            print(f"MISS{tag} {r['id']} ({r['type']},{r['group']}) gold={r['gold']}")
            for t in r["top"]:
                print("     ", t)
    if args.out:
        json.dump(rows, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
