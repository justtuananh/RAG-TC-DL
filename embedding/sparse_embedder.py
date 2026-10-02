"""Biểu diễn thưa (bag-of-tokens) cho nhánh BM25 của truy hồi lai.

Tokenizer CỐ Ý giữ nguyên mã kỹ thuật và đơn vị (vd. `1.061:2021`, `MPa`): dense
embedding làm mờ chúng, BM25 là nhánh duy nhất khớp chính xác ký hiệu / số QTKĐ.
"""

from __future__ import annotations

import re

_SPLIT_RE = re.compile(r'[\s,;!()\[\]{}<>"\'\\|]+')


def tokenize(text: str) -> list[str]:
    """Lowercase split preserving codes like 1.061:2021, MPa, bar, DN≤50."""
    tokens = _SPLIT_RE.split(text.lower())
    return [t for t in tokens if t]


def sparse_document_text(payload: dict) -> str:
    """Include file_stem + section_path so BM25 can match QTKĐ numbers (e.g. 1.062, 1.063)."""
    parts = [
        payload.get("file_stem", ""),
        payload.get("section_path", ""),
        payload.get("text", ""),
    ]
    return " ".join(p for p in parts if p)
