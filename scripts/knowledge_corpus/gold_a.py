"""Gold nhóm A suy TRỰC TIẾP từ spec thiết bị (``devices_a.py``) -- redo R1.

KHÔNG import ``knowledge.rules`` ở đây. ``qtkd_doc.py`` chỉ ghép các chuỗi
``value_text`` có sẵn trong spec vào câu văn (không định dạng lại số liệu), nên
mỗi hàm dưới đây chỉ cần đọc lại đúng những chuỗi đó và đóng gói theo schema
``eval/extract_golden.jsonl`` / ``eval/extract_golden_section6.jsonl`` (xem
``eval/extract_eval.py:golden_key`` để biết khoá đối chiếu chính xác). Nếu chạy
``eval.extract_eval`` cho kết quả sai với gold này, đó là một hành vi cần xác
minh (sửa tài liệu nếu tài liệu sai, hoặc ghi K-code mới nếu code sai) --
KHÔNG được bẻ gold để khớp code.
"""

from __future__ import annotations


def golden_rows_for_doc(doc_stem: str, dev: dict) -> list[dict]:
    """Dòng ``extract_golden.jsonl`` cho một QTKĐ nhóm A, suy từ ``dev`` spec."""
    rows: list[dict] = []

    rows.append(
        {
            "doc": doc_stem,
            "kind": "fact",
            "fact_kind": "working_range",
            "value_text": dev["range"]["value_text"],
        }
    )

    for term in dev["terms"]:
        rows.append({"doc": doc_stem, "kind": "term", "term_vi": term["vi"], "term_en": term["en"]})

    for step in dev["bang1"]:
        rows.append(
            {
                "doc": doc_stem,
                "kind": "fact",
                "fact_kind": "inspection_step",
                "label": step["label"],
            }
        )

    for std in dev["bang2"]:
        rows.append(
            {
                "doc": doc_stem,
                "kind": "standard",
                "name_vi": std["name"],
                "range_text": std["range"],
            }
        )

    for label, value_text in dev["env"]:
        rows.append(
            {
                "doc": doc_stem,
                "kind": "fact",
                "fact_kind": "env_condition",
                "label": label,
                "value_text": value_text,
            }
        )

    rows.append(
        {
            "doc": doc_stem,
            "kind": "fact",
            "fact_kind": "calibration_interval",
            "value_text": f"{dev['interval_months']} tháng",
        }
    )

    return rows


def section6_golden_rows_for_doc(doc_stem: str, dev: dict) -> list[dict]:
    """Dòng ``extract_golden_section6.jsonl`` cho một QTKĐ nhóm A, suy từ ``dev["section6"]``."""
    rows: list[dict] = []
    for fact in dev["section6"]:
        row = {
            "doc": doc_stem,
            "fact_kind": "max_permissible_error",
            "label": fact["label"],
            "rel_op": fact["rel_op"],
            "value_text": fact["value_text"],
            "limit": dict(fact["limit"]),
            "quote": fact["sentence"],
        }
        if fact.get("condition_text"):
            row["condition_text"] = fact["condition_text"]
        if fact.get("floor"):
            row["floor"] = dict(fact["floor"])
        rows.append(row)
    return rows
