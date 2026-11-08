"""Look up one source cell using explicit accuracy-class and range fields.

This parser compares table labels; it never evaluates formulas or converts units.
Unsupported structures and multiple matches retain the normal answer path.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from retrieval.normalize import fold

_NUMBER = r'-?\d+(?:[,.]\d+)?'
_END_NUMBER = r'(?!(?:[,.]\d)|[\d./eE])'
_TABLE = re.compile(r'(?m)^[ \t]*\|.*(?:\n[ \t]*\|.*)*')
_SEPARATOR = re.compile(r'^:?-{3,}:?$')


def _unaccent(text: str) -> str:
    decomposed = unicodedata.normalize('NFKD', text).replace('đ', 'd').replace('Đ', 'D')
    return ' '.join(''.join(c for c in decomposed if not unicodedata.combining(c)).split())


def _number(value: str) -> Decimal:
    return Decimal(value.replace(',', '.'))


def _fields(question: str) -> tuple[str, str, str, str] | None:
    q = _unaccent(question)
    classes = re.findall(
        r'\bcap chinh xac\s*(?:la\s*|:\s*)?(' + _NUMBER + ')' + _END_NUMBER, q, re.IGNORECASE
    )
    limits = re.findall(
        r'\bgioi han do(?: tren)?\s*(?:(?:khoang|la|bang)\s*|:\s*)?(' + _NUMBER + r')\s*([a-z]+)\b',
        q,
        re.IGNORECASE,
    )
    requested_units = {
        unit
        for label, unit in [('phut', 'min'), ('min', 'min'), ('giay', 's'), ('gio', 'h')]
        if re.search(r'\b' + label + r'\b', q, re.IGNORECASE)
    }
    if len(classes) != 1 or len(limits) != 1 or len(requested_units) != 1:
        return None
    value, unit = limits[0]
    return classes[0], value, unit, requested_units.pop()


def _quantity_matches(question: str, caption: str) -> bool:
    words = re.findall(r'\w+', fold(question))
    phrases = {' '.join(words[i : i + 3]) for i in range(len(words) - 2)}
    phrases -= {'cap chinh xac', 'gioi han do', 'do chinh xac'}
    title = ' '.join(re.findall(r'\w+', fold(caption)))
    return any(re.search(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', title) for phrase in phrases)


def _row_contains(label: str, value: Decimal) -> bool | None:
    label = fold(label)
    interval = re.fullmatch(r'tu\s+(' + _NUMBER + r')\s+den\s+(' + _NUMBER + ')', label)
    if interval:
        low, high = map(_number, interval.groups())
        return low <= value <= high if low <= high else None
    above = re.fullmatch(r'lon hon\s+(' + _NUMBER + ')', label)
    return value > _number(above.group(1)) if above else None


def _cell(
    question: str, text: str, match: re.Match, fields: tuple[str, str, str, str]
) -> tuple[str, str, str, str] | None:
    cls, limit, limit_unit, output_unit = fields
    rows = [
        [cell.strip() for cell in line.strip().strip('|').split('|')]
        for line in match.group().splitlines()
    ]
    n = len(rows[0])
    if n < 3 or len(rows) < 4 or any(len(row) != n for row in rows):
        return None
    top, separator, sub = rows[:3]
    source_unit = re.fullmatch(r'gioi han do\s*,?\s*/\s*([a-z]+)', _unaccent(top[0]), re.IGNORECASE)
    if source_unit is None or source_unit.group(1) != limit_unit:
        return None
    if not fold(top[1]).startswith('cap chinh xac') or '(%)' not in top[1] or any(top[2:]):
        return None
    if not all(_SEPARATOR.fullmatch(cell) for cell in separator) or sub[0]:
        return None
    if not all(re.fullmatch(_NUMBER, value) for value in sub[1:]):
        return None
    class_values = [_number(value) for value in sub[1:]]
    if len(set(class_values)) != len(class_values) or _number(cls) not in class_values:
        return None
    prefix = [
        block.strip() for block in re.split(r'\n\s*\n', text[: match.start()]) if block.strip()
    ][-3:]
    units = [
        re.fullmatch(r'(?i:(?:#+\s*)?Don vi:)\s*(min|s|h)', _unaccent(block)) for block in prefix
    ]
    units = [unit.group(1).lower() for unit in units if unit is not None]
    captions = [block for block in prefix if re.match(r'^(?:#+\s*)?Bảng\s+\d+\b', block)]
    if units != [output_unit] or len(captions) != 1 or not _quantity_matches(question, captions[0]):
        return None
    row_matches = [_row_contains(row[0], _number(limit)) for row in rows[3:]]
    if any(value is None for value in row_matches):
        return None
    matching_rows = [row for row, matched in zip(rows[3:], row_matches, strict=True) if matched]
    if len(matching_rows) != 1:
        return None
    row = matching_rows[0]
    cell = row[class_values.index(_number(cls)) + 1]
    if not re.fullmatch(_NUMBER, cell):
        return None
    return cell, row[0], captions[0], top[0].rsplit('/', 1)[1].strip()


def answer(question: str, results: list[dict]) -> str | None:
    fields = _fields(question)
    if fields is None:
        return None
    named = set(re.findall(r'\bqtkd\s*(\d\.\d{3})(?!\d)', fold(question)))
    if len(named) > 1:
        return None
    matches = []
    seen = set()
    for index, hit in enumerate(results, 1):
        payload = hit['payload']
        if named and not named.intersection(
            re.findall(r'(?<!\d)\d\.\d{3}(?!\d)', payload['file_stem'])
        ):
            continue
        text = (hit.get('parent_payload') or payload)['text']
        key = (payload['file_stem'], payload['section_path'], text)
        if key in seen:
            continue
        seen.add(key)
        for table in _TABLE.finditer(text):
            cell = _cell(question, text, table, fields)
            if cell is not None:
                matches.append((index, payload['file_stem'], text, cell))
    if len(matches) != 1:
        return None
    index, stem, text, (value, row_label, caption, source_limit_unit) = matches[0]
    cls, limit, limit_unit, output_unit = fields
    return (
        f'- **{stem}**: Với cấp chính xác **{cls}**, giới hạn đo trên **{limit} {source_limit_unit}** '
        f'(hàng **{row_label}**), giá trị tra bảng là **{value} {output_unit}** [{index}].\n\n'
        f'{caption}\n\n{text} [{index}]'
    )
