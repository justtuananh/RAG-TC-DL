"""Document-scoped quotations selected by one batched cross encoder."""

from __future__ import annotations

import logging
import re
from itertools import zip_longest

from core.settings_loader import get_settings
from query.multi_document import DocumentGroup
from reranking import reranker
from retrieval import doc_titles
from retrieval.normalize import semantic_query

logger = logging.getLogger(__name__)


def evidence_units(text: str) -> list[str]:
    """Keep paragraphs intact, tables/formulas with adjacent qualifications."""
    return [quote for _, quote in _evidence_pairs(text)]


def _evidence_pairs(text: str) -> list[tuple[str, str]]:
    """Rank compact units; retain adjacent qualifications in displayed quotations."""
    blocks = [b.strip() for b in re.split(r'\n\s*\n', text) if b.strip()]
    units = []
    seen = set()
    for i, block in enumerate(blocks):
        if block.startswith('#') and '\n' not in block:
            continue
        if any(line.lstrip().startswith('|') for line in block.splitlines()) or '$' in block:
            start = max(0, i - 1)
            if start > 0 and re.match(r'^(?:#+\s*|Bảng\s)', blocks[start]):
                start -= 1
            block = '\n\n'.join(blocks[start : i + 2])
        ranking_text = block
        if re.match(r'^(?:[-*+] |\d+[.)] )', blocks[i]):
            intro = i - 1
            while intro >= 0 and re.match(r'^(?:[-*+] |\d+[.)] )', blocks[intro]):
                intro -= 1
            if intro >= 0 and blocks[intro].endswith(':'):
                block = blocks[intro] + '\n\n' + block
        if i + 1 < len(blocks) and re.match(r'^CHÚ THÍCH\b', blocks[i + 1], re.IGNORECASE):
            if blocks[i + 1] not in block:
                block += '\n\n' + blocks[i + 1]
        if ranking_text not in seen:
            units.append((ranking_text, block))
            seen.add(ranking_text)
    return units


def answer(
    question: str, results: list[dict], groups: list[DocumentGroup], *, allow_single: bool = False
) -> str | None:
    """Return source-bound quotes, or None to retain generation fallback."""
    cfg = get_settings().llm.multi_document
    if not cfg.extractive_enabled or not groups or (len(groups) < 2 and not allow_single):
        return None
    pools = []
    for group in groups:
        sources = []
        for pos in group.positions:
            hit = results[pos]
            parent = hit.get('parent_payload') or hit['payload']
            units = _evidence_pairs(parent['text'])
            anchors = hit.get('anchor_texts') or [hit['payload']['text']]
            units.sort(
                key=lambda unit: (
                    not any(anchor[:80] in unit[0] for anchor in anchors if anchor.strip())
                )
            )
            sources.append(
                [
                    (group.stem, pos, quote, ranking_text)
                    for ranking_text, quote in units[: cfg.evidence_candidates_per_source]
                ]
            )
        pools.append([item for row in zip_longest(*sources) for item in row if item is not None])
    candidates = [item for row in zip_longest(*pools) for item in row if item is not None]
    candidates = candidates[: cfg.evidence_max_candidates]
    if not candidates:
        return None
    documents = [
        f"{stem} — {results[pos]['payload']['section_path']}\n{text}"
        for stem, pos, _, text in candidates
    ]
    try:
        scores = reranker.score_documents(semantic_query(question), documents)
        if len(scores) != len(candidates):
            raise ValueError('Incomplete evidence scores')
    except Exception:
        logger.warning('Evidence ranking unavailable; using generation fallback', exc_info=True)
        return None
    entries = []
    supported = 0
    for group in groups:
        ranked = sorted(
            [
                (score, pos, text)
                for (stem, pos, text, _), score in zip(candidates, scores, strict=True)
                if stem == group.stem
            ],
            reverse=True,
        )
        if not ranked:
            entries.append(f'- **{group.stem}**: Chưa tìm thấy đủ bằng chứng để trả lời.')
            continue
        floor = max(cfg.evidence_min_score, ranked[0][0] * cfg.evidence_relative_floor)
        chosen: list[tuple[int, str]] = []
        for score, pos, text in ranked:
            if score < floor or any(text in previous for _, previous in chosen):
                continue
            chosen.append((pos, text))
            if len(chosen) >= cfg.evidence_per_document:
                break
        if not chosen:
            entries.append(f'- **{group.stem}**: Chưa tìm thấy đủ bằng chứng để trả lời.')
            continue
        supported += 1
        title = doc_titles.title_for(group.stem)
        number = re.search(r'\d+\.\d+', group.stem)
        label = f"QTKĐ {number.group()} ({title})" if number else title or group.stem
        quotes = '\n\n'.join(f'{text} [{pos + 1}]' for pos, text in chosen)
        entries.append(f'- **{label}**:\n\n{quotes}')
    return '\n\n'.join(entries) if supported else None


def reference_answer(results: list[dict]) -> str | None:
    """Exact structural matches need no model to rediscover the selected heading."""
    if not results or not all(r.get('reference_match') for r in results):
        return None
    entries = []
    for index, result in enumerate(results, 1):
        payload = result['payload']
        entries.append(f"- **{payload['file_stem']}**:\n\n{payload['text']} [{index}]")
    return '\n\n'.join(entries)
