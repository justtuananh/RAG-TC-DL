"""Biểu 4 (danh mục tiêu chuẩn, quy trình) và Biểu 1 (lĩnh vực kiểm định, hiệu chuẩn)."""

from __future__ import annotations

import re

from catalogs.codes import parse_codes
from catalogs.rows import Group, Inherit, column_map, get, iter_rows, slug, to_int
from catalogs.tables import Row, cell_text, row_quote
from catalogs.types import CapabilityDraft, ProcedureCatalogDraft

PROCEDURE_SPEC = {
    "ord": "tt",
    "code": "so_hieu_tieu_chuan",
    "title": "ten_tieu_chuan",
    "issuer": "cap_ban_hanh",
    "note": "ghi_chu",
}
CAPABILITY_SPEC = {
    "ord": "tt",
    "name": "ten_dai_luong",
    "parameters": "tham_so",
    "procedures": "ky_hieu_tieu_chuan",
    "inspectors": "so_luong",
}
RECOGNITION_SPEC = {"bo_sung_moi": "bo_sung_moi", "mo_rong": "mo_rong", "duy_tri": "duy_tri"}
_YEAR_RE = re.compile(r"(?:19|20)\d{2}")


def _procedure(
    row: Row, mapping, group: Group, domain: str | None, inherit: Inherit
) -> ProcedureCatalogDraft:
    inherited: list[str] = []
    code_text = cell_text(get(row, mapping, "code"), " / ")
    note = cell_text(get(row, mapping, "note"))
    year = _YEAR_RE.search(note)
    return ProcedureCatalogDraft(
        ord=to_int(cell_text(get(row, mapping, "ord"))),
        domain=domain,
        group_code=group.code,
        group_title=group.title,
        code_text=code_text,
        codes=parse_codes(code_text),
        title=cell_text(get(row, mapping, "title")),
        issuer=inherit.resolve("issuer", cell_text(get(row, mapping, "issuer")), inherited) or None,
        year_issued=int(year.group(0)) if year else None,
        inherited=inherited,
        quote=row_quote(row),
    )


def parse_procedures(
    rows: list[Row], header: Row, domain: str | None
) -> list[ProcedureCatalogDraft]:
    mapping = column_map(header, PROCEDURE_SPEC)
    group, inherit = Group(), Inherit()
    return [
        _procedure(row, mapping, group, domain, inherit)
        for kind, row in iter_rows(rows, group)
        if kind == "data"
    ]


def _recognition(row: Row, columns: dict[str, int]) -> str | None:
    for name, index in columns.items():
        if index < len(row) and cell_text(row[index]).casefold() == "x":
            return name
    return None


def _capability(row: Row, mapping, recognition: dict[str, int], group: Group) -> CapabilityDraft:
    codes = [code for line in get(row, mapping, "procedures") for code in parse_codes(line)]
    return CapabilityDraft(
        ord=to_int(cell_text(get(row, mapping, "ord"))),
        group_code=group.code,
        group_title=group.title,
        name=cell_text(get(row, mapping, "name")),
        parameters=list(get(row, mapping, "parameters")),
        procedure_codes=codes,
        inspector_count=to_int(cell_text(get(row, mapping, "inspectors"))),
        recognition=_recognition(row, recognition),
        quote=row_quote(row),
    )


def parse_capabilities(rows: list[Row], header: Row) -> list[CapabilityDraft]:
    mapping = column_map(header, CAPABILITY_SPEC)
    # Tiêu đề 2 tầng: dòng dưới ghi "Bổ sung mới | Mở rộng | Duy trì".
    sub = next((row for row in rows[:2] if any("duy_tri" in slug(cell_text(c)) for c in row)), None)
    recognition = column_map(sub, RECOGNITION_SPEC) if sub is not None else {}
    body = [row for row in rows if row is not sub]
    group = Group()
    return [
        _capability(row, mapping, recognition, group)
        for kind, row in iter_rows(body, group)
        if kind == "data"
    ]
