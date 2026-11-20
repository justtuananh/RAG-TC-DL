"""Câu hỏi "tài liệu này để làm gì / nói về gì / gồm những mục nào": trả lời từ hồ sơ tài liệu.

Câu trả lời trích NGUYÊN VĂN mục "Phạm vi áp dụng" và mục lục của chính tài liệu (``retrieval.doc_profile``),
không qua LLM, nên không thể thiếu ý hay bịa. Chỉ áp dụng khi câu hỏi chỉ đích danh tài liệu (mã QTKĐ/TCVN,
kiểu thiết bị, tên thiết bị) và hỏi đúng một trong ba ý định trên; mọi trường hợp khác trả ``None`` để chat
đi pipeline RAG như cũ.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.settings_loader import get_settings
from knowledge import doc_summary
from retrieval import doc_profile, router
from retrieval.normalize import fold

PURPOSE = "purpose"
OVERVIEW = "overview"
TOC = "toc"
SUMMARY_SECTION = "Tóm tắt (đã duyệt)"
_MIN_TOC_SECTIONS = 2


@dataclass(frozen=True)
class DocumentAnswer:
    text: str
    hits: list[dict]


def classify_intent(question: str) -> str | None:
    """Ý định của câu hỏi (mục lục > tổng quan > mục đích), ``None`` nếu không thuộc ba loại này."""
    cfg = get_settings().doc_profile
    q = fold(question)
    if re.search(cfg.exclude_pattern, q):
        return None
    for intent, pattern in ((TOC, cfg.toc_pattern), (OVERVIEW, cfg.overview_pattern), (PURPOSE, cfg.purpose_pattern)):
        if re.search(pattern, q):
            return intent
    return None


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" for line in text.splitlines() if line.strip())


def _header(profile: doc_profile.DocProfile) -> str:
    return f"**{profile.label} - {profile.title}**" if profile.title else f"**{profile.label}**"


def _hit(profile: doc_profile.DocProfile, section_path: str, text: str) -> dict:
    payload = {"text": text, "file_stem": profile.file_stem, "section_path": section_path, "kind": "paragraph"}
    return {"payload": payload, "rerank_score": 1.0}


def _approved_summary(file_stem: str) -> str | None:
    """Bản tóm tắt người duyệt đã phê duyệt (``knowledge.doc_summary``), nếu cấu hình cho chat dùng."""
    if not get_settings().doc_summary.use_in_chat:
        return None
    return doc_summary.approved_text(file_stem)


def _toc_lines(profile: doc_profile.DocProfile, max_level: int) -> str:
    return "\n".join(
        "  " * (s.level - 1) + f"- {s.label}" for s in profile.sections if s.level <= max_level
    )


def _render(intent: str, profile: doc_profile.DocProfile, ref: int) -> tuple[str, dict] | None:
    if intent == TOC:
        if len(profile.sections) < _MIN_TOC_SECTIONS:
            return None
        toc = _toc_lines(profile, max_level=2)
        return f"{_header(profile)}\n\nMục lục [{ref}]:\n\n{toc}", _hit(profile, "Mục lục", toc)
    if intent == OVERVIEW:
        summary = _approved_summary(profile.file_stem)
        if summary:
            text = f"{_header(profile)}\n\nTóm tắt đã được người duyệt phê duyệt [{ref}]:\n\n{summary}"
            return text, _hit(profile, SUMMARY_SECTION, summary)
    if not profile.scope_text:
        return None
    scope = f"Theo mục {profile.scope_heading} [{ref}]:\n\n{_quote(profile.scope_text)}"
    text = f"{_header(profile)}\n\n{scope}"
    if intent == OVERVIEW and len(profile.sections) >= _MIN_TOC_SECTIONS:
        main = "; ".join(s.label for s in profile.sections if s.level == 1)
        text += f"\n\nTài liệu gồm các mục chính: {main}."
    return text, _hit(profile, profile.scope_heading, profile.scope_text)


def try_document_answer(question: str) -> DocumentAnswer | None:
    """Trả lời từ hồ sơ tài liệu, hoặc ``None`` để chat đi pipeline RAG."""
    cfg = get_settings().doc_profile
    if not cfg.enabled:
        return None
    intent = classify_intent(question)
    if intent is None:
        return None
    stems = sorted(router.route_files(question))
    if not stems or len(stems) > cfg.max_documents:
        return None
    blocks: list[str] = []
    hits: list[dict] = []
    for stem in stems:
        profile = doc_profile.profile_for(stem)
        rendered = _render(intent, profile, len(hits) + 1) if profile else None
        if rendered is None:
            return None  # thiếu dữ liệu ở một tài liệu: để RAG trả lời đủ cả nhóm
        block, hit = rendered
        blocks.append(block)
        hits.append(hit)
    lead = f"Có {len(blocks)} tài liệu khớp với câu hỏi:\n\n" if len(blocks) > 1 else ""
    return DocumentAnswer(lead + "\n\n---\n\n".join(blocks), hits)
