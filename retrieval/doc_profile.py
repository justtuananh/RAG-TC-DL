"""Hồ sơ tài liệu dựng từ Markdown nguồn: mã, tên đối tượng, mục "Phạm vi áp dụng", mục lục, từ khoá kiểu.

Dùng cho câu hỏi "QTKĐ này để làm gì / nói về gì / gồm những mục nào" (trả lời tất định, trích
nguyên văn, không qua LLM) và cho router (ghim tài liệu theo mã TCVN/ISO hoặc kiểu thiết bị).
Mọi trường lấy từ chính nội dung tài liệu khi nạp nên tài liệu mới tự có hồ sơ; cache khoá theo
mtime của tệp Markdown nên nạp lại tài liệu là hồ sơ được dựng lại.

Ba dạng tài liệu thực tế đều được nhận:
- QTKĐ mới: ``QTKĐ 1.061 : 2021`` / tên đối tượng / ``QUY TRÌNH KIỂM ĐỊNH``, mục có tiêu đề ``#``;
- QTKĐ cũ: ``Lời nói đầu`` / tên đối tượng / ``Quy trình kiểm định`` (mã chỉ có trong tên tệp);
- TCVN: ``TCVN 6165:1996`` / tên tiêu chuẩn, mục là dòng đánh số không có ``#``;
- đề cương xây dựng quy trình: ``1. Tên quy trình: ... - Quy trình kiểm định.``, ``2. Phạm vi sử dụng: ...``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from core.settings_loader import get_settings
from retrieval.normalize import fold

_HEAD_LINES = 80
_MAX_TITLE_LINES = 5

_QTKD_RE = re.compile(r"QTK[ĐD]\s*(\d\.\d{3})\s*:?\s*(\d{4})", re.IGNORECASE)
_TCVN_RE = re.compile(r"\bTCVN\s+((?:ISO/IEC\s+)?\d{3,5})\s*:\s*(\d{4})")
_STEM_RE = re.compile(r"QTK[ĐD]_(\d\.\d{3})_(\d{4})", re.IGNORECASE)
_OUTLINE_TITLE_RE = re.compile(r"Tên quy trình:\s*(.+?)\s*-\s*Quy trình kiểm định", re.IGNORECASE)
_TITLE_END_RE = re.compile(r"^#*\s*quy trình kiểm định\s*$", re.IGNORECASE)
_TITLE_STOP_RE = re.compile(
    r"^(?:Cơ quan|\(Ban hành|của Cục|HÀ NỘI|Mục lục|Lời nói đầu|Trang\b|\||QTKĐ QUY TRÌNH)",
    re.IGNORECASE,
)
_CODE_LIKE_RE = re.compile(r":\s*\d{4}\s*$")
_SCOPE_RE = re.compile(
    r"^#*\s*(\d{1,2})\.?\s+(Phạm vi (?:áp dụng|sử dụng))\s*:?\s*(.*)$", re.IGNORECASE
)
_SECTION_BOUNDARY_RE = re.compile(r"^(?:#|\s*\d{1,2}(?:\.\d+)*\.?\s+[A-ZĐÀ-ỸÂÊÔƠƯĂ])")
_SCOPE_SKIP_RE = re.compile(r"^Số hiệu\b", re.IGNORECASE)  # đề cương: dòng mã đăng ký nằm ngay dưới phạm vi
_PAGE_SUFFIX_RE = re.compile(r"[\s.…]*\d*\s*$")
_HEADING_RE = re.compile(r"^(#+)\s*(.+?)\s*$")
_NUMBERED_RE = re.compile(r"^(\d{1,2}(?:\.\d+)*)\.?\s+(.+)$")
_APPENDIX_RE = re.compile(r"^(Phụ lục\s+[A-Z])\b\s*(.*)$", re.IGNORECASE)
_PLAIN_SECTION_RE = re.compile(r"^#*\s*(\d{1,2})\.?\s+([A-ZĐÀ-Ỹa-zà-ỹ][^|]{2,120})$")
_MODEL_RE = re.compile(r"\bkiểu\s+(.+?)(?:\s*,|\s+có\s|$)", re.IGNORECASE)
# Tài liệu kỹ thuật thiết bị chuẩn mẫu: "THIẾT BỊ: <tên>" và bảng "| Ký hiệu / Model: | МП-600 (MP-600) |".
_EQUIPMENT_TITLE_RE = re.compile(r"^THIẾT BỊ\s*:\s*(.+)$", re.IGNORECASE)
_MODEL_ROW_RE = re.compile(r"^\|\s*Ký hiệu\s*/\s*Model\s*:?\s*\|\s*([^|]+?)\s*\|", re.IGNORECASE)
_MODEL_PART_SPLIT_RE = re.compile(r"[()/&]")
_ASCII_MODEL_RE = re.compile(r"[a-z0-9]*(?:[a-z][0-9]|[0-9][a-z])[a-z0-9]*")
_MIN_MODEL_ROW_KEYWORD = 3  # "MP-6" → "mp6"; router chỉ khớp tới ranh giới số nên không trùng "mp600"
_SKIPPED_HEADINGS = {"lời nói đầu", "mục lục", "lời giới thiệu"}
# Cắt trên chữ CÒN DẤU: bỏ dấu thì "dùng"/"dung tích", "có"/"động cơ" trùng nhau.
_SUBJECT_CUT_RE = re.compile(r"\s+(?:có|kiểu|dùng|loại|cấp|từ)\s+|,|\s+[-–]\s+|\(|:")
_SUBJECT_MIN_WORDS = 2
_SUBJECT_MAX_WORDS = 10  # tên tiêu chuẩn dài ("yêu cầu chung về năng lực ...") không phải tên thiết bị
_APPENDIX_LOOKAHEAD = 8

# Chữ Kirin trông như chữ Latinh trong tên kiểu (ТН-12, ИO-30): người dùng gõ bằng chữ Latinh.
_HOMOGLYPHS = str.maketrans("тнаеоросхкмвиі", "thaeopocxkmbii")


@dataclass(frozen=True)
class DocCode:
    kind: str  # "QTKĐ" | "TCVN"
    number: str  # "1.061" | "6165" | "ISO/IEC 17025"
    year: int | None

    @property
    def label(self) -> str:
        return f"{self.kind} {self.number}" + (f":{self.year}" if self.year else "")


@dataclass(frozen=True)
class Section:
    number: str
    title: str
    level: int

    @property
    def label(self) -> str:
        return f"{self.number} {self.title}".strip()


@dataclass(frozen=True)
class DocProfile:
    file_stem: str
    code: DocCode | None
    title: str
    scope_heading: str
    scope_text: str
    sections: tuple[Section, ...]
    keywords: tuple[str, ...]
    subject: str = ""  # tên đối tượng đã bỏ dấu ("luu luong ke chat long"), router dùng để ghim tài liệu

    @property
    def label(self) -> str:
        return self.code.label if self.code else self.file_stem


def normalize_keyword(text: str) -> str:
    """Bỏ dấu, chữ thường, đổi chữ Kirin giống Latinh, bỏ mọi ký tự không phải chữ/số."""
    folded = unicodedata.normalize("NFD", text.lower().replace("đ", "d")).translate(_HOMOGLYPHS)
    return "".join(c for c in folded if c.isalnum() and not unicodedata.combining(c))


def parse_code(head: list[str], file_stem: str) -> DocCode | None:
    """Mã chính: mã QTKĐ đầu tiên ở đầu tệp, rồi mã trong tên tệp, rồi mã TCVN đầu tiên."""
    for line in head:
        match = _QTKD_RE.search(line)
        if match:
            return DocCode("QTKĐ", match.group(1), int(match.group(2)))
    match = _STEM_RE.search(file_stem)
    if match:
        return DocCode("QTKĐ", match.group(1), int(match.group(2)))
    for line in head:
        match = _TCVN_RE.search(line)
        if match:
            return DocCode("TCVN", match.group(1), int(match.group(2)))
    return None


def parse_title(head: list[str], code: DocCode | None) -> str:
    """Tên đối tượng/tiêu chuẩn nguyên văn từ khối đầu tệp; rỗng nếu không nhận ra."""
    outline = _OUTLINE_TITLE_RE.search(" ".join(head))
    if outline:
        return outline.group(1).strip()
    for i, line in enumerate(head):
        if _TITLE_END_RE.match(line):
            parts: list[str] = []
            for previous in reversed(head[max(0, i - _MAX_TITLE_LINES) : i]):
                if _TITLE_STOP_RE.match(previous) or _QTKD_RE.search(previous):
                    break
                part = previous.lstrip("# ").strip()
                if re.search(r"\w", part):  # bỏ dòng chỉ có dấu câu (".")
                    parts.insert(0, part)
            if parts:
                return " ".join(parts)
    if code and code.kind == "TCVN":
        for i, line in enumerate(head):
            if _TCVN_RE.search(line):
                for following in head[i + 1 : i + 4]:
                    if not _CODE_LIKE_RE.search(following):
                        return following.strip()
                break
    for line in head:
        equipment = _EQUIPMENT_TITLE_RE.match(line)
        if equipment:
            return equipment.group(1).strip()
    return ""


def parse_scope(lines: list[str], max_chars: int) -> tuple[str, str]:
    """(tiêu đề mục, nguyên văn) của mục "Phạm vi áp dụng/sử dụng".

    Mục lục cũng có dòng "1 Phạm vi áp dụng" (kèm số trang hoặc ngay sau là mục 2) nên chọn
    ứng viên có thân dài nhất.
    """
    best: tuple[str, str] = ("", "")
    for i, line in enumerate(lines):
        match = _SCOPE_RE.match(line.strip())
        if not match:
            continue
        inline = match.group(3).strip()
        if re.fullmatch(r"[\d.…\s]*", inline):
            inline = ""
        body = [inline] if inline else []
        for following in lines[i + 1 :]:
            stripped = following.strip()
            if _SECTION_BOUNDARY_RE.match(stripped):
                break
            if stripped and not _SCOPE_SKIP_RE.match(stripped):
                body.append(stripped)
        text = "\n".join(body)
        if len(text) > len(best[1]):
            best = (f"{match.group(1)} {match.group(2)}", text)
    heading, text = best
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + " …"
    return heading, text


def _appendix_title(following: list[str]) -> str:
    """Tên phụ lục nằm ở dòng thường ngay sau tiêu đề: "(Quy định)" rồi "Mẫu Biên bản kiểm định"."""
    parts: list[str] = []
    for line in following:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("#", "|")):
            break
        parts.append(stripped)
        if not stripped.startswith("("):
            break  # dòng tên thật (không phải ghi chú trong ngoặc) là dòng cuối cần lấy
    return " ".join(parts)


def _heading_sections(lines: list[str]) -> list[Section]:
    sections: list[Section] = []
    for i, line in enumerate(lines):
        match = _HEADING_RE.match(line.strip())
        if not match:
            continue
        text = match.group(2).strip()
        if text.lower() in _SKIPPED_HEADINGS:
            continue
        if text.startswith("(") and sections and sections[-1].number.lower().startswith("phụ lục"):
            last = sections[-1]
            sections[-1] = Section(last.number, f"{last.title} {text}".strip(), last.level)
            continue
        appendix = _APPENDIX_RE.match(text)
        if appendix:
            number = appendix.group(1)
            if any(s.number.lower() == number.lower() for s in sections):
                continue  # "Phụ lục C (kết thúc)": phần tiếp của phụ lục đã có
            title = appendix.group(2).strip() or _appendix_title(lines[i + 1 : i + 1 + _APPENDIX_LOOKAHEAD])
            sections.append(Section(number, title, 1))
            continue
        numbered = _NUMBERED_RE.match(text)
        if numbered:
            number = numbered.group(1).rstrip(".")
            title = numbered.group(2).split(":")[0].strip()
            sections.append(Section(number, title, number.count(".") + 1))
    return sections


def _plain_sections(lines: list[str]) -> list[Section]:
    """Tài liệu không có tiêu đề ``#``: lấy các dòng đánh số 1, 2, 3... đúng thứ tự (lượt đầu tiên)."""
    sections: list[Section] = []
    expected = 1
    for line in lines:
        match = _PLAIN_SECTION_RE.match(line.strip())
        if not match:
            continue
        number = int(match.group(1))
        if number == 1 and sections:
            break  # mục lục đã đủ, phần thân bắt đầu lại từ mục 1
        if number != expected:
            continue
        title = _PAGE_SUFFIX_RE.sub("", match.group(2).split(":")[0]).strip()
        if title:
            sections.append(Section(str(number), title, 1))
            expected += 1
    return sections


def parse_sections(lines: list[str]) -> tuple[Section, ...]:
    """Mục lục cấp 1-2: theo tiêu đề ``#`` nếu có mục 1, nếu không theo dòng đánh số liên tiếp."""
    from_headings = _heading_sections(lines)
    if any(s.number == "1" for s in from_headings):
        return tuple(s for s in from_headings if s.level <= 2)
    return tuple(_plain_sections(lines))


def parse_keywords(title: str) -> tuple[str, ...]:
    """Từ khoá kiểu thiết bị trong tên ("kiểu H3000-SP-70/700" → h3000sp70700, h3000)."""
    match = _MODEL_RE.search(title)
    if not match:
        return ()
    model = match.group(1).strip()
    keywords = [normalize_keyword(model)]
    first = re.split(r"[\s\-/]", model, maxsplit=1)[0]
    if re.search(r"\d", first) and re.search(r"[^\W\d_]", first):
        keywords.append(normalize_keyword(first))
    return tuple(dict.fromkeys(k for k in keywords if len(k) >= 4))


def parse_model_row_keywords(head: list[str]) -> tuple[str, ...]:
    """Từ khoá kiểu từ dòng "Ký hiệu / Model" của tài liệu thiết bị chuẩn mẫu.

    "МП-600 (MP-600)" → mp600; "M2800 (WIKA / Desgranges & Huot)" → m2800. Chỉ giữ phần có cả chữ
    lẫn số viết bằng chữ Latinh: người dùng gõ "MP-600", không gõ chữ Kirin "МП"; tên hãng thì không
    phải kiểu.
    """
    for line in head:
        match = _MODEL_ROW_RE.match(line)
        if not match:
            continue
        keywords = []
        for part in _MODEL_PART_SPLIT_RE.split(match.group(1)):
            compact = "".join(c for c in part.lower() if c.isalnum())
            if len(compact) >= _MIN_MODEL_ROW_KEYWORD and _ASCII_MODEL_RE.fullmatch(compact):
                keywords.append(compact)
        return tuple(dict.fromkeys(keywords))
    return ()


def parse_subject(title: str) -> str:
    """Tên đối tượng (bỏ dấu) ở đầu tên tài liệu, trước "có / kiểu / dùng / ," ...

    "VAN AN TOÀN CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar" → "van an toan"; "LƯU LƯỢNG KẾ CHẤT LỎNG" →
    "luu luong ke chat long". Rỗng khi quá ngắn để ghim tài liệu an toàn (< 2 từ).
    """
    head = fold(_SUBJECT_CUT_RE.split(unicodedata.normalize("NFC", title.lower()), maxsplit=1)[0]).strip(" .-")
    words = head.split()
    if len(words) < _SUBJECT_MIN_WORDS or len(words) > _SUBJECT_MAX_WORDS:
        return ""
    return head


def build_profile(file_stem: str, text: str, max_scope_chars: int) -> DocProfile:
    lines = text.splitlines()
    head = [line.strip() for line in lines[:_HEAD_LINES] if line.strip()]
    code = parse_code(head, file_stem)
    title = parse_title(head, code)
    scope_heading, scope_text = parse_scope(lines, max_scope_chars)
    return DocProfile(
        file_stem=file_stem,
        code=code,
        title=title,
        scope_heading=scope_heading,
        scope_text=scope_text,
        sections=parse_sections(lines),
        keywords=tuple(dict.fromkeys(parse_keywords(title) + parse_model_row_keywords(head))),
        subject=parse_subject(title),
    )


@lru_cache(maxsize=512)
def _cached_profile(path: str, mtime: float, file_stem: str, max_scope_chars: int) -> DocProfile:
    return build_profile(file_stem, Path(path).read_text(encoding="utf-8"), max_scope_chars)


def profile_for(file_stem: str) -> DocProfile | None:
    """Hồ sơ của tài liệu đã nạp; ``None`` nếu chưa có Markdown."""
    settings = get_settings()
    path = Path(settings.paths.markdown_dir) / f"{file_stem}.md"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return _cached_profile(str(path), mtime, file_stem, settings.doc_profile.max_scope_chars)
