"""Compact source-bound equipment table views for ranking, never for display."""

from __future__ import annotations

import re
import unicodedata

_TT = re.compile(r"^(TT|STT|No\.?|Số TT)$", re.IGNORECASE)
_SEQ = re.compile(r"^\d+(\.\d+)*\.?$")
_SEP = re.compile(r"^:?-{3,}:?$")


def fold(text: str) -> str:
    decomposed = unicodedata.normalize('NFKD', text.casefold()).replace('đ', 'd')
    return ''.join(c for c in decomposed if not unicodedata.combining(c))


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip('|').split('|')]


def _valid(rows: list[list[str]]) -> bool:
    n = len(rows[0])
    if n < 3 or any(len(row) != n for row in rows):
        return False
    sep = next((i for i, row in enumerate(rows) if all(_SEP.fullmatch(c) for c in row)), None)
    first = next((i for i, row in enumerate(rows) if _SEQ.fullmatch(row[0])), None)
    if sep is None or first is None or not 0 < sep < first:
        return False
    return all(
        (bool(_SEQ.fullmatch(row[0])) and bool(row[1])) or (not row[0] and not row[1])
        for row in rows[first:]
    )


def focus_equipment_tables(text: str, query: str) -> str:
    """Ranking-only view of equipment rows named by a shared three-word phrase.

    Keep every column and continuation row of a matching item. Ambiguous or
    unsupported table structures keep the original text; displayed sources never
    use this view.
    """
    words = re.findall(r'\w+', fold(query))
    phrases = {' '.join(words[i : i + 3]) for i in range(len(words) - 2)}
    if not phrases:
        return text
    focused = []
    for match in re.finditer(r'(?m)^\s*\|.*(?:\n[ \t]*\|.*)*', text):
        lines = match.group().strip().splitlines()
        rows = [_cells(line) for line in lines]
        if not rows or not _TT.fullmatch(rows[0][0]) or not _valid(rows):
            continue
        first = next((i for i, row in enumerate(rows) if _SEQ.fullmatch(row[0])), None)
        if first is None:
            continue
        selected = []
        keep = False
        for i in range(first, len(rows)):
            row = rows[i]
            if _SEQ.fullmatch(row[0]):
                name = ' '.join(re.findall(r'\w+', fold(row[1])))
                keep = any(re.search(r'(?<!\w)' + re.escape(p) + r'(?!\w)', name) for p in phrases)
            if keep:
                selected.append(lines[i])
        if selected:
            focused.append('\n'.join(lines[:first] + selected))
    return '\n\n'.join(focused) if focused else text
