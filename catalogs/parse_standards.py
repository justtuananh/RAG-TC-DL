"""Biểu 3: danh mục chuẩn mẫu, phương tiện đo, phương tiện thử nghiệm."""

from __future__ import annotations

import re

from catalogs.rows import Group, Inherit, column_map, get, iter_rows, to_int
from catalogs.tables import Row, cell_text, row_quote
from catalogs.types import LabStandardDraft

HEADER_SPEC = {
    "ord": "tt",
    "name": "ten_chuan_mau",
    "model": "ky_hieu",
    "serial": "so_hieu",
    "characteristics": "dac_tinh",
    "interval": "chu_ky",
    "last_calibration": "ngay_va_noi",
    "usage": "su_dung",
}
_INTERVAL_RE = re.compile(r"^(?P<n>\d+)\s*(?P<unit>năm|tháng)$", re.IGNORECASE)
_LAST_RE = re.compile(r"^(?P<month>\d{1,2})\s*/\s*(?P<year>\d{4})\s*(?P<place>.*)$")
_FORM_RE = re.compile(r"Biểu\s*(\d+)\s*/\s*CN", re.IGNORECASE)
_SECTION_RE = re.compile(r"^(?:mục)?\s*(?:(?P<roman>[IVXLC]+)\s*\.\s*)?", re.IGNORECASE)


def interval_months(text: str | None) -> int | None:
    match = _INTERVAL_RE.match((text or "").strip())
    if match is None:
        return None
    number = int(match.group("n"))
    return number * 12 if match.group("unit").casefold() == "năm" else number


def usage_refs(text: str | None) -> list[tuple[str, str]]:
    """ "Biểu 1/CN Mục IV.1, 2, 3" → [("Biểu 1/CN", "IV.1"), ("Biểu 1/CN", "IV.2"), ...]."""
    if not text:
        return []
    forms = list(_FORM_RE.finditer(text))
    refs: list[tuple[str, str]] = []
    for index, form in enumerate(forms):
        end = forms[index + 1].start() if index + 1 < len(forms) else len(text)
        segment = text[form.end() : end].strip()
        section = _SECTION_RE.match(segment)
        roman = section.group("roman") if section else None
        for number in re.findall(r"\d+", segment[section.end() if section else 0 :]):
            refs.append((f"Biểu {form.group(1)}/CN", f"{roman}.{number}" if roman else number))
    return refs


def _standard(
    row: Row, mapping: dict[str, int], inherit: Inherit, warnings: list[str]
) -> LabStandardDraft:
    inherited: list[str] = []
    values = {
        name: inherit.resolve(name, cell_text(get(row, mapping, name), "\n"), inherited)
        for name in HEADER_SPEC
        if name != "ord"
    }
    ord_ = to_int(cell_text(get(row, mapping, "ord")))
    months = interval_months(values["interval"])
    if values["interval"] and months is None:
        warnings.append(
            f"TT {ord_}: chu kỳ '{values['interval']}' không ghi đơn vị năm/tháng; không suy ra số tháng."
        )
    last = _LAST_RE.match(values["last_calibration"] or "")
    return LabStandardDraft(
        ord=ord_,
        name=cell_text(values["name"].split("\n")),
        model=values["model"].strip() or None,
        serial=values["serial"].strip() or None,
        characteristics=values["characteristics"].strip() or None,
        interval_text=values["interval"] or None,
        interval_months=months,
        last_cal_text=values["last_calibration"] or None,
        last_cal_year=int(last.group("year")) if last else None,
        last_cal_month=int(last.group("month")) if last else None,
        last_cal_place=(last.group("place").strip() or None) if last else None,
        usage_text=values["usage"] or None,
        usage_refs=usage_refs(values["usage"]),
        inherited=inherited,
        quote=row_quote(row),
    )


def parse(rows: list[Row], header: Row, warnings: list[str]) -> list[LabStandardDraft]:
    mapping = column_map(header, HEADER_SPEC)
    inherit = Inherit()
    items: list[LabStandardDraft] = []
    for kind, row in iter_rows(rows, Group()):
        if kind == "data":
            items.append(_standard(row, mapping, inherit, warnings))
    return items
