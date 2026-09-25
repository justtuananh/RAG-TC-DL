"""§1 Phạm vi áp dụng → ``working_range`` (spec §7).

Luật nhận diện ba mẫu khoảng phạm vi đo gặp trong corpus:

- ``phạm vi (làm việc|đo) ... đến X đv`` (1.061/1.062/1.063);
- ``(A đến B) đv`` (1.159, nhiều dòng);
- ``từ A đv đến B đv`` (1.071/1.160/1.190).

Không khớp mẫu → rỗng. Số Việt (phẩy thập phân, nhóm nghìn) do ``vnnum`` xử lý;
đơn vị giữ nguyên văn để tầng ghi quy đổi SI, đơn vị lạ thì bỏ trống số.
"""

from __future__ import annotations

import re

from knowledge import vnnum
from knowledge.rules.sections import find_section, split_sections
from knowledge.rules.types import RuleHit

EXTRACTOR = "rule:phamvi.v1"
FACT_KIND = "working_range"
SECTION_KEYWORDS = ("phạm vi",)

_UNIT = r"[A-Za-zµ%°/](?:[\w%°/²³]|\.(?=[\w%°/²³]))*"
# K15: dấu "." chỉ thuộc đơn vị khi còn ký tự đơn vị theo sau; dấu chấm câu cuối
# token (theo sau là khoảng trắng hoặc hết dòng) bị chặn, không lọt vào value_text.
_NUM = r"-?\s?\d[\d\s.,]*?"

_TU_DEN_RE = re.compile(
    rf"từ\s+(?P<lo>{_NUM})\s*(?P<lo_unit>{_UNIT})?"
    rf"\s+đến\s+(?P<hi>{_NUM})\s*(?P<hi_unit>{_UNIT})",
    re.IGNORECASE,
)
_PAREN_RE = re.compile(rf"\((?P<inner>[^()]{{1,80}})\)\s*(?P<unit>{_UNIT})")
_DEN_ONLY_RE = re.compile(
    rf"(?:phạm\s+vi(?:\s+(?:làm\s+việc|đo))?|giới\s+hạn\s+đo)"
    rf"[^,;.\n]*?đến\s+(?P<num>{_NUM})\s*(?P<unit>{_UNIT})",
    re.IGNORECASE,
)


def _clean_num(text: str) -> str:
    cleaned = vnnum.normalize_spaces(text)
    return re.sub(r"^([+\-])\s+", r"\1", cleaned)


def _parse_num(text: str) -> float | None:
    return vnnum.parse_number(_clean_num(text))


def _normalize_signs(text: str) -> str:
    return re.sub(r"([+\-])\s+", r"\1", text)


def extract(text: str) -> list[RuleHit]:
    """Rút các khoảng phạm vi đo từ §1; rỗng nếu không có mục hoặc không khớp."""
    sections = split_sections(text)
    section = find_section(sections, *SECTION_KEYWORDS)
    if section is None:
        return []

    body = section.body
    base = section.body_start
    covered: list[tuple[int, int]] = []
    hits: list[RuleHit] = []

    def overlaps(start: int, end: int) -> bool:
        return any(not (end <= cs or start >= ce) for cs, ce in covered)

    def emit(rel_op, value_min, value_max, unit_min, unit_max, value_text, start, end) -> None:
        covered.append((start, end))
        hits.append(
            RuleHit(
                kind="fact",
                extractor=EXTRACTOR,
                section_path=section.path,
                quote=body[start:end],
                char_start=base + start,
                char_end=base + end,
                confidence=0.95,
                fact_kind=FACT_KIND,
                label="Phạm vi đo",
                rel_op=rel_op,
                value_min=value_min,
                value_max=value_max,
                unit=unit_max or unit_min,
                unit_min=unit_min,
                unit_max=unit_max,
                value_text=value_text,
            )
        )

    for match in _TU_DEN_RE.finditer(body):
        if overlaps(match.start(), match.end()):
            continue
        low, high = _parse_num(match.group("lo")), _parse_num(match.group("hi"))
        if low is None or high is None:
            continue
        lo_unit, hi_unit = match.group("lo_unit"), match.group("hi_unit")
        # QTKĐ có thể trộn đơn vị hai đầu (1.190: "-700 mbar đến 700 bar") — giữ
        # riêng từng đơn vị để quy đổi SI đúng từng biên.
        unit = hi_unit or lo_unit
        if hi_unit and lo_unit and hi_unit != lo_unit:
            lo_text, hi_text = (
                f"{_clean_num(match.group('lo'))} {lo_unit}",
                (f"{_clean_num(match.group('hi'))} {hi_unit}"),
            )
        else:
            lo_text = f"{_clean_num(match.group('lo'))} {unit}"
            hi_text = f"{_clean_num(match.group('hi'))} {unit}"
        emit(
            "range",
            low,
            high,
            lo_unit or unit,
            hi_unit or unit,
            f"từ {lo_text} đến {hi_text}",
            match.start(),
            match.end(),
        )

    for match in _PAREN_RE.finditer(body):
        if overlaps(match.start(), match.end()):
            continue
        parsed = vnnum.parse_range(_normalize_signs(match.group("inner")))
        if parsed is None:
            continue
        unit = match.group("unit")
        emit(
            "range",
            parsed.low,
            parsed.high,
            unit,
            unit,
            f"({match.group('inner').strip()}) {unit}",
            match.start(),
            match.end(),
        )

    for match in _DEN_ONLY_RE.finditer(body):
        if overlaps(match.start(), match.end()):
            continue
        high = _parse_num(match.group("num"))
        if high is None:
            continue
        unit = match.group("unit")
        emit(
            "range",
            None,
            high,
            unit,
            unit,
            f"đến {_clean_num(match.group('num'))} {unit}",
            match.start(),
            match.end(),
        )

    return hits
