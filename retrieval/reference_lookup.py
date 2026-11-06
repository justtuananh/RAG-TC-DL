"""Resolve explicit appendix topics and replacement declarations from source text.

These front-matter/appendix labels may be deliberately absent from the semantic
index. Only loaded document stems are read; no external file path is accepted.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from core.settings_loader import get_settings
from retrieval import doc_titles
from retrieval.normalize import fold

_CODE = re.compile(r'(?<!\d)\d\.\d{3}(?!\d)')
_APPENDIX = re.compile(r'\bphu luc\s+([a-z])\b')


def _replacement_request(q: str) -> bool:
    return bool(re.search(r'\b(?:thay the|thay bang|duoc thay)\b', q))


def is_reference_query(question: str) -> bool:
    q = fold(question)
    if not _CODE.search(q):
        return False
    if _replacement_request(q):
        return True
    labels = _APPENDIX.findall(q)
    return bool(
        len(set(labels)) == 1
        and not re.search(r'phu luc\s+[a-z]\s*(?:va|,|/)\s*[a-z]\b', q)
        and any(term in q for term in ('noi dung gi', 'noi dung chinh', 'la gi', 've gi'))
        and not any(term in q for term in ('cong thuc', 'he so', 'dieu kien', 'tinh toan'))
    )


def _hit(stem: str, section: str, text: str) -> dict:
    payload = dict(
        file_stem=stem,
        section_path=section,
        text=text,
        kind='paragraph',
        chunk_id=hashlib.sha256(f'{stem}\0{section}\0{text}'.encode()).hexdigest()[:16],
    )
    return dict(payload=payload, parent_payload=payload, rerank_score=1.0, reference_match=True)


def lookup(question: str, stems: set[str] | frozenset[str]) -> list[dict]:
    if not is_reference_query(question):
        return []
    q = fold(question)
    numbers = set(_CODE.findall(q))
    appendix = _APPENDIX.search(q)
    root = Path(get_settings().paths.markdown_dir)
    hits = []
    for stem in sorted(stems):
        # Stems are catalog data, but must still be basenames.
        if Path(stem).name != stem:
            continue
        try:
            text = (root / f'{stem}.md').read_text(encoding='utf-8')
        except OSError:
            continue
        if _replacement_request(q):
            for paragraph in re.split(r'\n\s*\n', text[:12000]):
                normalized = fold(paragraph)
                if (
                    'thay the' in normalized
                    and len(_CODE.findall(normalized)) >= 2
                    and numbers.intersection(_CODE.findall(normalized))
                ):
                    title = doc_titles.parse_title(text.splitlines()[:40])
                    hits.append(_hit(stem, 'Lời nói đầu', f'{title}\n\n{paragraph.strip()}'))
        elif appendix and numbers.intersection(_CODE.findall(stem)):
            lines = text.splitlines()
            for i, line in enumerate(lines):
                heading = re.sub(r'^#+\s*', '', fold(line))
                if heading != f'phu luc {appendix.group(1)}' or not line.startswith('#'):
                    continue
                following = []
                title_started = False
                for next_line in lines[i + 1 :]:
                    stripped = next_line.strip()
                    if not stripped:
                        if title_started:
                            break
                        continue
                    if stripped.startswith('#') and _APPENDIX.search(fold(stripped)):
                        break
                    if fold(stripped.lstrip('# ')) in ('(quy dinh)', '(tham khao)'):
                        following.append(stripped)
                        continue
                    if '|' in stripped or '$' in stripped or re.match(r'^[A-Z]\.\d', stripped):
                        break
                    following.append(stripped)
                    title_started = True
                if title_started:
                    hits.append(
                        _hit(stem, line.lstrip('# ').strip(), '\n\n'.join([line] + following))
                    )
                break
    covered = set()
    for hit in hits:
        covered.update(_CODE.findall(hit['payload']['file_stem']))
        covered.update(_CODE.findall(hit['payload']['text']))
    return hits if numbers <= covered else []
