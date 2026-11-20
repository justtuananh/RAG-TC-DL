"""Nội dung nguyên văn của các mục cấu trúc trong một tài liệu QTKĐ (thuần văn bản, không gọi dịch vụ).

QTKĐ có bố cục chuẩn: "Phương tiện kiểm định", "Điều kiện và chuẩn bị kiểm định", "Xử lý chung" (chu kỳ),
"Thuật ngữ và định nghĩa", khối "Cơ quan biên soạn / ban hành" ở đầu tệp. Câu hỏi về các mục này được trả
lời bằng chính nội dung mục (``query.doc_sections``) thay vì để LLM chọn đoạn: model 7B hay lấy nhầm bảng
(thông số lò thay cho nhiệt kế chuẩn) hoặc bỏ sót mục con (điều kiện 4.1 khi chỉ thấy chuẩn bị 4.2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core import outline
from retrieval.normalize import fold

_HEADING_RE = re.compile(r"^(#+)\s*(.+?)\s*$")
_NUMBERED_RE = re.compile(r"^(\d{1,2}(?:\.\d+)*)\.?\s+(.+)$")
_APPENDIX_RE = re.compile(r"^Phụ lục\s+[A-Z]\b", re.IGNORECASE)
_BOUNDARY_HEADINGS = {"loi noi dau", "muc luc", "loi gioi thieu"}
_BLANK_RUN_RE = re.compile(r"\n{3,}")
_CYCLE_RE = re.compile(r"\bchu ky kiem dinh\b")
_LIST_MARK_RE = re.compile(r"^[-*+]\s+")
_AGENCY_RE = re.compile(
    r"^(?:\d+\.\s*)?(?:co quan|chu nhiem|nguoi bien soan|thanh vien|don vi (?:bien soan|chu tri))\b"
)
_AGENCY_HEAD_LINES = 150
_AGENCY_MAX_GAP = 4
_TERM_COLON_RE = re.compile(r"^(?:\d+(?:\.\d+)+\.?\s+)?([^:|]{3,80}):\s*(.+)$")
_TERM_NUMBERED_RE = re.compile(r"^(\d+\.\d+)\.?\s+([^:|]{3,80})$")
# Dòng bảng thuật ngữ (TCVN 6165): "| 3.9. Độ không đảm bảo đo / A. uncertainty ... | định nghĩa |";
# dòng sau có ô đầu "A. ..." / "P. ..." / trống là chú thích, tên tiếng Anh/Pháp của cùng mục từ.
_TERM_ROW_RE = re.compile(r"^\|\s*(\d{1,2}\.\s?\d{1,2})\.?\s+([^|]{3,400}?)\s*\|\s*([^|]*?)\s*\|$")
_TERM_ROW_NOTE_RE = re.compile(r"^\|\s*(?:[AP]\.?\s[^|]*)?\|\s*([^|]*?)\s*\|$")
_TERM_LANGUAGE_SPLIT_RE = re.compile(r"\s+/\s+")
_NOT_TERMS = ("cac thuat ngu", "trong quy trinh", "chu thich", "vi du", "ghi chu")


@dataclass(frozen=True)
class SectionBody:
    number: str
    title: str
    level: int
    text: str

    @property
    def label(self) -> str:
        return f"{self.number} {self.title}"


@dataclass(frozen=True)
class Definition:
    term: str
    text: str  # nguyên văn mục từ, gồm cả tên thuật ngữ
    section: str  # "2 Thuật ngữ và định nghĩa"


def _heads(lines: list[str]) -> list[tuple[int, str | None, str, int]]:
    """(chỉ số dòng, số mục | None, tiêu đề, cấp) cho mọi tiêu đề ``#`` là mục đánh số, phụ lục hoặc ranh giới."""
    heads: list[tuple[int, str | None, str, int]] = []
    for i, line in enumerate(lines):
        match = _HEADING_RE.match(line.strip())
        if not match:
            continue
        text = match.group(2).strip()
        numbered = _NUMBERED_RE.match(text)
        if numbered:
            number = numbered.group(1).rstrip(".")
            heads.append((i, number, numbered.group(2).strip(), number.count(".") + 1))
        elif _APPENDIX_RE.match(text) or fold(text) in _BOUNDARY_HEADINGS:
            heads.append((i, None, text, 1))
    return heads


def _clean(lines: list[str]) -> str:
    out = []
    for line in lines:
        heading = _HEADING_RE.match(line.strip())
        out.append(f"**{heading.group(2).strip()}**" if heading else line.rstrip())
    return _BLANK_RUN_RE.sub("\n\n", "\n".join(out)).strip()


def section_bodies(markdown: str) -> list[SectionBody]:
    """Mọi mục đánh số có tiêu đề ``#`` kèm thân nguyên văn (gồm các mục con), theo thứ tự tài liệu.

    Tài liệu không có ``#`` (TCVN 6165, TCVN ISO/IEC 17025, thiết bị chuẩn mẫu) dùng mục suy ra từ dòng đánh
    số - cùng cách hiểu với chunker (``core.outline``)."""
    if not outline.has_headings(markdown):
        markdown = outline.promote_numbered_headings(markdown) or markdown
    lines = markdown.splitlines()
    heads = _heads(lines)
    bodies: list[SectionBody] = []
    for k, (start, number, title, level) in enumerate(heads):
        if number is None:
            continue
        end = len(lines)
        for nxt, nxt_number, _title, nxt_level in heads[k + 1 :]:
            if nxt_number is None or nxt_level <= level:
                end = nxt
                break
        bodies.append(SectionBody(number, title, level, _clean(lines[start + 1 : end])))
    return bodies


def find_section(markdown: str, title_pattern: str) -> SectionBody | None:
    """Mục có tiêu đề (đã bỏ dấu) khớp ``title_pattern``: ưu tiên cấp nông nhất, rồi thân dài nhất."""
    matches = [
        b for b in section_bodies(markdown) if re.search(title_pattern, fold(b.title)) and b.text
    ]
    if not matches:
        return None
    return min(matches, key=lambda b: (b.level, -len(b.text)))


def cycle_lines(markdown: str) -> list[str]:
    """Các câu nêu "Chu kỳ kiểm định ..." nguyên văn (bỏ dấu đầu dòng), không trùng lặp."""
    found: list[str] = []
    for line in markdown.splitlines():
        stripped = _LIST_MARK_RE.sub("", line.strip())
        if _CYCLE_RE.search(fold(stripped)) and "|" not in stripped and stripped not in found:
            found.append(stripped)
    return found


def agency_lines(markdown: str) -> list[str]:
    """Khối "Cơ quan biên soạn / đề nghị / trình duyệt / ban hành" đầu tiên ở đầu tệp, nguyên văn."""
    found: list[str] = []
    gap = 0
    awaiting_value = False  # "4. Chủ nhiệm biên soạn quy trình:" - tên người ở dòng kế tiếp
    for line in markdown.splitlines()[:_AGENCY_HEAD_LINES]:
        stripped = line.strip().lstrip("#").strip()
        if not stripped:
            continue
        if _AGENCY_RE.match(fold(stripped)):
            found.append(stripped)
            gap = 0
            awaiting_value = stripped.endswith(":")
        elif awaiting_value:
            found[-1] = f"{found[-1]} {stripped}"
            awaiting_value = False
        elif found:
            gap += 1
            if gap > _AGENCY_MAX_GAP:
                break
    return found


def definitions(markdown: str) -> list[Definition]:
    """Mục từ trong mục "Thuật ngữ (và định nghĩa)": dạng "Thuật ngữ: định nghĩa" hoặc "2.1 Thuật ngữ" + đoạn sau."""
    section = find_section(markdown, r"^thuat ngu")
    if section is None:
        return []
    found: list[Definition] = []
    # Mục con trong thân được ``_clean`` in đậm ("**3.1 Tính khách quan**"): bỏ dấu in đậm để nhận mục từ.
    lines = [line.strip().strip("*").strip() for line in section.text.splitlines()]
    in_row = False  # mục từ vừa đọc là một dòng bảng: dòng chú thích kế tiếp thuộc về nó
    for i, line in enumerate(lines):
        row = _TERM_ROW_RE.match(line)
        if row and row.group(3):
            term = _TERM_LANGUAGE_SPLIT_RE.split(row.group(2), maxsplit=1)[0].strip()
            label = f"{section.label}, mục từ {row.group(1).replace(' ', '')}"
            found.append(Definition(term, f"{row.group(1)} {term}: {row.group(3)}", label))
            in_row = True
            continue
        note = _TERM_ROW_NOTE_RE.match(line) if in_row and not row else None
        if note:
            if note.group(1):
                last = found[-1]
                found[-1] = Definition(last.term, f"{last.text}\n\n{note.group(1)}", last.section)
            continue
        in_row = False
        colon = _TERM_COLON_RE.match(line)
        if colon and fold(colon.group(1)).startswith(_NOT_TERMS):
            if found and fold(colon.group(1)).startswith(
                "chu thich"
            ):  # chú thích thuộc mục từ đứng trước
                last = found[-1]
                found[-1] = Definition(last.term, f"{last.text}\n\n{line}", last.section)
            continue
        if colon:
            found.append(Definition(colon.group(1).strip(), line, section.label))
            continue
        numbered = _TERM_NUMBERED_RE.match(line)
        if numbered:
            body = next((nxt for nxt in lines[i + 1 :] if nxt), "")
            if body and not _TERM_NUMBERED_RE.match(body):
                found.append(
                    Definition(numbered.group(2).strip(), f"{line}\n{body}", section.label)
                )
    return found
