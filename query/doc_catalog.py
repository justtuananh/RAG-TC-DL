"""Câu "những QTKĐ nào liên quan đến X": liệt kê tài liệu theo tên và phạm vi áp dụng, không qua LLM.

Pipeline RAG trả lời câu liệt kê kém: mỗi tài liệu chỉ góp vài đoạn, model 7B bỏ sót tài liệu hoặc chèn
tài liệu không liên quan. Hồ sơ tài liệu (``retrieval.doc_profile``) có sẵn tên và phạm vi của MỌI tài liệu
đã nạp nên trả lời tất định được: tài liệu khớp khi chủ đề X nằm trong tên hoặc câu đầu mục phạm vi; chủ đề
ngắn ("nhiệt độ") còn khớp khi danh từ chính của nó là một từ trong tên đối tượng ("nhiệt kế", "ổn nhiệt").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.settings_loader import get_settings
from retrieval import doc_profile, router
from retrieval.normalize import fold

_SENTENCE_END_RE = re.compile(r"(?<=[.;])\s|\n")
_SHORT_TOPIC_WORDS = 2
_MIN_HEAD_CHARS = 4


@dataclass(frozen=True)
class CatalogAnswer:
    text: str
    hits: list[dict]


def topic_of(question: str) -> str | None:
    """Chủ đề X (đã bỏ dấu) của câu "những QTKĐ nào liên quan đến X", ``None`` nếu không phải câu liệt kê."""
    cfg = get_settings().doc_catalog
    q = fold(question).strip(" ?.")
    if not re.search(cfg.question_pattern, q):
        return None
    match = re.search(cfg.topic_pattern, q)
    if not match:
        return None
    topic = re.sub(cfg.topic_prefix_pattern, "", match.group(1).strip()).strip()
    return topic or None


def _matches(profile: doc_profile.DocProfile, topic: str) -> bool:
    first_sentence = _SENTENCE_END_RE.split(profile.scope_text, maxsplit=1)[0] if profile.scope_text else ""
    haystack = f"{fold(profile.title)}\n{fold(first_sentence)}"
    if re.search(rf"(?<!\w){re.escape(topic)}(?!\w)", haystack):
        return True
    words = topic.split()
    head = words[0]
    return (
        len(words) <= _SHORT_TOPIC_WORDS
        and len(head) >= _MIN_HEAD_CHARS
        and head in profile.subject.split()
    )


def try_catalog_answer(question: str) -> CatalogAnswer | None:
    """Danh sách tài liệu khớp chủ đề, hoặc ``None`` để chat đi pipeline RAG."""
    cfg = get_settings().doc_catalog
    if not cfg.enabled:
        return None
    topic = topic_of(question)
    if topic is None:
        return None
    profiles = [p for p in map(doc_profile.profile_for, sorted(router.known_files())) if p is not None]
    found = sorted((p for p in profiles if _matches(p, topic)), key=lambda p: p.label)
    if not found or len(found) > cfg.max_documents:
        return None
    lines: list[str] = []
    hits: list[dict] = []
    for profile in found:
        payload = {
            "text": profile.scope_text or profile.title,
            "file_stem": profile.file_stem,
            "section_path": profile.scope_heading or "Tên tài liệu",
            "kind": "paragraph",
        }
        hits.append({"payload": payload, "rerank_score": 1.0})
        name = f" - {profile.title}" if profile.title else ""
        lines.append(f"- **{profile.label}**{name} [{len(hits)}]")
    lead = f"Có {len(found)} tài liệu liên quan (theo tên và phạm vi áp dụng của tài liệu):"
    return CatalogAnswer(lead + "\n\n" + "\n".join(lines), hits)
