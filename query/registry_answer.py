"""Tầng 1 của chat: tra sổ đăng ký danh mục 877 trước mọi câu hỏi (docs/KIEN_TRUC_DANH_MUC_877.md mục 6).

- Câu hỏi CHUNG (có không, bao nhiêu, liệt kê, dải đo, cấp chính xác, chu kỳ chuẩn, dùng quy trình nào)
  được trả lời ngay từ bảng, trích nguyên văn kèm [n] = dòng trong file danh mục, không qua LLM.
- Câu hỏi SÂU (cách làm, điều kiện, công thức, sai số cho phép...) nhận danh sách tài liệu trong kho
  mà sổ đăng ký chỉ ra; chat chỉ tìm trong các tài liệu đó (``retriever.retrieve_pinned``).
- Câu có cả hai ý: phần chung trả lời trước, phần sâu tìm tiếp trong cùng lượt.
- Hỏi tiếp ("còn cái thứ 2 thì sao?", "quy trình đó cần chuẩn gì?") dùng TIÊU ĐIỂM: các dòng danh mục mà
  câu hỏi trước đó đã nói tới, tính lại tất định từ lịch sử nên frontend không phải giữ trạng thái.

Không khớp gì thì trả ``None``: chat đi tiếp như cũ (doc_catalog → doc_sections → doc_overview → RAG).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from core.settings_loader import get_settings
from knowledge.catalog_codes import CatalogCode
from knowledge.catalog_units import question_quantities
from knowledge.registry import CapabilityEntry, ProcedureEntry, StandardEntry
from retrieval import registry_match
from retrieval.normalize import fold
from retrieval.registry_match import DocLink, Entry

_KIND_LABEL = {"kiem_dinh": "kiểm định", "hieu_chuan": "hiệu chuẩn"}
_ORDINALS = {"nhat": 1, "hai": 2, "ba": 3, "tu": 4, "bon": 4, "nam": 5, "sau": 6, "bay": 7, "tam": 8, "chin": 9, "muoi": 10}
_ORDINAL_RE = re.compile(r"\b(?:thứ|mục|cái)\s+(\d+|nhất|hai|ba|tư|bốn|năm|sáu|bảy|tám|chín|mười)\b", re.IGNORECASE)
# Loại câu chung đi cùng câu sâu vẫn được trả lời trước ("dùng quy trình nào và kiểm tra độ kín ra sao").
_GENERAL_WITH_DEEP = {"procedure", "range", "count", "list"}
_MAX_FOCUS_TURNS = 6
_MAX_EXCLUDED_NAMES = 8


@dataclass(frozen=True)
class RegistryPlan:
    """Kết quả tra sổ đăng ký cho một câu hỏi.

    ``mode``: ``answer`` (trả lời xong từ danh mục), ``deep`` (tìm sâu trong ``stems``) hoặc ``both``
    (``text`` trả lời phần chung trước, rồi tìm sâu). ``routing_hint`` là các mã tài liệu đã chọn, nối vào
    câu hỏi cho các bộ trả lời nguyên văn hiện có (mục tài liệu, hồ sơ) để chúng ghim đúng tài liệu."""

    mode: str
    text: str = ""
    hits: list[dict] = field(default_factory=list)
    stems: frozenset[str] = frozenset()
    catalog_block: str = ""
    note: str = ""
    routing_hint: str = ""
    no_document: bool = False  # danh mục có, kho không nối được văn bản nào
    # Câu hỏi tiếp dựa vào tiêu điểm ("cái thứ 2"): tên đối tượng để nối vào câu hỏi cho tìm kiếm và LLM.
    subject: str = ""


@dataclass(frozen=True)
class _Resolved:
    entries: tuple[Entry, ...]
    general: tuple[str, ...]
    deep: bool
    confident: bool
    excluded: tuple[Entry, ...] = ()
    quantity_text: str = ""
    kind_mismatch: str = ""  # hỏi "hiệu chuẩn" mà danh mục chỉ có năng lực kiểm định (hoặc ngược lại)


# ── Phân loại và chọn dòng danh mục ──────────────────────────────────────────


def _general_types(q: str) -> tuple[str, ...]:
    patterns = get_settings().registry.general_patterns
    return tuple(name for name, pattern in patterns.items() if re.search(pattern, q))


def _is_deep(q: str) -> bool:
    return bool(re.search(get_settings().registry.deep_pattern, q))


def _kind_filter(q: str, entries: Sequence[Entry]) -> tuple[list[Entry], str]:
    """"kiểm định" / "hiệu chuẩn" trong câu hỏi chọn đúng loại năng lực và quy trình.
    Không còn dòng nào đúng loại thì giữ nguyên các dòng và báo loại bị thiếu."""
    wanted = {k for k, label in (("kiem_dinh", "kiem dinh"), ("hieu_chuan", "hieu chuan")) if label in q}
    if len(wanted) != 1:
        return list(entries), ""
    kept = [e for e in entries if isinstance(e, StandardEntry) or e.kind in wanted]
    if kept:
        return kept, ""
    return list(entries), _KIND_LABEL[next(iter(wanted))]


def _quantity_filter(
    question: str, entries: Sequence[Entry], *, strict: bool
) -> tuple[list[Entry], list[Entry], str]:
    """Câu có "<số> <đơn vị>": giữ dòng có dải chứa giá trị đó, ghi lại dòng bị loại.

    ``strict`` (câu liệt kê không nêu tên, "chuẩn nào tạo được 600 bar"): dòng không có dải cùng đại lượng
    cũng bị bỏ (quả cân, cầu điện trở). Câu nêu tên thì giữ dòng đó dù danh mục không tách được dải."""
    quantities = question_quantities(question)
    if not quantities:
        return list(entries), [], ""
    kept: list[Entry] = []
    excluded: list[Entry] = []
    for entry in entries:
        ranges = getattr(entry, "ranges", ())
        covering = registry_match.covering_ranges(ranges, quantities) if ranges else None
        if covering:
            kept.append(entry)
        elif covering == []:
            excluded.append(entry)
        elif not strict:
            kept.append(entry)
    return kept, excluded, ", ".join(q.raw for q in quantities)


def _without_listed_procedures(entries: Sequence[Entry]) -> list[Entry]:
    """Năng lực đã nêu quy trình của nó thì không liệt kê lại dòng quy trình trùng số như một mục riêng
    ("van an toàn" khớp cả năng lực lẫn QTKĐ 1.023:2021)."""
    bases = {code.base for e in entries if isinstance(e, CapabilityEntry) for code in e.codes}
    return [e for e in entries if not (isinstance(e, ProcedureEntry) and e.code and e.code.base in bases)]


def _browse(question: str, q: str) -> list[Entry]:
    """Câu liệt kê / đếm không nêu tên ("những phương tiện đo áp suất nào", "chuẩn nào tạo được 600 bar"):
    chọn theo lĩnh vực, loại và đối tượng (năng lực, quy trình hay chuẩn mẫu)."""
    cfg = get_settings().registry
    snapshot = registry_match.data()
    terms = registry_match.field_terms(question)
    has_quantity = bool(question_quantities(question))
    has_kind = "kiem dinh" in q or "hieu chuan" in q
    if re.search(cfg.standard_pattern, q):
        if not (terms or has_quantity or re.search(r"\bchuan mau\b", q)):
            return []
        return [s for s in snapshot.standards if registry_match.in_field(s, terms)]
    if re.search(cfg.procedure_pattern, q):
        if not (terms or has_kind):
            return []
        return [p for p in snapshot.procedures if registry_match.in_field(p, terms)]
    if not (terms or has_kind or has_quantity):
        return []
    return [c for c in snapshot.capabilities if registry_match.in_field(c, terms)]


def _resolve(question: str) -> _Resolved | None:
    """Các dòng danh mục câu hỏi nói tới (đã lọc), loại câu chung và có ý sâu hay không."""
    cfg = get_settings().registry
    q = fold(question)
    general = _general_types(q)
    deep = _is_deep(q)
    found = registry_match.match(question)
    browsing = found.empty
    if browsing:
        if not general or deep or found.codes:
            return None
        entries = _browse(question, q)
        confident = True
    else:
        entries = _without_listed_procedures(found.entries)
        confident = found.explicit or found.coverage >= cfg.min_coverage
    entries, mismatch = _kind_filter(q, entries)
    entries, excluded, quantity_text = _quantity_filter(question, entries, strict=browsing)
    if not entries and not excluded:
        return None
    return _Resolved(tuple(entries), general, deep, confident, tuple(excluded), quantity_text, mismatch)


# ── Tiêu điểm hội thoại ──────────────────────────────────────────────────────


def _ordinal(question: str) -> int | None:
    match = _ORDINAL_RE.search(question)
    if not match:
        return None
    value = match.group(1).lower()
    return int(value) if value.isdigit() else _ORDINALS.get(fold(value))


def _is_followup(question: str) -> bool:
    cfg = get_settings().registry
    if re.search(cfg.followup_pattern, question.lower()):
        return True
    q = fold(question)
    return len(q.split()) <= cfg.followup_max_words and _is_deep(q)


def _topic(questions: Sequence[str], index: int) -> tuple[Entry, ...]:
    """Dòng danh mục mà câu hỏi thứ ``index`` nói tới, kể cả khi chính nó là câu hỏi tiếp."""
    resolved = _resolve(questions[index])
    if resolved is not None and resolved.entries:
        return resolved.entries
    return _focus(questions[index], questions[:index])


def _focus(question: str, prior_questions: Sequence[str]) -> tuple[Entry, ...]:
    """Tiêu điểm: dòng danh mục của câu hỏi gần nhất có khớp; số thứ tự ("cái thứ 2") chọn một dòng."""
    if not _is_followup(question):
        return ()
    recent = list(prior_questions)[-_MAX_FOCUS_TURNS:]
    for index in range(len(recent) - 1, -1, -1):
        entries = _topic(recent, index)
        if not entries:
            continue
        position = _ordinal(question)
        if position is not None and 1 <= position <= len(entries):
            return (entries[position - 1],)
        return entries
    return ()


# ── Trích dẫn và hiển thị ────────────────────────────────────────────────────


def _row_text(entry: Entry) -> str:
    if isinstance(entry, CapabilityEntry):
        parts = [entry.name, entry.params_raw, entry.procedures_raw, entry.field]
    elif isinstance(entry, ProcedureEntry):
        kind = f"Quy trình {_KIND_LABEL.get(entry.kind, '')}"
        parts = [entry.code_raw, entry.title, entry.issuer, entry.field, kind]
    else:
        parts = [entry.name, entry.model, entry.serial, entry.characteristics_raw, entry.interval_raw]
    return " | ".join(" ".join(p.split()) for p in parts if p)


class _Citations:
    """Đánh số [n] theo dòng danh mục; ``hits`` có cùng dạng nguồn của RAG để panel hiển thị."""

    def __init__(self) -> None:
        self.hits: list[dict] = []
        self._index: dict[int, int] = {}

    def cite(self, entry: Entry) -> str:
        key = id(entry)
        if key not in self._index:
            payload = {
                "text": _row_text(entry),
                "file_stem": entry.source_file.rsplit(".", 1)[0],
                "section_path": f"Dòng {entry.row}",
                # Không phải tài liệu trong kho: panel nguồn không mở trình xem tài liệu cho loại này.
                "kind": "registry",
            }
            self.hits.append({"payload": payload, "rerank_score": 1.0})
            self._index[key] = len(self.hits)
        return f"[{self._index[key]}]"


def _same_number(code: CatalogCode) -> list[ProcedureEntry]:
    return [e for e in registry_match.data().procedures if e.code is not None and e.code.base == code.base]


def _code_line(code: CatalogCode) -> str:
    catalog = registry_match.procedure_for(code)
    if catalog is not None:
        title = f" - {catalog.title}"
    elif same := _same_number(code):
        listed = "; ".join(f"{e.code.key} - {e.title}" for e in same)
        title = f" (danh mục quy trình ghi: {listed})"
    else:
        title = " (không có trong danh mục quy trình)"
    docs = registry_match.docs_for_code(code, catalog.title if catalog else None)
    status = "kho có văn bản" if docs else "kho chưa có văn bản"
    return f"{code.key}{title} ({status})"


def _entry_name(entry: Entry) -> str:
    if isinstance(entry, ProcedureEntry):
        return f"{entry.code.key if entry.code else entry.code_raw} - {entry.title}"
    if isinstance(entry, StandardEntry):
        ident = " ".join(p for p in (entry.model, f"số {entry.serial}" if entry.serial else "") if p)
        return f"{entry.name} {ident}".strip()
    return entry.name


def _capability_lines(entry: CapabilityEntry, general: set[str]) -> list[str]:
    lines: list[str] = []
    if "range" in general or "procedure" not in general:
        lines.extend(f"  - {p}" for p in entry.params_raw.splitlines() if p.strip())
    lines.extend(f"  - Quy trình: {_code_line(code)}" for code in entry.codes)
    if not entry.codes:
        lines.append("  - Danh mục năng lực để trống cột quy trình.")
    return lines


def _entry_block(entry: Entry, general: set[str], cite: _Citations) -> str:
    """Một mục trong câu trả lời: tên + các cột câu hỏi cần, nguyên văn."""
    lines = [f"- **{_entry_name(entry)}** {cite.cite(entry)}"]
    if isinstance(entry, CapabilityEntry):
        lines.extend(_capability_lines(entry, general))
    elif isinstance(entry, StandardEntry):
        lines.extend(f"  - {p}" for p in entry.characteristics_raw.splitlines() if p.strip())
        if entry.interval_raw:
            lines.append(f"  - Chu kỳ kiểm định, hiệu chuẩn: {entry.interval_raw}")
    else:
        lines.append(f"  - {entry.issuer}; {entry.field}; quy trình {_KIND_LABEL.get(entry.kind, '')}")
        lines.append("  - Kho có văn bản." if registry_match.docs_for(entry) else "  - Kho chưa có văn bản.")
    return "\n".join(lines)


def _noun(entries: Sequence[Entry]) -> str:
    if all(isinstance(e, StandardEntry) for e in entries):
        return "chuẩn mẫu"
    if all(isinstance(e, ProcedureEntry) for e in entries):
        return "quy trình"
    kinds = {e.kind for e in entries if isinstance(e, CapabilityEntry)}
    if kinds == {"kiem_dinh"}:
        return "phương tiện đo phòng được kiểm định"
    if kinds == {"hieu_chuan"}:
        return "phương tiện đo phòng được hiệu chuẩn"
    return "mục"


def _lead(resolved: _Resolved) -> str:
    entries = resolved.entries
    if resolved.kind_mismatch:
        return f"Danh mục 877 không ghi năng lực {resolved.kind_mismatch} cho đối tượng này. Danh mục ghi:"
    general = set(resolved.general)
    if "exists" in general and not {"count", "list"} & general:
        return "Có. Theo danh mục 877:"
    if {"count", "list"} & general:
        condition = f" có dải chứa {resolved.quantity_text}" if resolved.quantity_text else ""
        return f"Theo danh mục 877, có **{len(entries)}** {_noun(entries)}{condition}:"
    return "Theo danh mục 877:"


def _general_answer(resolved: _Resolved) -> tuple[str, list[dict]]:
    if not resolved.entries:
        names = ", ".join(_entry_name(e) for e in resolved.excluded[:_MAX_EXCLUDED_NAMES])
        text = f"Không có mục nào trong danh mục 877 có dải chứa {resolved.quantity_text} (đã xét: {names})."
        return text, []
    cfg = get_settings().registry
    cite = _Citations()
    general = set(resolved.general)
    shown = resolved.entries[: cfg.max_list]
    parts = [_lead(resolved), "\n".join(_entry_block(e, general, cite) for e in shown)]
    if len(resolved.entries) > len(shown):
        parts.append(
            f"(Đã liệt kê {len(shown)}/{len(resolved.entries)} mục; hãy nêu thêm lĩnh vực hoặc tên để thu hẹp.)"
        )
    if resolved.excluded:
        names = ", ".join(_entry_name(e) for e in resolved.excluded[:_MAX_EXCLUDED_NAMES])
        parts.append(f"Không có dải chứa {resolved.quantity_text}: {names}.")
    return "\n\n".join(parts), cite.hits


# ── Tìm sâu ──────────────────────────────────────────────────────────────────


def _links(entries: Sequence[Entry]) -> tuple[list[DocLink], list[str]]:
    """Tài liệu trong kho của các dòng danh mục + các mã có trong danh mục mà kho chưa có văn bản."""
    links: list[DocLink] = []
    seen: set[str] = set()
    missing: list[str] = []
    for entry in entries:
        found = registry_match.docs_for(entry)
        for link in found:
            if link.stem not in seen:
                seen.add(link.stem)
                links.append(link)
        for code in registry_match.codes_of(entry):
            catalog = registry_match.procedure_for(code)
            if not registry_match.docs_for_code(code, catalog.title if catalog else None):
                missing.append(code.key)
        if isinstance(entry, StandardEntry) and not found:
            missing.append(_entry_name(entry))
    return links, list(dict.fromkeys(missing))


def _catalog_block(entries: Sequence[Entry]) -> str:
    rows = "\n".join(f"- {e.source_file}, dòng {e.row}: {_row_text(e)}" for e in entries)
    return "Thông tin danh mục 877 của phòng (nguyên văn):\n" + rows


def _deep_note(links: Sequence[DocLink], missing: Sequence[str]) -> str:
    lines: list[str] = []
    if links:
        labels = ", ".join(dict.fromkeys(link.label for link in links))
        lines.append(f"_Phạm vi tìm theo danh mục 877: {labels}._")
    lines.extend(f"_Lưu ý: {link.note}._" for link in links if link.note)
    if missing:
        lines.append("_" + ", ".join(missing) + " có trong danh mục 877 nhưng kho chưa có văn bản để tra sâu._")
    return "\n".join(lines)


def _no_document_answer(entries: Sequence[Entry], missing: Sequence[str]) -> RegistryPlan:
    cite = _Citations()
    blocks = "\n".join(_entry_block(e, {"procedure"}, cite) for e in entries)
    subjects = ", ".join(missing or [_entry_name(e) for e in entries])
    text = (
        f"Theo danh mục 877:\n\n{blocks}\n\n"
        f"Kho tài liệu chưa có văn bản của {subjects} nên chưa tra sâu được nội dung câu hỏi."
    )
    return RegistryPlan(mode="answer", text=text, hits=cite.hits, no_document=True)


def _deep_plan(resolved: _Resolved, text: str = "", hits: list[dict] | None = None) -> RegistryPlan:
    links, missing = _links(resolved.entries)
    if not links:
        if text:
            text = text + "\n\n" + _deep_note([], missing)
            return RegistryPlan(mode="answer", text=text, hits=hits or [], no_document=True)
        return _no_document_answer(resolved.entries, missing)
    return RegistryPlan(
        mode="both" if text else "deep",
        text=text,
        hits=hits or [],
        stems=frozenset(link.stem for link in links),
        catalog_block=_catalog_block(resolved.entries),
        note=_deep_note(links, missing),
        routing_hint="; ".join(dict.fromkeys(link.label for link in links)),
    )


# ── Điểm vào ─────────────────────────────────────────────────────────────────


def plan(question: str, prior_questions: Sequence[str] = ()) -> RegistryPlan | None:
    """Kế hoạch trả lời theo sổ đăng ký, hoặc ``None`` để chat đi tiếp như cũ."""
    if not get_settings().registry.enabled:
        return None
    resolved = _resolve(question)
    subject = ""
    if resolved is None:
        focus = _focus(question, prior_questions)
        if not focus:
            return None
        q = fold(question)
        resolved = _Resolved(focus, _general_types(q), _is_deep(q), confident=True)
        subject = "; ".join(_entry_name(e) for e in focus)
    plan_ = _plan(resolved)
    if plan_ is not None and subject:
        plan_ = replace(plan_, subject=subject)
    return plan_


def _plan(resolved: _Resolved) -> RegistryPlan | None:
    general = set(resolved.general)
    # "Chu kỳ" của phương tiện / quy trình nằm trong văn bản QTKĐ; chỉ chuẩn mẫu có chu kỳ trong danh mục.
    if general == {"interval"} and not any(isinstance(e, StandardEntry) for e in resolved.entries):
        general = set()
    if general and not resolved.deep:
        text, hits = _general_answer(resolved)
        return RegistryPlan(mode="answer", text=text, hits=hits)
    if not resolved.confident or not resolved.entries:
        return None
    if resolved.deep and general & _GENERAL_WITH_DEEP:
        text, hits = _general_answer(resolved)
        return _deep_plan(resolved, text, hits)
    return _deep_plan(resolved)
