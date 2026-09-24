"""§4 Bảng 2 Phương tiện kiểm định → ``procedure_standard`` (spec §7).

Bảng 2 thường mô tả bằng quan hệ chứ không bằng số ("lớn hơn áp suất chỉnh đặt
của van đồng thời nhỏ hơn 1,5 lần ..."), nên giữ nguyên dạng text: ``range_text``
và ``accuracy_text``. Một QTKĐ có thể tách Bảng 2 thành hai bảng ("Bảng 2" và
"Bảng 2 (kết thúc)") — luật gom mọi bảng trong mục. Bảng không có cột tên → rỗng.
"""

from __future__ import annotations

from knowledge import vnnum
from knowledge.rules.markdown_tables import MarkdownTable, parse_tables
from knowledge.rules.sections import find_section, split_sections
from knowledge.rules.types import RuleHit

EXTRACTOR = "rule:bang2.v1"
SECTION_KEYWORDS = ("phương tiện kiểm định",)

_ACCURACY_KEYS = ("cấp chính xác", "sai số", "độ chính xác", "độ không đảm bảo")


def _norm(text: str) -> str:
    return vnnum.normalize_spaces(text).lower()


def _column(headers: tuple[str, ...], *needles: str) -> int | None:
    for index, header in enumerate(headers):
        haystack = _norm(header)
        if any(needle in haystack for needle in needles):
            return index
    return None


def _parse_ord(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def _table_hits(table: MarkdownTable, section_path: str) -> list[RuleHit]:
    name_idx = _column(table.headers, "tên")
    if name_idx is None:
        return []
    tt_idx = _column(table.headers, "tt")
    range_idx = _column(table.headers, "phạm vi")
    accuracy_idx = _column(table.headers, *_ACCURACY_KEYS)

    hits: list[RuleHit] = []
    for row in table.rows:
        if name_idx >= len(row.cells) or not row.cells[name_idx].strip():
            continue
        name = row.cells[name_idx].strip()
        range_text = (
            row.cells[range_idx].strip()
            if range_idx is not None and range_idx < len(row.cells)
            else ""
        )
        accuracy_text = (
            row.cells[accuracy_idx].strip()
            if accuracy_idx is not None and accuracy_idx < len(row.cells)
            else ""
        )
        tt_value = (
            row.cells[tt_idx].strip() if tt_idx is not None and tt_idx < len(row.cells) else ""
        )
        hits.append(
            RuleHit(
                kind="standard",
                extractor=EXTRACTOR,
                section_path=section_path,
                quote=row.raw.strip(),
                char_start=row.start,
                char_end=row.end,
                confidence=0.95,
                ord=_parse_ord(tt_value),
                name_vi=name,
                range_text=range_text or None,
                accuracy_text=accuracy_text or None,
            )
        )
    return hits


def extract(text: str) -> list[RuleHit]:
    """Rút danh mục phương tiện kiểm định từ Bảng 2; rỗng nếu không khớp."""
    sections = split_sections(text)
    section = find_section(sections, *SECTION_KEYWORDS)
    if section is None:
        return []
    hits: list[RuleHit] = []
    for table in parse_tables(section.body, base_offset=section.body_start):
        hits.extend(_table_hits(table, section.path))
    return hits
