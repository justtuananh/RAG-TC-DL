"""Luật dòng dùng chung cho mọi biểu NAS: cột theo tiêu đề, "nt", đề mục nhóm, dòng giữ chỗ."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from catalogs.tables import Cell, Row, cell_text

_ROMAN_RE = re.compile(r"^[IVXLC]+$")
_DIGITS_RE = re.compile(r"^\d+$")
_NT_VALUES = {"nt", "n.t", "như trên"}


def slug(text: str) -> str:
    from records.template import slugify

    return slugify(text)


def is_nt(text: str) -> bool:
    """Ô "nt"/"Nt"/"như trên": lấy giá trị ô cùng cột của dòng trên."""
    return text.strip().casefold().rstrip(".") in _NT_VALUES


def to_int(text: str | None) -> int | None:
    digits = re.sub(r"\D", "", text or "")
    return int(digits) if digits and _DIGITS_RE.match((text or "").strip()) else None


def column_map(header: Row, spec: dict[str, str]) -> dict[str, int]:
    """``{trường: chỉ số cột}``: cột đầu tiên có slug tiêu đề chứa từ khóa của trường."""
    slugs = [slug(cell_text(cell)) for cell in header]
    mapping: dict[str, int] = {}
    for name, keyword in spec.items():
        index = next(
            (i for i, s in enumerate(slugs) if keyword in s and i not in mapping.values()), None
        )
        if index is not None:
            mapping[name] = index
    return mapping


@dataclass
class Group:
    """Đề mục nhóm đang hiệu lực ("IV | PHƯƠNG TIỆN ĐO ÁP SUẤT")."""

    code: str | None = None
    title: str | None = None


@dataclass
class Inherit:
    """Giá trị đã phân giải của dòng trên theo từng trường, để thay cho "nt"."""

    previous: dict[str, str] = field(default_factory=dict)

    def resolve(self, name: str, text: str, inherited: list[str]) -> str:
        if text and is_nt(text):
            inherited.append(name)
            return self.previous.get(name, "")
        if text:
            self.previous[name] = text
        return text


def _filled(row: Row) -> list[int]:
    return [index for index, cell in enumerate(row) if cell_text(cell)]


def iter_rows(rows: list[Row], group: Group) -> Iterator[tuple[str, Row]]:
    """``("group"|"placeholder"|"data", dòng)``; cập nhật ``group`` khi gặp đề mục số La Mã."""
    for row in rows:
        filled = _filled(row)
        if not filled:
            continue
        first = cell_text(row[filled[0]])
        if filled[0] == 0 and _ROMAN_RE.match(first):
            group.code = first
            group.title = next((cell_text(row[i]) for i in filled[1:]), None)
            yield "group", row
        elif filled == [0] and _DIGITS_RE.match(first):
            yield "placeholder", row
        else:
            yield "data", row


def get(row: Row, mapping: dict[str, int], name: str) -> Cell:
    index = mapping.get(name)
    return row[index] if index is not None and index < len(row) else []
