"""Cổng eval §6 Tiến hành kiểm định (spec §9 Sprint 5, §11).

Mục tiêu cổng: precision ≥ 0,90 trên tập vàng §6 và **tỷ lệ bịa số bằng 0** trên
toàn bộ tập kiểm. Vì CI không có GPU/Ollama, mặc định eval chạy một **client
kịch bản** (``ScriptedClient``) dựng từ tập vàng, có chủ đích chèn các dòng bịa
số để chứng minh bộ xác minh loại chúng. Độ chính xác của model thật đo bằng
``--live`` khi có Ollama.

Usage:
  python -m eval.extract_section6_eval [--golden PATH] [--md-dir PATH] [--live] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from knowledge import llm_extract, vnnum

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GOLDEN = ROOT / "eval" / "extract_golden_section6.jsonl"
DEFAULT_MD_DIR = ROOT / "build" / "spike_a"


class ScriptedClient:
    """Client giả lập LLM: trả payload dựng sẵn cho một mục.

    Dùng để kiểm chứng hàng rào xác minh + chấm điểm một cách tất định, không cần
    model. ``model_name`` ghi vào ``extractor`` để giữ xuất xứ.
    """

    def __init__(self, payload: dict, model_name: str = "scripted") -> None:
        self.payload = payload
        self.model_name = model_name
        self.calls = 0

    def chat(self, prompt: str, system: str | None = None) -> str:
        self.calls += 1
        return json.dumps(self.payload, ensure_ascii=False)


def load_golden(path: Path = DEFAULT_GOLDEN) -> list[dict]:
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def golden_key(item: dict) -> tuple[str, str, str]:
    """Khóa định danh dòng vàng §6: (doc, fact_kind, quote đã chuẩn hóa)."""
    return (
        item["doc"],
        item["fact_kind"],
        vnnum.normalize_spaces(item["quote"]).lower(),
    )


def _fact_from_golden(item: dict) -> dict:
    """Dựng payload dữ kiện (như LLM trả) từ một dòng vàng."""
    fact = {"fact_kind": item["fact_kind"], "quote": item["quote"]}
    for key in ("label", "rel_op", "value_text", "condition_text", "formula"):
        if item.get(key) is not None:
            fact[key] = item[key]
    for key in ("limit", "floor"):
        if item.get(key) is not None:
            fact[key] = dict(item[key])
    return fact


def build_scripted_payload(items: list[dict], *, inject_hallucinations: bool = True) -> dict:
    """Payload cho một tài liệu: dữ kiện vàng + (tùy chọn) hai dòng bịa số.

    Hai kiểu bịa được chèn để chứng minh hàng rào: quote không tồn tại trong
    nguồn, và quote có thật nhưng gán sai con số.
    """
    facts = [_fact_from_golden(item) for item in items]
    if inject_hallucinations and items:
        facts.append(
            {
                "fact_kind": "max_permissible_error",
                "label": "Bịa — quote không có trong tài liệu",
                "rel_op": "<=",
                "limit": {
                    "value": 42.0,
                    "unit": "%",
                    "quote": "không được vượt quá 42 % giới hạn bịa đặt",
                },
                "quote": "Câu này hoàn toàn không xuất hiện trong tài liệu nguồn.",
            }
        )
        real = items[0]
        if real.get("limit"):
            facts.append(
                {
                    "fact_kind": "max_permissible_error",
                    "label": "Bịa — quote thật nhưng sai con số",
                    "rel_op": real.get("rel_op") or "=",
                    "limit": {
                        "value": float(real["limit"]["value"]) + 1000,
                        "unit": real["limit"].get("unit"),
                        "quote": real["limit"]["quote"],
                    },
                    "quote": real["quote"],
                }
            )
    return {"facts": facts}


def evaluate(
    md_dir: Path = DEFAULT_MD_DIR,
    golden_path: Path = DEFAULT_GOLDEN,
    *,
    live: bool = False,
    client_factory=None,
) -> dict:
    """Chạy trích xuất §6 và đối chiếu tập vàng; trả báo cáo precision/recall."""
    golden = load_golden(golden_path)
    by_doc: dict[str, list[dict]] = {}
    for item in golden:
        by_doc.setdefault(item["doc"], []).append(item)

    golden_keys = {golden_key(item) for item in golden}
    accepted_keys: set[tuple[str, str, str]] = set()
    hallucinations = 0
    unverified_accepted = 0
    per_doc: dict[str, dict] = {}

    for doc, items in sorted(by_doc.items()):
        md_path = md_dir / f"{doc}.md"
        if not md_path.exists():
            continue
        text = md_path.read_text(encoding="utf-8")
        if client_factory is not None:
            client = client_factory(doc, items)
        elif live:
            client = llm_extract.default_client()
        else:
            client = ScriptedClient(build_scripted_payload(items))

        result = llm_extract.extract_section6(text, client)
        hallucinations += llm_extract.numeric_hallucinations(result, text)
        for verified in result.facts:
            unverified_accepted += 0 if llm_extract.verify_fact(verified.fact, text).ok else 1
            accepted_keys.add(
                (doc, verified.fact.fact_kind, vnnum.normalize_spaces(verified.fact.quote).lower())
            )
        per_doc[doc] = {
            "accepted": len(result.facts),
            "rejected": len(result.rejected),
            "error": result.error,
        }

    categories = {}
    for kind in ("max_permissible_error", "formula"):
        gold = {key for key in golden_keys if key[1] == kind}
        pred = {key for key in accepted_keys if key[1] == kind}
        tp = len(gold & pred)
        categories[kind] = {
            "golden": len(gold),
            "predicted": len(pred),
            "true_positive": tp,
            "false_positive": len(pred - gold),
            "false_negative": len(gold - pred),
            "precision": tp / len(pred) if pred else 1.0,
            "recall": tp / len(gold) if gold else 1.0,
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
        "numeric_hallucinations": hallucinations,
        "unverified_accepted": unverified_accepted,
        "per_doc": per_doc,
        "live": live,
    }


def gate(report: dict, min_precision: float = 0.90) -> tuple[bool, list[str]]:
    """Cổng: precision ≥ ngưỡng, 0 bịa số, mọi dòng chấp nhận đều đã xác minh."""
    failures: list[str] = []
    for category, metrics in report["categories"].items():
        if metrics["golden"] == 0:
            continue
        if metrics["precision"] < min_precision:
            failures.append(
                f"{category}: precision {metrics['precision']:.3f} < {min_precision:.2f}"
            )
    if report["numeric_hallucinations"] != 0:
        failures.append(f"bịa số: {report['numeric_hallucinations']} > 0")
    if report["unverified_accepted"] != 0:
        failures.append(f"dòng chấp nhận chưa xác minh: {report['unverified_accepted']} > 0")
    return (not failures, failures)


def _print_report(report: dict, min_precision: float) -> None:
    mode = "Ollama thật" if report["live"] else "client kịch bản"
    print(f"Trích xuất §6 bằng LLM ({mode}) — precision/recall theo loại dữ kiện")
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
    print(f"Bịa số lọt qua: {report['numeric_hallucinations']}")
    ok, failures = gate(report, min_precision)
    print(f"\nCổng: precision ≥ {min_precision:.2f}, bịa số = 0 → {'ĐẠT' if ok else 'HỎNG'}")
    for failure in failures:
        print(f"  - {failure}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval trích xuất §6 bằng LLM")
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--md-dir", type=Path, default=DEFAULT_MD_DIR)
    parser.add_argument("--min-precision", type=float, default=0.90)
    parser.add_argument(
        "--live", action="store_true", help="Dùng Ollama thật thay vì client kịch bản"
    )
    parser.add_argument("--json", action="store_true", help="In báo cáo dạng JSON")
    args = parser.parse_args(argv)

    report = evaluate(args.md_dir, args.golden, live=args.live)
    ok, _ = gate(report, args.min_precision)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report, args.min_precision)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
