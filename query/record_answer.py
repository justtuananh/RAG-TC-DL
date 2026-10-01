"""Câu trả lời một dòng cho câu hỏi cực trị trên sổ cái ("Biên bản nào ... thấp nhất").

Người hỏi cần biết biên bản nào và giá trị bao nhiêu, không phải cả sổ cái:

    Biên bản 020/2026 của áp kế píttông tiêu chuẩn CPB5800 số hiệu 1A0043219, ngày
    19/05/2026: trung bình 154,6 s (cùng chiều kim đồng hồ 157,3 s; ngược chiều kim
    đồng hồ 151,9 s), thấp hơn mức cho phép ≥ 180 s nên không đạt.

Câu được dựng tất định (không qua LLM) từ NGUYÊN VĂN các ô của dòng thắng bằng
``query.answer_phrases``; bảng đi kèm chỉ có dòng thắng và vẫn giữ xuất xứ từng ô (P1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from query.answer_phrases import clean_value, lower_first, point_clause, record_head
from query.table_model import DataTable


@dataclass
class RankGroup:
    """Kết quả cực trị của MỘT QTKĐ: bảng các dòng thắng và câu trả lời cho từng dòng."""

    table: DataTable
    procedure: str | None
    label: str
    order: str
    sentences: list[str] = field(default_factory=list)


def point_sentence(record: dict, point: dict, table_label: str) -> str:
    """Câu trả lời cho một dòng số liệu đo thắng cực trị."""
    return f"{record_head(record)}: {point_clause(record, point, table_label)}."


def field_sentence(record: dict, row: dict, label: str, related: list[tuple[str, Any]]) -> str:
    """Câu trả lời cho một trường đầu mục thắng cực trị (kèm trường đi kèm, vd. U(p))."""
    sentence = f"{record_head(record)}: {lower_first(label)} {clean_value(row.get('value_text'))}"
    extras = [
        f"{related_label} {clean_value(related_row['value_text'])}"
        for related_label, related_row in related
        if related_row is not None and related_row.get("value_text")
    ]
    if extras:
        sentence += f" ({'; '.join(extras)})"
    return sentence + "."


def extreme_answer(groups: list[RankGroup]) -> str:
    """Ghép câu trả lời: một dòng thắng → một câu; đồng hạng / nhiều QTKĐ → danh sách."""
    if len(groups) == 1 and len(groups[0].sentences) == 1:
        return groups[0].sentences[0]
    if len(groups) == 1:
        group = groups[0]
        lines = [f"- {sentence}" for sentence in group.sentences]
        lead = f"Có {len(lines)} biên bản cùng {lower_first(group.label)} {group.order}:"
        return "\n".join([lead, "", *lines])
    lines = [
        f"- **QTKĐ {group.procedure}**{' (đồng hạng)' if len(group.sentences) > 1 else ''}: "
        f"{sentence}"
        for group in groups
        for sentence in group.sentences
    ]
    return "\n".join(["Mỗi QTKĐ so riêng, không so chéo quy trình:", "", *lines])
