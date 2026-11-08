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
    view = '\n\n'.join(focused) if focused else text
    summary = verification_mode_summary(view)
    return summary + '\n\n' + view if summary else view


def verification_mode_summary(text: str) -> str:
    """Label cells of recognized verification-mode tables without guessing symbols."""
    summaries = []
    for match in re.finditer(r'(?m)^\s*\|.*(?:\n[ \t]*\|.*)*', text):
        rows = [_cells(line) for line in match.group().strip().splitlines()]
        if not rows or not _valid(rows) or len(rows[0]) != 6:
            continue
        if fold(rows[0][1]) != 'ten phep kiem dinh' or fold(rows[0][3]) != 'che do kiem dinh':
            continue
        first = next(i for i, row in enumerate(rows) if _SEQ.fullmatch(row[0]))
        labels = rows[first - 1][3:]
        if [fold(label) for label in labels] != ['ban dau', 'dinh ky', 'sau sua chua']:
            continue
        body = rows[first:]
        if any(
            not _SEQ.fullmatch(row[0]) or any(cell not in {'+', ''} for cell in row[3:])
            for row in body
        ):
            continue
        for row in body:
            name = row[1].split(' / ')[0]
            modes = [
                f'Chế độ kiểm định {label}: '
                + ('có áp dụng (+)' if value == '+' else 'không đánh dấu áp dụng (ô trống)')
                for label, value in zip(labels, row[3:], strict=True)
            ]
            summaries.append(f'- {name}: ' + '; '.join(modes) + '.')
    return '\n'.join(summaries)


_MODES = ('ban dau', 'dinh ky', 'sau sua chua')


def verification_mode_request(question: str) -> bool:
    """Only a single applicability question, not procedures or numerical criteria."""
    q = fold(question)
    modes = [mode for mode in _MODES if re.search(r'(?<!\w)' + mode + r'(?!\w)', q)]
    return (
        len(modes) == 1
        and any(term in q for term in ('ap dung', 'phai thuc hien', 'co thuc hien'))
        and not any(
            term in q
            for term in (
                'bao nhieu',
                'bao lau',
                'the nao',
                'cach ',
                'cong thuc',
                'thay the',
                'ap suat',
                'sai so',
                'nhiet do',
                'chu ky',
                'yeu cau',
            )
        )
    )


def lookup_verification_mode(text: str, question: str) -> str | None:
    """Resolve one exact source row/mode; keep complete table and explicit symbols."""
    if not verification_mode_request(question):
        return None
    q = fold(question)
    matches = []
    for match in re.finditer(r'(?m)^\s*\|.*(?:\n[ \t]*\|.*)*', text):
        table = match.group().strip()
        if not verification_mode_summary(table):
            continue
        lines = table.splitlines()
        rows = [_cells(line) for line in lines]
        first = next(i for i, row in enumerate(rows) if _SEQ.fullmatch(row[0]))
        selected = []
        for i in range(first, len(rows)):
            name = fold(rows[i][1].split(' / ')[0])
            if len(name.split()) >= 3 and re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', q):
                selected.append(i)
        if len(selected) != 1:
            continue
        i = selected[0]
        summary = verification_mode_summary('\n'.join(lines[:first] + [lines[i]]))
        name = fold(rows[i][1].split(' / ')[0])
        mode = next(mode for mode in _MODES if re.search(r'(?<!\w)' + mode + r'(?!\w)', q))
        declarations = [
            block.strip()
            for block in re.split(r'\n\s*\n', text)
            if name in fold(block)
            and mode in fold(block)
            and 'khong ap dung' in fold(block)
            and '|' not in block
        ]
        matches.append('\n\n'.join([summary, table] + declarations))
    return matches[0] if len(matches) == 1 else None
