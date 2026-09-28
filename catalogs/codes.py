"""Nhận dạng và chuẩn hóa mã tiêu chuẩn, quy trình trong hồ sơ NAS.

Biểu 1/4 ghi mã rất không đồng nhất: "QTKĐ 1.019 : 2014", "QTKĐ 1.159.2021",
"23 QTKĐ 1.039: 2001", "ĐLVN 213:2009", "TCVN 5199 - 1990", "06.TCN 3.80-88".
Dạng chuẩn hóa là ``[tiền tố ]HỌ SỐ:NĂM``; mã không nhận dạng được vẫn giữ
nguyên văn (``family=None``), không đoán.
"""

from __future__ import annotations

import re

from catalogs.types import ProcedureCode
from knowledge import vnnum

_CODE_RE = re.compile(
    r"^(?:(?P<prefix>\d{2})\s+)?"
    r"(?P<family>QTK[ĐD]|ĐLVN|DLVN|TCVN|TQSA|TQSB|TC|\d{2}\.TCN)\s+"
    r"(?P<number>\d+(?:\.\d+)?)\s*"
    r"(?:[:\-.]\s*(?P<year>\d{4}|\d{2}))?\s*$",
    re.IGNORECASE,
)
_SPLIT_RE = re.compile(r"\s*(?:\n|\s/\s)\s*")
_FAMILY_ALIASES = {"QTKD": "QTKĐ", "DLVN": "ĐLVN"}
_TWO_DIGIT_YEAR_PIVOT = 30


def _year(text: str | None) -> int | None:
    if not text:
        return None
    value = int(text)
    if len(text) == 2:
        value += 1900 if value > _TWO_DIGIT_YEAR_PIVOT else 2000
    return value


def parse_code(text: str) -> ProcedureCode:
    """Một mã; không khớp mẫu thì giữ nguyên văn đã chuẩn hóa khoảng trắng."""
    raw = vnnum.normalize_spaces(text).strip()
    match = _CODE_RE.match(raw)
    if match is None:
        return ProcedureCode(raw=raw, normalized=raw)
    family = match.group("family").upper()
    family = _FAMILY_ALIASES.get(family, family)
    prefix, number, year = match.group("prefix"), match.group("number"), _year(match.group("year"))
    head = f"{prefix} {family}" if prefix else family
    normalized = f"{head} {number}:{year}" if year else f"{head} {number}"
    return ProcedureCode(
        raw=raw, normalized=normalized, family=family, prefix=prefix, number=number, year=year
    )


def parse_codes(text: str | None) -> list[ProcedureCode]:
    """Mọi mã trong một ô (các mã tách nhau bằng xuống dòng hoặc " / ")."""
    if not text:
        return []
    return [parse_code(part) for part in _SPLIT_RE.split(text.strip()) if part.strip()]
