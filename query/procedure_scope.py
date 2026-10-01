"""Câu hỏi QTKĐ nào trả lời được bằng dữ kiện đã duyệt (``procedure_params``).

Chạy SAU ``disambiguate_records``. Model phân loại nhỏ đưa MỌI câu hỏi có số QTKĐ vào
``procedure_params`` (quy tắc 8 của prompt), kể cả câu hỏi quy định mà sổ cái không
có dữ kiện ("sai số cho phép của áp suất chỉnh đặt…", "tốc độ hạ của pít tông…"). Bảng
trả về khi đó là toàn bộ dữ kiện của QTKĐ, không trả lời câu hỏi, trong khi văn bản
QTKĐ có đáp án nguyên văn kèm trích dẫn.

Lớp này đọc câu hỏi để biết nó hỏi LOẠI dữ kiện nào (phạm vi đo, cấp chính xác, chu kỳ
kiểm định, điều kiện môi trường…):

- hỏi một đại lượng không thuộc loại dữ kiện nào (độ chênh áp, tốc độ hạ, công thức…)
  → nhánh văn bản, không gọi DB;
- hỏi đúng loại dữ kiện → ``asked_kinds`` (+ ``asked_labels`` cho điều kiện môi
  trường) để resolver chỉ giữ dữ kiện được hỏi; thiếu dữ kiện cho một phần được hỏi
  thì resolver trả bảng rỗng và câu hỏi rơi về nhánh văn bản;
- hỏi chung "thông số của QTKĐ X" → giữ nguyên (bảng mọi dữ kiện đã duyệt).
"""

from __future__ import annotations

import re
from typing import Any

from catalogs.text import fold
from query.answer_phrases import clean_value, lower_first

# Loại dữ kiện (``procedure_fact.fact_kind``) và cách hỏi tương ứng, trên chữ đã bỏ dấu.
_KIND_CUES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("working_range", re.compile(r"pham vi (?:do|lam viec)|gioi han do|dai do|khoang do")),
    ("accuracy_class", re.compile(r"cap chinh xac|\bccx\b")),
    ("calibration_interval", re.compile(r"chu ky")),
    # Hỏi GIÁ TRỊ sai số cho phép, không phải mọi câu có chữ "sai số" ("nguyên nhân gây
    # sai số", "sai số được tính thế nào").
    (
        "max_permissible_error",
        re.compile(r"sai so(?: \w+){0,3} (?:cho phep|lon nhat|cuc dai|toi da)"),
    ),
    ("env_condition", re.compile(r"nhiet do|do am|ap suat khi quyen")),
    ("formula", re.compile(r"cong thuc")),
)
ENV_KIND = "env_condition"
# Nhiệt độ / độ ẩm là điều kiện môi trường KHI KIỂM ĐỊNH chỉ khi câu hỏi nói vậy; "nhiệt
# độ làm việc của van", "nhiệt độ bảo quản" là đại lượng khác.
_ENV_CONTEXT_RE = re.compile(r"dieu kien|moi truong|kiem dinh|hieu chuan|phong (?:do|thi nghiem)")
# Nhãn dữ kiện điều kiện môi trường ("Nhiệt độ môi trường", "Độ ẩm tương đối").
ENV_LABELS: tuple[str, ...] = ("nhiet do", "do am", "ap suat khi quyen")
# Hỏi chung mọi dữ kiện của QTKĐ.
_GENERIC_RE = re.compile(r"thong so|du kien")
# Đại lượng / nội dung quy định mà ``procedure_fact`` không có loại dữ kiện: trả lời từ
# văn bản QTKĐ. "sai so" và "cong thuc" là loại dữ kiện ở trên, không nằm ở đây.
_OTHER_RE = re.compile(
    r"do chenh|tut ap|(?:tang|giam)(?:\s*/\s*(?:tang|giam))? ap|toc do|thoi gian|do kin|"
    r"do nhay|dung tich|the tich|khoi luong|do lech|do khong dam bao|dkdbd|do on dinh|"
    r"do tre|ha pit|cach (?:tinh|xac dinh|kiem|lam|tien hanh)|phuong phap|cac buoc|"
    r"trinh tu|yeu cau ky thuat|nguyen nhan|anh huong|xu ly khi|"
    r"(?:nhiet do|do am|ap suat) (?:lam viec|bao quan|van hanh|su dung)"
)


def asked_kinds(question: str) -> tuple[list[str], list[str]] | None:
    """(loại dữ kiện, nhãn điều kiện môi trường) câu hỏi nhắm tới.

    None: câu hỏi hỏi điều dữ kiện đã duyệt không có (trả lời từ văn bản). ``([], [])``:
    câu hỏi chung về thông số của QTKĐ.
    """
    text = fold(question)
    if _OTHER_RE.search(text):
        return None
    kinds = [kind for kind, cue in _KIND_CUES if cue.search(text)]
    if ENV_KIND in kinds and not _ENV_CONTEXT_RE.search(text):
        return None
    if not kinds:
        return ([], []) if _GENERIC_RE.search(text) else None
    labels = [label for label in ENV_LABELS if label in text] if ENV_KIND in kinds else []
    return kinds, labels


def scope_procedure_params(payload: dict[str, Any] | None, question: str) -> dict[str, Any] | None:
    """Gắn phạm vi dữ kiện được hỏi vào ``procedure_params``, hoặc trả về nhánh văn bản."""
    if not isinstance(payload, dict):
        return payload
    if str(payload.get("intent") or "").strip().lower() != "procedure_params":
        return payload
    asked = asked_kinds(question or "")
    if asked is None:
        return {"branch": "text", "confidence": 1.0}
    kinds, labels = asked
    if not kinds:
        return payload
    params = {**(payload.get("params") or {}), "asked_kinds": kinds, "asked_labels": labels}
    return {**payload, "params": params}


def _distinct(group: list[dict]) -> bool:
    """Các dữ kiện cùng loại phân biệt được bằng nhãn hoặc điều kiện của chúng.

    QTKĐ 1.159 có ba "Phạm vi đo" không ghi điều kiện (khí tuyệt đối, khí tương đối,
    chất lỏng): kể ba khoảng trần trụi là mất ngữ cảnh, văn bản QTKĐ nói rõ hơn.
    """
    keys = {(fold(fact.get("label")), fold(fact.get("condition_text"))) for fact in group}
    return len(keys) == len(group)


def select_facts(facts: list[dict], kinds: list[str], labels: list[str]) -> list[dict] | None:
    """Dữ kiện trả lời đúng điều được hỏi, theo thứ tự câu hỏi; None khi thiếu một phần."""
    chosen: list[dict] = []
    for kind in kinds:
        of_kind = [fact for fact in facts if fact.get("fact_kind") == kind]
        if kind == ENV_KIND:
            groups = [[f for f in of_kind if label in fold(f.get("label"))] for label in labels]
        else:
            groups = [of_kind]
        for group in groups:
            if not group or not _distinct(group):
                return None
            chosen.extend(fact for fact in group if fact not in chosen)
    return chosen


def fact_clause(fact: dict, kind_label: str) -> str:
    """ "nhiệt độ môi trường (23 ± 5) oC, nhiệt độ không được thay đổi quá 2 oC/h"."""
    label = lower_first(fact.get("label") or kind_label)
    clause = f"{label} {clean_value(fact.get('value_text'))}"
    condition = fact.get("condition_text")
    return f"{clause}, {lower_first(clean_value(condition))}" if condition else clause


def facts_answer(number: str, clauses: list[str], *, asked: bool) -> str:
    """Câu hỏi đúng loại dữ kiện → một câu; câu hỏi chung → danh sách dữ kiện."""
    if asked:
        # "; " giữa các vế: một vế có thể chứa dấu phẩy (điều kiện kèm theo).
        return f"Theo QTKĐ {number}: {'; '.join(clauses)}."
    lines = "\n".join(f"- {clause}" for clause in clauses)
    return f"QTKĐ {number} có {len(clauses)} dữ kiện đã duyệt:\n\n{lines}"
