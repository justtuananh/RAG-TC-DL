"""Kiểu dữ liệu chung cho bộ luật trích xuất QTKĐ.

``RuleHit`` là một ứng viên trích xuất: một dòng dữ kiện kèm đầy đủ xuất xứ P1
(đường dẫn mục, đoạn trích nguyên văn, khoảng ký tự) để tầng ghi dựng bản ghi
``extraction`` + bảng dữ kiện tương ứng. Bộ luật thuần hàm: không chạm DB.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleHit:
    """Một ứng viên trích xuất từ một luật.

    ``kind`` nhận ``"fact"`` | ``"standard"`` | ``"term"``. Các trường còn lại
    chỉ có nghĩa với ``kind`` tương ứng (fact → ``fact_kind``…, standard →
    ``name_vi``…, term → ``term_vi``…).
    """

    kind: str
    extractor: str
    section_path: str
    quote: str
    char_start: int
    char_end: int
    confidence: float = 0.9

    # fact
    fact_kind: str | None = None
    label: str | None = None
    rel_op: str | None = None
    value_min: float | None = None
    value_max: float | None = None
    unit: str | None = None
    unit_min: str | None = None
    unit_max: str | None = None
    value_text: str | None = None
    condition_text: str | None = None

    # standard (Bảng 2)
    ord: int | None = None
    name_vi: str | None = None
    range_text: str | None = None
    accuracy_text: str | None = None
    note: str | None = None

    # term (§2)
    term_vi: str | None = None
    term_en: str | None = None
    definition: str | None = None
