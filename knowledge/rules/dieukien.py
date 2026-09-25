"""§5.1 (hoặc §4.1) Điều kiện kiểm định → ``env_condition`` (spec §7).

Mẫu: ``Nhiệt độ môi trường: (A ± B) °C``, ``Độ ẩm tương đối: không lớn hơn 80 %``,
``Áp suất khí quyển: (A ± B) kPa``. Chỉ nhận dòng có nhãn bắt đầu bằng một trong
các điều kiện môi trường; dòng mô tả khác bị bỏ. Phần sau dấu phẩy (ví dụ "sự
thay đổi nhiệt độ không lớn hơn 2 oC/h") vào ``condition_text``.
"""

from __future__ import annotations

import re

from knowledge import vnnum
from knowledge.rules.sections import find_section, split_sections
from knowledge.rules.types import RuleHit

EXTRACTOR = "rule:dieukien.v1"
FACT_KIND = "env_condition"
SECTION_KEYWORDS = ("điều kiện kiểm định",)

_LABEL_KEYS = ("nhiệt độ", "độ ẩm", "áp suất khí quyển")
_UNIT = r"[A-Za-zµ%°/][\w%°/²³.]*"
_LE_RE = re.compile(r"không\s+(?:lớn|vượt)\s+hơn|≤|<=|Û", re.IGNORECASE)
_LE_NUM_RE = re.compile(rf"(?P<num>-?\d[\d\s.,]*)\s*(?P<unit>{_UNIT})?")


def _norm(text: str) -> str:
    return vnnum.normalize_spaces(text).lower()


def _line_offsets(body: str) -> list[tuple[str, int, int]]:
    result: list[tuple[str, int, int]] = []
    offset = 0
    for line in body.split("\n"):
        result.append((line, offset, offset + len(line)))
        offset += len(line) + 1
    return result


def _split_condition_text(expression: str) -> tuple[str, str | None]:
    """Tách ``value_text`` / ``condition_text`` tại dấu phẩy ĐẦU TIÊN không nằm
    giữa hai chữ số (K02): dấu phẩy thập phân kiểu Việt "(20,5 ± 2) °C" không
    phải ranh giới tách."""
    for index, char in enumerate(expression):
        if char != ",":
            continue
        if (
            0 < index < len(expression) - 1
            and expression[index - 1].isdigit()
            and expression[index + 1].isdigit()
        ):
            continue
        return expression[:index], expression[index + 1 :]
    return expression, None


def _parse_condition(expr: str) -> tuple[str | None, float | None, float | None, str | None]:
    """(rel_op, value_min, value_max, unit) từ biểu thức điều kiện."""
    normalized = vnnum.normalize_spaces(expr)
    if _LE_RE.search(normalized):
        match = _LE_NUM_RE.search(normalized)
        if match is None:
            return ("<=", None, None, None)
        return ("<=", None, vnnum.parse_number(match.group("num")), match.group("unit"))
    parsed = vnnum.parse_quantity(expr)
    if parsed is None:
        return (None, None, None, None)
    return (parsed.rel_op, parsed.value_min, parsed.value_max, parsed.unit)


def extract(text: str) -> list[RuleHit]:
    """Rút các điều kiện môi trường từ §5.1/§4.1; rỗng nếu không khớp."""
    sections = split_sections(text)
    section = find_section(sections, *SECTION_KEYWORDS)
    if section is None:
        return []

    base = section.body_start
    hits: list[RuleHit] = []
    for line, start, _end in _line_offsets(section.body):
        stripped = line.strip()
        if ":" not in stripped:
            continue
        body = re.sub(r"^[-*]\s+", "", stripped)
        label, _, expression = body.partition(":")
        label = label.strip()
        if not _norm(label).startswith(_LABEL_KEYS):
            continue
        expression = expression.strip().rstrip(";").strip()
        if not expression:
            continue
        value_text, condition_text = _split_condition_text(expression)
        value_text = value_text.strip()
        if condition_text is not None:
            condition_text = condition_text.strip().rstrip(";").strip() or None

        rel_op, value_min, value_max, unit = _parse_condition(value_text)
        leading = len(line) - len(line.lstrip())
        hits.append(
            RuleHit(
                kind="fact",
                extractor=EXTRACTOR,
                section_path=section.path,
                quote=stripped,
                char_start=base + start + leading,
                char_end=base + start + leading + len(stripped),
                confidence=0.95,
                fact_kind=FACT_KIND,
                label=label,
                rel_op=rel_op,
                value_min=value_min,
                value_max=value_max,
                unit=unit,
                value_text=value_text,
                condition_text=condition_text,
            )
        )
    return hits
