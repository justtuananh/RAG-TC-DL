"""Câu hỏi về một mục cấu trúc của tài liệu đã chỉ đích danh: trả lời bằng nguyên văn mục đó, không qua LLM.

Ý định (mẫu trong ``doc_sections:`` của settings, so trên câu hỏi đã bỏ dấu):

- ``equipment``: phương tiện / chuẩn dùng để kiểm định → mục "Phương tiện kiểm định" (gồm Bảng 2);
- ``conditions``: điều kiện / chuẩn bị kiểm định → mục "Điều kiện (và chuẩn bị) kiểm định" trọn vẹn;
- ``cycle``: chu kỳ kiểm định → câu "Chu kỳ kiểm định của ... là ..." (tài liệu không có câu này thì nói rõ);
- ``agency``: cơ quan biên soạn / ban hành → khối "Cơ quan ..." ở đầu tài liệu;
- định nghĩa: "X là gì" mà X là một mục từ trong "Thuật ngữ và định nghĩa" (tài liệu chỉ đích danh, không có
  thì toàn kho).

Tài liệu được chọn bằng ``retrieval.router.route_files`` (mã, tên thiết bị, kiểu); câu so sánh nhiều tài liệu
được trả lời lần lượt từng tài liệu. Thiếu dữ liệu ở một tài liệu → ``None`` để pipeline RAG trả lời.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from core.settings_loader import get_settings
from retrieval import doc_profile, doc_sections, router
from retrieval.normalize import fold

EQUIPMENT = "equipment"
CONDITIONS = "conditions"
CYCLE = "cycle"
AGENCY = "agency"
_SECTION_TITLES = {EQUIPMENT: r"^phuong tien kiem dinh", CONDITIONS: r"^dieu kien"}
_NO_CYCLE = "Tài liệu không quy định chu kỳ kiểm định."
_SUBJECT_RE = re.compile(
    r"^(.+?)\s+(?:la gi|nghia la gi|duoc hieu la gi|duoc hieu (?:nhu )?the nao|la khai niem gi"
    r"|duoc dinh nghia (?:nhu )?(?:the nao|ra sao))$"
)
# "TCVN 6165:1996 định nghĩa X như thế nào", "Định nghĩa X".
_DEFINE_RE = re.compile(
    r"^(?:[\w.:/ ]{0,40}\s)?dinh nghia (?:cua |ve )?(.+?)(?:\s+(?:nhu )?(?:the nao|ra sao))?$"
)
_SOURCE_PREFIX_RE = re.compile(r"^(?:theo|trong) [^,]{2,40},\s*")
_SUBJECT_CUT_RE = re.compile(r"\s+(?:cua|trong|theo|o|tai)\s+|\s*\(")
_PAREN_RE = re.compile(r"\s*\([^)]*\)")
_MAX_TRAILING_TOKENS = 1  # "lượng cấp phát tối thiểu V_min": cho phép một ký hiệu sau thuật ngữ
_MIN_DEVICE_CHARS = 5  # "takhomet": tên thiết bị một từ phải đủ dài để không khớp nhầm


@dataclass(frozen=True)
class SectionAnswer:
    text: str
    hits: list[dict]


def classify(question: str) -> list[str]:
    """Các ý định mục cấu trúc có trong câu hỏi (thứ tự cố định); rỗng nếu không có hoặc bị loại trừ."""
    cfg = get_settings().doc_sections
    q = fold(question)
    if re.search(cfg.exclude_pattern, q):
        return []
    patterns = (
        (EQUIPMENT, cfg.equipment_pattern),
        (CONDITIONS, cfg.conditions_pattern),
        (CYCLE, cfg.cycle_pattern),
        (AGENCY, cfg.agency_pattern),
    )
    return [intent for intent, pattern in patterns if re.search(pattern, q)]


def _hit(stem: str, section_path: str, text: str) -> dict:
    payload = {"text": text, "file_stem": stem, "section_path": section_path, "kind": "paragraph"}
    return {"payload": payload, "rerank_score": 1.0}


def _header(profile: doc_profile.DocProfile) -> str:
    return f"**{profile.label} - {profile.title}**" if profile.title else f"**{profile.label}**"


def _read(stem: str) -> str | None:
    path = Path(get_settings().paths.markdown_dir) / f"{stem}.md"
    return path.read_text(encoding="utf-8") if path.exists() else None


def _block(intent: str, stem: str, markdown: str, ref: int) -> tuple[str, dict | None] | None:
    """(đoạn trả lời, nguồn) cho một ý định ở một tài liệu; ``None`` = không lấy được, để RAG trả lời."""
    if intent in _SECTION_TITLES:
        section = doc_sections.find_section(markdown, _SECTION_TITLES[intent])
        if section is None or len(section.text) > get_settings().doc_sections.max_section_chars:
            return None
        return f"Theo mục {section.label} [{ref}]:\n\n{section.text}", _hit(
            stem, section.label, section.text
        )
    if intent == CYCLE:
        lines = doc_sections.cycle_lines(markdown)
        if not lines:
            return _NO_CYCLE, None
        text = "\n".join(lines)
        return f"{text} [{ref}]", _hit(stem, "Chu kỳ kiểm định", text)
    lines = doc_sections.agency_lines(markdown)
    if not lines:
        return None
    return "\n\n".join(lines) + f" [{ref}]", _hit(
        stem, "Cơ quan biên soạn, ban hành", "\n".join(lines)
    )


def _render(
    blocks: list[tuple[doc_profile.DocProfile, list[str]]], hits: list[dict]
) -> SectionAnswer:
    parts = [f"{_header(profile)}\n\n" + "\n\n".join(texts) for profile, texts in blocks]
    lead = f"Có {len(parts)} tài liệu khớp với câu hỏi:\n\n" if len(parts) > 1 else ""
    return SectionAnswer(lead + "\n\n---\n\n".join(parts), hits)


def _structural_answer(intents: list[str], stems: list[str]) -> SectionAnswer | None:
    blocks: list[tuple[doc_profile.DocProfile, list[str]]] = []
    hits: list[dict] = []
    for stem in stems:
        profile = doc_profile.profile_for(stem)
        markdown = _read(stem)
        if profile is None or markdown is None:
            return None
        texts: list[str] = []
        for intent in intents:
            rendered = _block(intent, stem, markdown, len(hits) + 1)
            if rendered is None:
                return None
            text, hit = rendered
            texts.append(text)
            if hit is not None:
                hits.append(hit)
        blocks.append((profile, texts))
    if not hits:
        return None  # không tài liệu nào có dữ liệu: để RAG tìm thêm
    return _render(blocks, hits)


def _question_subject(question: str) -> str | None:
    """Thuật ngữ được hỏi: phần trước "là gì / được định nghĩa thế nào", hoặc sau "định nghĩa"; bỏ phần chỉ
    tài liệu ("của cột đo...", "trong QTKĐ ...", "(...)", "Theo TCVN 6165, ...")."""
    q = _SOURCE_PREFIX_RE.sub("", fold(question).strip(" ?."))
    match = _SUBJECT_RE.match(q) or _DEFINE_RE.match(q)
    if not match:
        return None
    return _SUBJECT_CUT_RE.split(match.group(1), maxsplit=1)[0].strip()


def _term_matches(term: str, subject: str) -> bool:
    """Câu hỏi nêu đúng thuật ngữ (hoặc một tên đồng nghĩa sau ";": "Sai số cho phép lớn nhất (...); giới
    hạn sai số cho phép (...)"), cho phép thêm tối đa ``_MAX_TRAILING_TOKENS`` ký hiệu phía sau."""
    for name in fold(_PAREN_RE.sub("", term)).split(";"):
        folded = name.strip()
        if len(folded.split()) >= 2 and subject.startswith(folded):
            if len(subject[len(folded) :].split()) <= _MAX_TRAILING_TOKENS:
                return True
    return False


def _definition_answer(subject: str, stems: list[str]) -> SectionAnswer | None:
    blocks: list[tuple[doc_profile.DocProfile, list[str]]] = []
    hits: list[dict] = []
    for stem in stems:
        markdown = _read(stem)
        profile = doc_profile.profile_for(stem)
        if markdown is None or profile is None:
            continue
        for definition in doc_sections.definitions(markdown):
            if _term_matches(definition.term, subject):
                hits.append(_hit(stem, definition.section, definition.text))
                quoted = "\n".join(
                    f"> {line}" if line else ">" for line in definition.text.splitlines()
                )
                blocks.append(
                    (profile, [f"Theo mục {definition.section} [{len(hits)}]:\n\n{quoted}"])
                )
                break
    if not hits or len(hits) > get_settings().doc_sections.max_documents:
        return None
    return _render(blocks, hits)


def _device_scope_answer(subject: str, stems: list[str]) -> SectionAnswer | None:
    """ "Takhomet là gì?": không có mục từ, nhưng X là tên thiết bị của tài liệu → nói rõ và trích phạm vi."""
    if len(subject) < _MIN_DEVICE_CHARS:
        return None
    blocks: list[tuple[doc_profile.DocProfile, list[str]]] = []
    hits: list[dict] = []
    for stem in stems:
        profile = doc_profile.profile_for(stem)
        if profile is None or not profile.scope_text or not profile.subject:
            continue
        if not re.match(rf"{re.escape(subject)}(?!\w)", profile.subject):
            continue
        hits.append(_hit(stem, profile.scope_heading, profile.scope_text))
        quoted = "\n".join(f"> {line}" for line in profile.scope_text.splitlines() if line.strip())
        blocks.append((profile, [f"Theo mục {profile.scope_heading} [{len(hits)}]:\n\n{quoted}"]))
    if not hits or len(hits) > get_settings().doc_sections.max_documents:
        return None
    answer = _render(blocks, hits)
    lead = f"Các tài liệu không có mục định nghĩa riêng cho «{subject}»; tài liệu nói về đối tượng này như sau.\n\n"
    return SectionAnswer(lead + answer.text, answer.hits)


def comparison_facts(question: str) -> str | None:
    """Khối "thông tin chính" nguyên văn của từng tài liệu cho câu so sánh nhiều tài liệu đã nêu đích danh.

    Đặt trước ngữ cảnh RAG: model 7B so sánh từ vài đoạn rời hay khẳng định sai "tài liệu không nêu chu kỳ"
    khi đoạn chu kỳ không lọt vào ngữ cảnh. Mỗi tài liệu: phạm vi, điều kiện kiểm định, chu kỳ kiểm định.
    """
    cfg = get_settings().doc_sections
    if not cfg.enabled or not re.search(cfg.comparison_pattern, fold(question)):
        return None
    stems = _by_label(router.route_files(question))
    if not 2 <= len(stems) <= cfg.max_documents:
        return None
    parts: list[str] = []
    for stem in stems:
        profile = doc_profile.profile_for(stem)
        markdown = _read(stem)
        if profile is None or markdown is None:
            return None
        lines = [f"### {profile.label} - {profile.title}".rstrip(" -")]
        if profile.scope_text:
            lines.append(f"Phạm vi áp dụng: {profile.scope_text}")
        conditions = doc_sections.find_section(markdown, r"^dieu kien kiem dinh$")
        if conditions is not None and len(conditions.text) <= cfg.max_fact_chars:
            lines.append(f"Điều kiện kiểm định (mục {conditions.number}):\n{conditions.text}")
        cycle = doc_sections.cycle_lines(markdown)
        lines.append(
            "Chu kỳ kiểm định: " + (" ".join(cycle) if cycle else "tài liệu không quy định.")
        )
        parts.append("\n".join(lines))
    header = (
        "THÔNG TIN CHÍNH CỦA TỪNG TÀI LIỆU (trích nguyên văn từ chính tài liệu; điều gì có ở đây thì "
        "KHÔNG được nói là tài liệu không nêu):"
    )
    return header + "\n\n" + "\n\n".join(parts)


def try_section_answer(question: str) -> SectionAnswer | None:
    """Trả lời nguyên văn theo mục cấu trúc, hoặc ``None`` để chat đi pipeline RAG."""
    cfg = get_settings().doc_sections
    if not cfg.enabled:
        return None
    intents = classify(question)
    if intents:
        routed = _by_label(router.route_files(question))
        if not routed or len(routed) > cfg.max_documents:
            return None
        return _structural_answer(intents, routed)
    subject = _question_subject(question)
    if not subject or re.search(cfg.exclude_pattern, fold(question)):
        return None
    candidates = _by_label(router.route_files(question)) or _by_label(router.known_files())
    if len(subject.split()) >= 2:
        definition = _definition_answer(subject, candidates)
        if definition is not None:
            return definition
    return _device_scope_answer(subject, candidates)


def _by_label(stems: frozenset[str]) -> list[str]:
    """Thứ tự trả lời theo mã tài liệu (QTKĐ 1.061 trước 1.213), không theo tên tệp."""

    def key(stem: str) -> tuple[str, str]:
        profile = doc_profile.profile_for(stem)
        return (profile.label if profile is not None else stem, stem)

    return sorted(stems, key=key)
