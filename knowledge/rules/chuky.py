"""§7 (hoặc §6) Xử lý chung → ``calibration_interval`` (spec §7).

Mẫu: ``Chu kỳ kiểm định của <X> là N tháng|năm`` hoặc dạng rút gọn không có "là"
``Chu kỳ kiểm định: N tháng|năm`` (K10). Giữ nguyên văn giá trị ("12 tháng",
"01 năm") - không quy đổi, không tự tính hạn hiệu lực (P2). Không khớp mẫu →
rỗng.
"""

from __future__ import annotations

import re

from knowledge import vnnum
from knowledge.rules.sections import find_section, split_sections
from knowledge.rules.types import RuleHit

EXTRACTOR = "rule:chuky.v1"
FACT_KIND = "calibration_interval"
SECTION_KEYWORDS = ("xử lý chung",)

_INTERVAL_RE = re.compile(
    r"chu\s*kỳ\s*kiểm\s*định[^.;\n]*?(?:\s+là\s*:?\s*|:\s*)(?P<val>[^.;\n]+)",
    re.IGNORECASE,
)


def _line_offsets(body: str) -> list[tuple[str, int, int]]:
    result: list[tuple[str, int, int]] = []
    offset = 0
    for line in body.split("\n"):
        result.append((line, offset, offset + len(line)))
        offset += len(line) + 1
    return result


def extract(text: str) -> list[RuleHit]:
    """Rút chu kỳ kiểm định từ §7/§6; rỗng nếu không khớp."""
    sections = split_sections(text)
    section = find_section(sections, *SECTION_KEYWORDS)
    if section is None:
        return []

    base = section.body_start
    hits: list[RuleHit] = []
    for line, start, _end in _line_offsets(section.body):
        stripped = line.strip()
        if not stripped:
            continue
        match = _INTERVAL_RE.search(stripped)
        if match is None:
            continue
        value_text = match.group("val").strip()
        parsed = vnnum.parse_quantity(value_text)
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
                label="Chu kỳ kiểm định",
                rel_op=parsed.rel_op if parsed else "=",
                value_min=parsed.value_min if parsed else None,
                value_max=parsed.value_max if parsed else None,
                unit=parsed.unit if parsed else None,
                value_text=value_text,
            )
        )
    return hits
