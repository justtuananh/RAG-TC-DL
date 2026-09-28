"""Biểu 7: danh sách kiểm định viên."""

from __future__ import annotations

import re
from datetime import date

from catalogs.rows import Group, column_map, get, iter_rows
from catalogs.tables import Cell, Row, cell_text, row_quote
from catalogs.types import InspectorDraft

HEADER_SPEC = {
    "ord": "tt",
    "name": "ho_va_ten",
    "rank": "cap_bac",
    "education": "trinh_do",
    "specialization": "nganh",
    "fields": "linh_vuc",
    "card": "so_the",
}
_YEAR_RE = re.compile(r"^(?P<head>.*?)\s*(?P<year>(?:19|20)\d{2})$")
_DATE_RE = re.compile(r"(?P<d>\d{1,2})\s*/\s*(?P<m>\d{1,2})\s*/\s*(?P<y>\d{4})")


def _name_and_year(cell: Cell) -> tuple[str, int | None]:
    names: list[str] = []
    year: int | None = None
    for line in cell:
        match = _YEAR_RE.match(line)
        if match and year is None:
            year = int(match.group("year"))
            if match.group("head"):
                names.append(match.group("head"))
        else:
            names.append(line)
    return cell_text(names), year


def _fields(cell: Cell) -> list[str]:
    cleaned = (line.lstrip("-–• ").rstrip(";.,").strip() for line in cell)
    return [line for line in cleaned if line]


def _card(cell: Cell) -> tuple[str | None, date | None]:
    card_no: str | None = None
    issued: date | None = None
    for line in cell:
        match = _DATE_RE.search(line)
        if match and issued is None:
            issued = date(int(match.group("y")), int(match.group("m")), int(match.group("d")))
        elif card_no is None:
            card_no = line
    return card_no, issued


def _inspector(index: int, row: Row, mapping: dict[str, int]) -> InspectorDraft:
    name, year = _name_and_year(get(row, mapping, "name"))
    rank_lines = get(row, mapping, "rank")
    card_no, card_date = _card(get(row, mapping, "card"))
    ord_text = cell_text(get(row, mapping, "ord"))
    return InspectorDraft(
        ord=int(ord_text) if ord_text.isdigit() else index,
        name=name,
        birth_year=year,
        rank=rank_lines[0] if rank_lines else None,
        position=cell_text(rank_lines[1:]) or None,
        education=cell_text(get(row, mapping, "education")) or None,
        specialization=cell_text(get(row, mapping, "specialization")) or None,
        fields=_fields(get(row, mapping, "fields")),
        card_no=card_no,
        card_date=card_date,
        quote=row_quote(row),
    )


def parse(rows: list[Row], header: Row, warnings: list[str]) -> list[InspectorDraft]:
    mapping = column_map(header, HEADER_SPEC)
    data = [row for kind, row in iter_rows(rows, Group()) if kind == "data"]
    return [_inspector(index, row, mapping) for index, row in enumerate(data, start=1)]
