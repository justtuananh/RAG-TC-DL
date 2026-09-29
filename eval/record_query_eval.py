"""Eval tra cứu biên bản có cấu trúc trên sổ cái thật (Pha R).

Mỗi câu trong ``eval/record_query_set.jsonl`` đi ĐÚNG đường của ``/api/chat/stream``:
bộ phân loại Ollama → ``decide`` → ``build_data_payload`` trên PostgreSQL. Một câu
đạt khi intent đúng VÀ mọi giá trị trong ``must`` (nguyên văn biên bản, so sau khi
bỏ khoảng trắng) có mặt trong bảng trả về. ``must_not`` là giá trị KHÔNG được xuất
hiện (câu lọc theo người / đơn vị mà trả cả sổ cái thì trượt, dù đủ ``must``).
``not_intents`` là intent câu hỏi KHÔNG được rơi vào (câu hỏi quy định không bị kéo
sang tra biên bản). ``intents`` (tuỳ chọn) liệt kê mọi intent trả lời đúng câu hỏi khi
có hơn một cách.

Bộ ``bo20`` là 20 câu hỏi trích xuất số liệu áp kế pít tông (``Bo_20_cau.xlsx``);
bộ ``paraphrase`` là câu hỏi diễn đạt khác để chống khớp riêng bộ câu gốc; bộ ``gen``
(``record_query_generated.jsonl``) do một LLM khác sinh, đáp án lấy nguyên văn sổ cái. Cần
Postgres (20 biên bản trong ``TC_DL/`` đã nạp + duyệt) và Ollama.

Usage:
  OLLAMA_MODEL=qwen2.5:3b python -m eval.record_query_eval [--set bo20] [-v]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

DEFAULT_SET = Path(__file__).with_name("record_query_set.jsonl")
PASS_RATE = 0.9
_UNIT_FORMS = (("kgf/cm²", "kgf/cm2"), ("kg/cm²", "kgf/cm2"), ("kg/cm2", "kgf/cm2"), ("m²", "m2"))


def normalize(value: str) -> str:
    """So khớp bỏ khoảng trắng / hoa thường; đơn vị viết ² và cm2 coi như nhau."""
    text = unicodedata.normalize("NFC", str(value)).casefold()
    for source, target in _UNIT_FORMS:
        text = text.replace(source, target)
    return re.sub(r"\s+", "", text)


def _payload_text(payload) -> str:
    return " ".join(
        cell.text for table in payload.tables for row in table.rows for cell in row.values()
    )


def run_case(case: dict, classifier) -> dict:
    """Một câu qua đường chat thật; trả intent, giá trị thiếu và kết quả."""
    from db import SessionLocal
    from query import intents, router

    decision = intents.decide(classifier.classify(case["question"]))
    intent = decision.request.intent if decision.branch != "text" and decision.request else None
    text = ""
    if intent is not None:
        session = SessionLocal()
        try:
            text = _payload_text(router.build_data_payload(session, decision.request))
        except Exception as exc:  # noqa: BLE001 - lỗi resolver là một câu trượt, không dừng eval
            text = f"LỖI: {exc}"
        finally:
            session.close()
    blob = normalize(text)
    missing = [value for value in case.get("must", []) if normalize(value) not in blob]
    leaked = [value for value in case.get("must_not", []) if normalize(value) in blob]
    accepted = case.get("intents") or ([case["intent"]] if case.get("intent") else [])
    intent_ok = intent in accepted if accepted else True
    if intent in case.get("not_intents", []):
        intent_ok = False
    return {
        "id": case["id"],
        "intent": intent,
        "expected": case.get("intent"),
        "missing": missing,
        "leaked": leaked,
        "passed": intent_ok and not missing and not leaked,
    }


def main(argv: list[str] | None = None) -> int:
    from query import intents

    parser = argparse.ArgumentParser(description="Eval tra cứu biên bản trên sổ cái thật")
    parser.add_argument("--path", type=Path, default=DEFAULT_SET)
    parser.add_argument("--set", dest="subset", help="Chỉ chạy một bộ (bo20, paraphrase)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    lines = args.path.read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in lines if line.strip()]
    if args.subset:
        cases = [case for case in cases if case.get("set") == args.subset]
    classifier = intents.default_classifier()
    results = [run_case(case, classifier) for case in cases]
    passed = sum(result["passed"] for result in results)
    for result in results:
        if args.verbose or not result["passed"]:
            mark = "✓" if result["passed"] else "✗"
            print(
                f"  {mark} {result['id']}: intent {result['intent']} "
                f"(mong {result['expected']}), thiếu {result['missing']}"
                + (f", thừa {result['leaked']}" if result["leaked"] else "")
            )
    rate = passed / len(results) if results else 0.0
    ok = rate >= PASS_RATE
    print(f"Tra cứu biên bản: {passed}/{len(results)} đạt ({rate:.3f})")
    print(
        f"Cổng: ≥ {PASS_RATE:.2f} câu đạt (intent đúng + đủ số liệu) → {'ĐẠT' if ok else 'TRƯỢT'}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
