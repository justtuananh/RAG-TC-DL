"""§2 Thuật ngữ và định nghĩa → ``term`` (spec §7).

Mẫu: ``Tên tiếng Việt (English): là ...``. Chỉ nhận dòng có định nghĩa bắt đầu
bằng ``là``; dòng khác (câu dẫn, CHÚ THÍCH) bị bỏ. QTKĐ không có mục Thuật ngữ
(ví dụ 1.159 có §2 Tài liệu viện dẫn) → rỗng.
"""

from __future__ import annotations

import re

from knowledge.rules.sections import find_section, split_sections
from knowledge.rules.types import RuleHit

EXTRACTOR = "rule:thuatngu.v1"
SECTION_KEYWORDS = ("thuật ngữ",)

_TERM_RE = re.compile(
    r"^(?P<vi>[^()]+?)\s*\((?P<en>[^()]+)\)\s*:\s*(?P<def>.+?)\s*$",
    re.IGNORECASE,
)


def _line_offsets(body: str) -> list[tuple[str, int, int]]:
    """(dòng, offset đầu dòng trong body, offset kết thúc) cho từng dòng."""
    result: list[tuple[str, int, int]] = []
    offset = 0
    for line in body.split("\n"):
        result.append((line, offset, offset + len(line)))
        offset += len(line) + 1
    return result


def extract(text: str) -> list[RuleHit]:
    """Rút các cặp thuật ngữ/định nghĩa từ §2; rỗng nếu không khớp."""
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
        match = _TERM_RE.match(stripped)
        if match is None:
            continue
        definition = match.group("def").strip()
        if not definition.lower().startswith("là"):
            continue
        leading = len(line) - len(line.lstrip())
        quote_start = start + leading
        hits.append(
            RuleHit(
                kind="term",
                extractor=EXTRACTOR,
                section_path=section.path,
                quote=stripped,
                char_start=base + quote_start,
                char_end=base + quote_start + len(stripped),
                confidence=0.95,
                term_vi=match.group("vi").strip(),
                term_en=match.group("en").strip(),
                definition=definition,
            )
        )
    return hits
