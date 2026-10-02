"""So sánh các phương án kiến trúc trên CÙNG một bộ câu hỏi biên bản (báo cáo đồ án, Chương 5).

Ba chế độ, cùng tiêu chí chấm của ``eval/record_query_eval.py`` (mọi giá trị ``must``
có mặt nguyên văn, không giá trị ``must_not`` nào lọt vào, so sau khi bỏ khoảng trắng):

- ``text``: RAG văn bản thuần của Chương 2-4 (truy hồi lai → LLM sinh câu trả lời),
  chấm trên câu trả lời văn xuôi;
- ``sql``: text-to-SQL - LLM đọc lược đồ ba view đã duyệt và tự viết một câu SELECT,
  chấm trên kết quả truy vấn (giao dịch chỉ đọc, có giới hạn thời gian);
- ``router``: bộ định tuyến intent của mã nguồn ở ``--code-root`` (đo lại được các
  commit cũ trong một git worktree), chấm trên bảng số liệu trả về.

Câu hỏi quy định (``not_intents``) đạt khi KHÔNG bị kéo sang tra biên bản; ở chế độ
``sql`` đạt khi mô hình trả ``NO_SQL``. Kết quả từng câu ghi ra ``--out`` (JSON).

Usage:
  OLLAMA_MODEL=qwen2.5:3b python eval/arch_eval.py --mode text --out logs/arch/text.json
  python eval/arch_eval.py --mode router --code-root /path/to/worktree --out ...
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
SETS = (HERE / "record_query_set.jsonl", HERE / "record_query_generated.jsonl")
_UNIT_FORMS = (("kgf/cm²", "kgf/cm2"), ("kg/cm²", "kgf/cm2"), ("kg/cm2", "kgf/cm2"), ("m²", "m2"))
SQL_VIEWS = ("v_record_detail", "v_record_field", "v_measurement_detail")
SQL_ROW_LIMIT = 200
SQL_TIMEOUT_MS = 5000


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFC", str(value)).casefold()
    for source, target in _UNIT_FORMS:
        text = text.replace(source, target)
    return re.sub(r"\s+", "", text)


def load_cases() -> list[dict]:
    cases = []
    for path in SETS:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                cases.append(json.loads(line))
    return cases


def is_regulation(case: dict) -> bool:
    return not case.get("intent") and not case.get("intents") and bool(case.get("not_intents"))


def score(case: dict, blob: str) -> tuple[list[str], list[str]]:
    text = normalize(blob)
    missing = [v for v in case.get("must", []) if normalize(v) not in text]
    leaked = [v for v in case.get("must_not", []) if normalize(v) in text]
    return missing, leaked


# ── text: RAG văn bản thuần ──────────────────────────────────────────────────


def run_text(case: dict) -> dict:
    from llm.generator import stream_ollama
    from llm.guards import REFUSAL_SENTENCE, enforce_refusal_stop, is_calculation_request
    from llm.prompt import build_messages
    from retrieval.context_builder import build_context_and_citations, filter_by_confidence
    from retrieval.retriever import retrieve

    question = case["question"]
    if is_calculation_request(question):
        answer = REFUSAL_SENTENCE
    else:
        results = filter_by_confidence(retrieve(question))
        context, _ = build_context_and_citations(results)
        messages = build_messages(question, context, [])
        answer = enforce_refusal_stop("".join(stream_ollama(messages)))
    if is_regulation(case):
        return {"passed": True, "route": "text", "answer": answer[:400]}
    missing, leaked = score(case, answer)
    return {
        "passed": not missing and not leaked,
        "route": "text",
        "missing": missing,
        "leaked": leaked,
        "answer": answer[:400],
    }


# ── sql: text-to-SQL trên view đã duyệt ──────────────────────────────────────


def _schema(session) -> str:
    from sqlalchemy import text

    lines = []
    for view in SQL_VIEWS:
        cols = session.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = :v ORDER BY ordinal_position"
            ),
            {"v": view},
        ).all()
        lines.append(f"{view}(" + ", ".join(f"{c} {t}" for c, t in cols) + ")")
    keys = session.execute(
        text("SELECT DISTINCT field_key, label FROM v_record_field ORDER BY field_key")
    ).all()
    steps = session.execute(
        text("SELECT DISTINCT step_code, label FROM v_measurement_detail ORDER BY step_code")
    ).all()
    lines.append("Giá trị field_key của v_record_field (field_key: nhãn):")
    lines += [f"  {key}: {label}" for key, label in keys]
    lines.append("Giá trị step_code của v_measurement_detail (step_code: nhãn dòng):")
    seen: set[str] = set()
    for code, label in steps:
        if code not in seen:
            seen.add(code)
            lines.append(f"  {code}: {label or ''}")
    return "\n".join(lines)


SQL_SYSTEM = (
    "Bạn viết MỘT câu lệnh PostgreSQL SELECT để trả lời câu hỏi về biên bản kiểm định, "
    "CHỈ dùng các view dưới đây. v_record_detail: một dòng mỗi biên bản (cert_no là số "
    "biên bản, serial_no là số hiệu thiết bị, verdict là 'dat' hoặc 'khong_dat', "
    "calibrated_at là ngày kiểm định). v_record_field: trường đầu mục của biên bản "
    "(record_id = v_record_detail.id, value_text là giá trị nguyên văn). "
    "v_measurement_detail: từng dòng bảng kết quả (record_id, step_code, *_text là "
    "nguyên văn, cells là JSON nguyên văn từng ô). Luôn SELECT kèm cột nguyên văn cần "
    "trả lời và cert_no. Nếu câu hỏi hỏi về nội dung quy trình kiểm định (không phải dữ "
    "liệu biên bản cụ thể) thì trả đúng một từ NO_SQL. Chỉ trả câu SQL, không giải thích."
)


def _ask_sql(question: str, schema: str) -> str:
    import requests

    from core.settings_loader import get_settings
    from llm.generator import native_chat_url

    url = native_chat_url(get_settings().llm_url("chat"))
    body = {
        "model": get_settings().llm_model("chat"),
        "messages": [
            {"role": "system", "content": SQL_SYSTEM + "\n\nLược đồ:\n" + schema},
            {"role": "user", "content": question},
        ],
        "stream": False,
        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 512},
    }
    reply = requests.post(url, json=body, timeout=300).json()["message"]["content"]
    match = re.search(r"```(?:sql)?\s*(.*?)```", reply, re.S | re.I)
    return (match.group(1) if match else reply).strip().rstrip(";")


def run_sql(case: dict, session, schema: str) -> dict:
    from sqlalchemy import text

    sql = _ask_sql(case["question"], schema)
    if sql.upper().startswith("NO_SQL"):
        return {"passed": is_regulation(case), "route": "no_sql", "sql": sql}
    if is_regulation(case):
        return {"passed": False, "route": "sql", "sql": sql[:400]}
    if not re.match(r"(?is)^\s*(select|with)\b", sql):
        return {
            "passed": False,
            "route": "sql_error",
            "sql": sql[:400],
            "error": "không phải SELECT",
        }
    try:
        session.execute(text("SET TRANSACTION READ ONLY"))
        session.execute(text(f"SET LOCAL statement_timeout = {SQL_TIMEOUT_MS}"))
        rows = session.execute(text(sql)).fetchmany(SQL_ROW_LIMIT)
    except Exception as exc:  # noqa: BLE001 - SQL lỗi là một kết quả đo, không dừng eval
        session.rollback()
        return {"passed": False, "route": "sql_error", "sql": sql[:400], "error": str(exc)[:200]}
    session.rollback()
    blob = " ".join(str(value) for row in rows for value in row if value is not None)
    missing, leaked = score(case, blob)
    route = "sql_ok" if not missing and not leaked else "sql_wrong"
    return {
        "passed": route == "sql_ok",
        "route": route,
        "sql": sql[:400],
        "rows": len(rows),
        "missing": missing,
        "leaked": leaked,
    }


# ── router: bộ định tuyến của phiên bản mã được đo ───────────────────────────


def run_router(case: dict, classifier) -> dict:
    from db import SessionLocal
    from query import intents, router

    decision = intents.decide(classifier.classify(case["question"]))
    intent = decision.request.intent if decision.branch != "text" and decision.request else None
    if is_regulation(case):
        return {"passed": intent not in case["not_intents"], "route": intent or "text"}
    blob, error = "", None
    if intent is not None:
        session = SessionLocal()
        try:
            payload = router.build_data_payload(session, decision.request)
            blob = " ".join(
                cell.text for table in payload.tables for row in table.rows for cell in row.values()
            )
        except Exception as exc:  # noqa: BLE001 - resolver lỗi là một câu trượt
            error = str(exc)[:200]
        finally:
            session.close()
    missing, leaked = score(case, blob)
    return {
        "passed": intent is not None and not missing and not leaked,
        "route": intent or "text",
        "missing": missing,
        "leaked": leaked,
        "error": error,
    }


def summarize(cases: list[dict], results: list[dict]) -> dict:
    groups: dict[str, list[bool]] = {}
    for case, result in zip(cases, results, strict=True):
        group = "quy_dinh" if is_regulation(case) else case.get("set", "?")
        groups.setdefault(group, []).append(result["passed"])
    return {name: [sum(values), len(values)] for name, values in groups.items()}


def _runner(mode: str):
    if mode == "router":
        from query import intents

        classifier = intents.default_classifier()
        return lambda case: run_router(case, classifier)
    if mode == "sql":
        from db import SessionLocal

        session = SessionLocal()
        schema = _schema(session)
        session.rollback()
        return lambda case: run_sql(case, session, schema)
    return run_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="So sánh phương án kiến trúc trên bộ câu hỏi biên bản"
    )
    parser.add_argument("--mode", choices=("text", "sql", "router"), required=True)
    parser.add_argument("--code-root", type=Path, default=HERE.parent)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label", default="")
    args = parser.parse_args(argv)

    out = args.out.resolve()
    sys.path.insert(0, str(args.code_root.resolve()))
    os.chdir(args.code_root)
    cases = load_cases()
    run = _runner(args.mode)
    results: list[dict] = []
    started = time.monotonic()
    for index, case in enumerate(cases, start=1):
        try:
            result = run(case)
        except Exception as exc:  # noqa: BLE001 - lỗi hạ tầng một câu không dừng lượt đo
            result = {"passed": False, "route": "error", "error": str(exc)[:200]}
        results.append({"id": case["id"], "question": case["question"], **result})
        mark = "✓" if result["passed"] else "✗"
        print(f"[{index}/{len(cases)}] {mark} {case['id']} {result['route']}", flush=True)
    summary = summarize(cases, results)
    out.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "label": args.label,
        "mode": args.mode,
        "summary": summary,
        "seconds": round(time.monotonic() - started),
        "results": results,
    }
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
