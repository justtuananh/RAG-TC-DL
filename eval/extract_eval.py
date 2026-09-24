"""Eval trích xuất bằng luật trên tập vàng gán tay (spec §9 Sprint 4, §11).

Chạy ``knowledge.rules`` trên toàn bộ QTKĐ trong ``build/spike_a/`` và đối chiếu
với ``eval/extract_golden.jsonl`` — tập vàng đọc tay từ corpus hiện có. Tính độ
chính xác và độ phủ RIÊNG TỪNG loại dữ kiện (spec: precision ≥ 0,95, recall ≥
0,80; ưu tiên precision vì có người duyệt ở sau).

Usage:
  python -m eval.extract_eval [--golden PATH] [--md-dir PATH] [--json]

Không cần DB, không cần service — chỉ đọc Markdown + luật thuần hàm.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from knowledge import vnnum
from knowledge.rules import extract_all

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GOLDEN = ROOT / "eval" / "extract_golden.jsonl"
DEFAULT_MD_DIR = ROOT / "build" / "spike_a"

CATEGORIES = (
    "working_range",
    "calibration_interval",
    "env_condition",
    "inspection_step",
    "standard",
    "term",
)


def _norm(text: str | None) -> str:
    return vnnum.normalize_spaces(text or "").lower()


def golden_key(doc: str, item: dict) -> tuple[str, str, str]:
    """Khóa định danh một dòng vàng: (doc, loại, chuỗi nhận dạng)."""
    kind = item["kind"]
    if kind == "term":
        return (doc, "term", _norm(item.get("term_vi")))
    if kind == "standard":
        return (
            doc,
            "standard",
            f"{_norm(item.get('name_vi'))}|{_norm(item.get('range_text'))}",
        )
    fact_kind = item["fact_kind"]
    if fact_kind == "inspection_step":
        return (doc, fact_kind, _norm(item.get("label")))
    if fact_kind == "env_condition":
        return (
            doc,
            fact_kind,
            f"{_norm(item.get('label'))}|{_norm(item.get('value_text'))}",
        )
    return (doc, fact_kind, _norm(item.get("value_text")))


def hit_key(doc: str, hit) -> tuple[str, str, str]:
    """Khóa định danh một ``RuleHit`` theo cùng quy ước với tập vàng."""
    if hit.kind == "term":
        return (doc, "term", _norm(hit.term_vi))
    if hit.kind == "standard":
        return (
            doc,
            "standard",
            f"{_norm(hit.name_vi)}|{_norm(hit.range_text)}",
        )
    if hit.fact_kind == "inspection_step":
        return (doc, "inspection_step", _norm(hit.label))
    if hit.fact_kind == "env_condition":
        return (
            doc,
            "env_condition",
            f"{_norm(hit.label)}|{_norm(hit.value_text)}",
        )
    return (doc, hit.fact_kind or "", _norm(hit.value_text))


def load_golden(path: Path) -> list[dict]:
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def evaluate(
    md_dir: Path = DEFAULT_MD_DIR,
    golden_path: Path = DEFAULT_GOLDEN,
) -> dict:
    """Trả báo cáo precision/recall theo từng loại dữ kiện."""
    golden = load_golden(golden_path)
    golden_keys = {golden_key(item["doc"], item) for item in golden}

    predicted_keys: set[tuple[str, str, str]] = set()
    for md_path in sorted(md_dir.glob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        for hit in extract_all(text):
            predicted_keys.add(hit_key(md_path.stem, hit))

    categories: dict[str, dict] = {}
    for category in CATEGORIES:
        gold = {key for key in golden_keys if key[1] == category}
        pred = {key for key in predicted_keys if key[1] == category}
        true_positive = len(gold & pred)
        precision = true_positive / len(pred) if pred else 1.0
        recall = true_positive / len(gold) if gold else 1.0
        categories[category] = {
            "golden": len(gold),
            "predicted": len(pred),
            "true_positive": true_positive,
            "false_positive": len(pred - gold),
            "false_negative": len(gold - pred),
            "precision": precision,
            "recall": recall,
            "missing": sorted(key[2] for key in (gold - pred)),
            "extra": sorted(key[2] for key in (pred - gold)),
        }

    total_tp = sum(item["true_positive"] for item in categories.values())
    total_pred = sum(item["predicted"] for item in categories.values())
    total_gold = sum(item["golden"] for item in categories.values())
    return {
        "categories": categories,
        "micro_precision": total_tp / total_pred if total_pred else 1.0,
        "micro_recall": total_tp / total_gold if total_gold else 1.0,
        "golden_total": total_gold,
        "predicted_total": total_pred,
    }


def gate(report: dict, min_precision: float, min_recall: float) -> tuple[bool, list[str]]:
    """Kiểm cổng theo từng loại; trả (đạt?, danh sách lý do hỏng)."""
    failures: list[str] = []
    for category, metrics in report["categories"].items():
        if metrics["golden"] == 0:
            continue
        if metrics["precision"] < min_precision:
            failures.append(
                f"{category}: precision {metrics['precision']:.3f} < {min_precision:.2f}"
            )
        if metrics["recall"] < min_recall:
            failures.append(f"{category}: recall {metrics['recall']:.3f} < {min_recall:.2f}")
    return (not failures, failures)


def _print_report(report: dict, min_precision: float, min_recall: float) -> None:
    print("Trích xuất bằng luật — precision/recall theo loại dữ kiện")
    print(f"{'loại':<22}{'vàng':>6}{'đoán':>6}{'TP':>5}{'FP':>5}{'FN':>5}{'P':>8}{'R':>8}")
    for category, metrics in report["categories"].items():
        print(
            f"{category:<22}{metrics['golden']:>6}{metrics['predicted']:>6}"
            f"{metrics['true_positive']:>5}{metrics['false_positive']:>5}"
            f"{metrics['false_negative']:>5}{metrics['precision']:>8.3f}"
            f"{metrics['recall']:>8.3f}"
        )
    print(
        f"{'TỔNG (micro)':<22}{report['golden_total']:>6}{report['predicted_total']:>6}"
        f"{'':>15}{report['micro_precision']:>8.3f}{report['micro_recall']:>8.3f}"
    )
    ok, failures = gate(report, min_precision, min_recall)
    print(
        f"\nCổng: precision ≥ {min_precision:.2f}, recall ≥ {min_recall:.2f} → "
        f"{'ĐẠT' if ok else 'HỎNG'}"
    )
    for failure in failures:
        print(f"  - {failure}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval trích xuất QTKĐ bằng luật")
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--md-dir", type=Path, default=DEFAULT_MD_DIR)
    parser.add_argument("--min-precision", type=float, default=0.95)
    parser.add_argument("--min-recall", type=float, default=0.80)
    parser.add_argument("--json", action="store_true", help="In báo cáo dạng JSON")
    args = parser.parse_args(argv)

    report = evaluate(args.md_dir, args.golden)
    ok, _ = gate(report, args.min_precision, args.min_recall)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report, args.min_precision, args.min_recall)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
