"""§3 Bảng 1 Các phép kiểm định → ``inspection_step`` (spec §7).

Đọc bảng Markdown header hai tầng, lấy tên phép, mục QTKĐ tương ứng, và chế độ
kiểm định (Ban đầu / Định kỳ / Sau sửa chữa) nơi ô đánh dấu ``+``. Dòng không có
tên phép bị bỏ; bảng không nhận diện được cột tên → rỗng.
"""

from __future__ import annotations

from knowledge import vnnum
from knowledge.rules.markdown_tables import MarkdownTable, parse_tables
from knowledge.rules.sections import find_section, split_sections
from knowledge.rules.types import RuleHit

EXTRACTOR = "rule:bang1.v1"
FACT_KIND = "inspection_step"
SECTION_KEYWORDS = ("các phép kiểm định",)

# (khóa trong header đã chuẩn hóa, nhãn hiển thị)
_MODE_KEYS = (
    ("ban đầu", "Ban đầu"),
    ("định kỳ", "Định kỳ"),
    ("sau sửa chữa", "Sau sửa chữa"),
)


def _norm(text: str) -> str:
    return vnnum.normalize_spaces(text).lower()


def _column(headers: tuple[str, ...], *needles: str) -> int | None:
    for index, header in enumerate(headers):
        haystack = _norm(header)
        if any(needle in haystack for needle in needles):
            return index
    return None


def _table_hits(table: MarkdownTable, section_path: str) -> list[RuleHit]:
    name_idx = _column(table.headers, "tên phép kiểm định", "tên")
    if name_idx is None:
        return []
    ref_idx = _column(table.headers, "theo điều")
    mode_cols = [
        (index, label)
        for index, header in enumerate(table.headers)
        for needle, label in _MODE_KEYS
        if needle in _norm(header)
    ]

    hits: list[RuleHit] = []
    for row in table.rows:
        if name_idx >= len(row.cells) or not row.cells[name_idx].strip():
            continue
        modes = [
            label
            for index, label in mode_cols
            if index < len(row.cells) and row.cells[index].strip() == "+"
        ]
        ref = row.cells[ref_idx].strip() if ref_idx is not None and ref_idx < len(row.cells) else ""
        hits.append(
            RuleHit(
                kind="fact",
                extractor=EXTRACTOR,
                section_path=section_path,
                quote=row.raw.strip(),
                char_start=row.start,
                char_end=row.end,
                confidence=0.95,
                fact_kind=FACT_KIND,
                label=row.cells[name_idx].strip(),
                rel_op="=",
                value_text=ref or None,
                condition_text="Chế độ: " + ", ".join(modes) if modes else None,
            )
        )
    return hits


def extract(text: str) -> list[RuleHit]:
    """Rút các bước kiểm định từ Bảng 1; rỗng nếu không có mục/bảng."""
    sections = split_sections(text)
    section = find_section(sections, *SECTION_KEYWORDS)
    if section is None:
        return []
    hits: list[RuleHit] = []
    for table in parse_tables(section.body, base_offset=section.body_start):
        hits.extend(_table_hits(table, section.path))
    return hits
