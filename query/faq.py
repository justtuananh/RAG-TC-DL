"""Bộ câu hỏi - đáp án (bảng "| STT | Câu hỏi | Đáp án |"): trả đúng đáp án của câu khớp, không qua LLM.

Chạy trước mọi nhánh khác của chat. Mọi tài liệu đã nạp có bảng với cột câu hỏi và cột đáp án đều được
dùng; câu hỏi của người dùng được cross-encoder so với từng câu hỏi trong bộ. Câu khớp nhất đạt
``faq.min_score`` thì trả nguyên văn đáp án của nó (văn bản thường, không phải bảng); không đạt thì
trả ``None`` để pipeline RAG trả lời như thường.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from core.settings_loader import get_settings
from reranking import reranker
from retrieval import router
from retrieval.normalize import fold

logger = logging.getLogger(__name__)

_SEPARATOR_RE = re.compile(r"^\|\s*:?-{3,}")
# Ô có nhiều đoạn được trích thành "đoạn 1 / đoạn 2": mỗi đoạn sau là một dòng của đáp án.
_PART_SPLIT_RE = re.compile(r"\s+/\s+")
_LIST_MARKER_RE = re.compile(r"^(?:[-+*•]|\d+[.)])\s")


@dataclass(frozen=True)
class FaqPair:
    stem: str
    number: str
    question: str
    answer: str


@dataclass(frozen=True)
class FaqAnswer:
    text: str
    hits: list[dict]


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_pairs(
    text: str, question_pattern: str, answer_pattern: str, stem: str = ""
) -> list[FaqPair]:
    """Mọi dòng của các bảng có tiêu đề cột câu hỏi + đáp án (mẫu so trên tiêu đề đã bỏ dấu)."""
    lines = text.split("\n")
    pairs: list[FaqPair] = []
    columns: tuple[int, int, int | None] | None = None
    for i, line in enumerate(lines):
        if not line.startswith("|"):
            columns = None
            continue
        if _SEPARATOR_RE.match(line):
            continue
        cells = _cells(line)
        if i + 1 < len(lines) and _SEPARATOR_RE.match(lines[i + 1]):
            columns = _header_columns(cells, question_pattern, answer_pattern)
            continue
        if columns is None:
            continue
        q_col, a_col, n_col = columns
        if max(q_col, a_col) >= len(cells) or not cells[q_col] or not cells[a_col]:
            continue
        number = cells[n_col] if n_col is not None and n_col < len(cells) else str(len(pairs) + 1)
        pairs.append(FaqPair(stem, number, cells[q_col], cells[a_col]))
    return pairs


def _header_columns(
    cells: list[str], question_pattern: str, answer_pattern: str
) -> tuple[int, int, int | None] | None:
    folded = [fold(cell) for cell in cells]
    q_col = next((i for i, c in enumerate(folded) if re.search(question_pattern, c)), None)
    a_col = next((i for i, c in enumerate(folded) if re.search(answer_pattern, c)), None)
    if q_col is None or a_col is None or q_col == a_col:
        return None
    n_col = next((i for i, c in enumerate(folded) if c in ("stt", "tt", "cau")), None)
    return q_col, a_col, n_col


@lru_cache(maxsize=256)
def _cached_pairs(
    path: str, mtime: float, stem: str, question_pattern: str, answer_pattern: str
) -> tuple[FaqPair, ...]:
    text = Path(path).read_text(encoding="utf-8")
    return tuple(parse_pairs(text, question_pattern, answer_pattern, stem))


def _all_pairs() -> list[FaqPair]:
    settings = get_settings()
    cfg = settings.faq
    root = Path(settings.paths.markdown_dir)
    try:
        stems = sorted(router.known_files())
    except Exception:
        logger.warning("Không đọc được danh sách tài liệu cho bộ câu hỏi - đáp án", exc_info=True)
        return []
    pairs: list[FaqPair] = []
    for stem in stems:
        path = root / f"{stem}.md"
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        pairs.extend(
            _cached_pairs(
                str(path), mtime, stem, cfg.question_header_pattern, cfg.answer_header_pattern
            )
        )
    return pairs


def _overlap(question: str, pair: FaqPair) -> int:
    asked = set(fold(question).split())
    return len(asked & set(fold(pair.question).split()))


def format_answer(answer: str) -> str:
    """"Mở đầu: / ý 1 / ý 2" → đoạn mở đầu rồi danh sách gạch đầu dòng, mỗi ý một dòng."""
    parts = [part.strip() for part in _PART_SPLIT_RE.split(answer) if part.strip()]
    if len(parts) <= 1:
        return answer.strip()
    rest = [part if _LIST_MARKER_RE.match(part) else f"- {part}" for part in parts[1:]]
    return "\n".join([parts[0], *rest])


def _hit(pair: FaqPair, score: float) -> dict:
    text = f"Câu hỏi: {pair.question}\n\nĐáp án: {pair.answer}"
    payload = {
        "text": text,
        "file_stem": pair.stem,
        "section_path": f"Câu {pair.number}: {pair.question}",
        "kind": "paragraph",
    }
    return {"payload": payload, "rerank_score": score}


def try_faq_answer(question: str) -> FaqAnswer | None:
    """Đáp án của câu hỏi khớp nhất trong các bộ câu hỏi - đáp án; ``None`` để RAG trả lời."""
    cfg = get_settings().faq
    if not cfg.enabled or not question.strip():
        return None
    pairs = _all_pairs()
    if not pairs:
        return None
    # Lọc thô theo từ chung để lô cross-encoder nhỏ; bộ nhỏ thì chấm hết.
    candidates = sorted(pairs, key=lambda p: _overlap(question, p), reverse=True)
    candidates = candidates[: cfg.max_candidates]
    try:
        scores = reranker.score_documents(question, [p.question for p in candidates])
    except Exception:
        logger.warning("Không chấm được bộ câu hỏi - đáp án; chuyển sang RAG", exc_info=True)
        return None
    if len(scores) != len(candidates):
        return None
    score, best = max(zip(scores, candidates, strict=True), key=lambda item: item[0])
    if score < cfg.min_score:
        return None
    logger.info("Trả lời từ bộ câu hỏi - đáp án %s câu %s (%.3f)", best.stem, best.number, score)
    return FaqAnswer(format_answer(best.answer), [_hit(best, score)])
