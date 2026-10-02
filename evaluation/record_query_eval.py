"""Eval tra cứu biên bản có cấu trúc trên sổ cái thật (Pha R).

Mỗi câu trong ``evaluation/record_query_set.jsonl`` đi ĐÚNG đường của ``/api/chat/stream``:
bộ phân loại Ollama → ``decide`` → ``build_data_payload`` trên PostgreSQL. Một câu
đạt khi intent đúng VÀ mọi giá trị trong ``must`` (nguyên văn biên bản, so sau khi
bỏ khoảng trắng, số khớp trọn) có mặt trong câu trả lời (bộ ``bo20``, đúng tiêu chí
chấm của ``Bo_20_cau.xlsx``) hoặc trong câu trả lời + bảng (các bộ khác). ``must_not``
là giá trị (hay tiêu đề bảng) KHÔNG được xuất hiện (câu lọc theo người / đơn vị mà trả
cả sổ cái thì trượt, dù đủ ``must``; câu cực trị kèm cả danh sách sổ cái cũng trượt).
``not_intents`` là intent câu hỏi KHÔNG được rơi vào (câu hỏi quy định không bị kéo
sang tra biên bản). ``intents`` (tuỳ chọn) liệt kê mọi intent trả lời đúng câu hỏi khi
có hơn một cách.

Bộ ``bo20`` là 20 câu hỏi trích xuất số liệu áp kế pít tông (``Bo_20_cau.xlsx``);
bộ ``paraphrase`` là câu hỏi diễn đạt khác để chống khớp riêng bộ câu gốc; bộ ``gen``
(``record_query_generated.jsonl``) do một LLM khác sinh, đáp án lấy nguyên văn sổ cái. Cần
Postgres (20 biên bản trong ``TC_DL/`` đã nạp + duyệt) và Ollama.

Usage:
  OLLAMA_MODEL=<model chat, xem config/settings.yaml> python -m evaluation.record_query_eval [--set bo20] [-v]
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


# Bộ chấm theo câu trả lời: "câu trả lời phải chứa hoặc khớp đủ các giá trị này"
# (Bo_20_cau.xlsx, sheet "Huong dan"); các bộ khác chấm trên câu trả lời + bảng.
ANSWER_SETS = frozenset({"bo20"})


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFC", str(value)).casefold()
    for source, target in _UNIT_FORMS:
        text = text.replace(source, target)
    return re.sub(r"\s+", " ", text)


def contains(text: str, value: str) -> bool:
    """``value`` có trong ``text`` như một giá trị trọn, không phải mẩu của số khác.

    Khoảng trắng tùy ý ("1 015,99" ≡ "1015,99"), nhưng số phải khớp trọn: "20" không
    khớp "020/2026", "12" không khớp "1 200", "0,31" vẫn khớp "lượt 1 0,31".
    """
    needle = _fold(value).strip()
    if not needle:
        return True
    pattern = r"\s?".join(re.escape(char) for char in needle if not char.isspace())
    if needle[0].isdigit():
        pattern = r"(?<![\d,.])" + pattern
    if needle[-1].isdigit():
        pattern += r"(?!\d)(?![,.]\d)"
    return re.search(pattern, _fold(text)) is not None


def _payload_text(payload) -> str:
    """Câu trả lời + tiêu đề và ô của mọi bảng: ``must_not`` bắt được cả bảng thừa."""
    cells = [cell.text for table in payload.tables for row in table.rows for cell in row.values()]
    titles = [table.title for table in payload.tables]
    return " ".join([payload.answer or "", *titles, *cells])


def run_case(case: dict, classifier) -> dict:
    """Một câu qua đường chat thật; trả intent, giá trị thiếu và kết quả."""
    from db import SessionLocal
    from query import intents, router

    decision = intents.decide(classifier.classify(case["question"]))
    intent = decision.request.intent if decision.branch != "text" and decision.request else None
    text = answer = ""
    if intent is not None:
        session = SessionLocal()
        try:
            payload = router.build_data_payload(session, decision.request)
            text, answer = _payload_text(payload), payload.answer or ""
        except Exception as exc:  # noqa: BLE001 - lỗi resolver là một câu trượt, không dừng eval
            text = f"LỖI: {exc}"
        finally:
            session.close()
    graded = answer if case.get("set") in ANSWER_SETS else text
    missing = [value for value in case.get("must", []) if not contains(graded, value)]
    leaked = [value for value in case.get("must_not", []) if contains(text, value)]
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
