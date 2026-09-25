"""Chia văn bản QTKĐ thành các mục theo tiêu đề Markdown.

Cấu trúc ĐLVN ổn định về *nội dung* nhưng không ổn định về *số mục*: QTKĐ 1.061
đánh số §1 Phạm vi / §2 Thuật ngữ / §3 Các phép kiểm định / §4 Phương tiện /
§5.1 Điều kiện / §7 Xử lý chung, còn 1.062, 1.071, 1.160 lại dồn lại thành
§2 Các phép kiểm định / §4.1 Điều kiện / §6 Xử lý chung. Vì vậy luật tra mục
theo *tiêu đề* chứ không theo số, và trả rỗng khi không thấy — thà thiếu còn hơn
gán nhầm mục (spec §7, §12).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from knowledge import vnnum

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)
_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+(.*)$")
# Nhãn phụ lục phải là MỘT chữ cái đứng riêng, B..Z (bỏ A), không theo sau bởi
# chữ cái/chữ số khác: "Phụ lục B", "PHỤ LỤC C (tiếp theo)" khớp; "Phụ lục này",
# "Phụ lục Bảng", "Phụ lục A (tiếp theo)" không khớp (K12).
_APPENDIX_LABEL_RE = re.compile(r"^phụ\s*lục\s+([b-z])(?![^\W_])", re.IGNORECASE)


@dataclass(frozen=True)
class Section:
    """Một mục: số (nếu có), tiêu đề, cấp, đường dẫn, và khoảng ký tự tuyệt đối."""

    number: str | None
    title: str
    level: int
    path: str
    heading: str
    start: int
    body_start: int
    end: int
    body: str


def split_sections(text: str) -> list[Section]:
    """Trả mọi mục theo tiêu đề ``#``; rỗng nếu văn bản không có tiêu đề."""
    if not text:
        return []
    headings = list(_HEADING_RE.finditer(text))
    sections: list[Section] = []
    for index, match in enumerate(headings):
        level = len(match.group(1))
        raw_title = match.group(2).strip()
        number_match = _NUMBER_RE.match(raw_title)
        if number_match:
            number = number_match.group(1)
            title = number_match.group(2).strip()
        else:
            number, title = None, raw_title
        body_start = match.end()
        if body_start < len(text) and text[body_start] == "\n":
            body_start += 1
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        path = f"{number} {title}".strip() if number else title
        sections.append(
            Section(
                number=number,
                title=title,
                level=level,
                path=path,
                heading=raw_title,
                start=match.start(),
                body_start=body_start,
                end=end,
                body=text[body_start:end],
            )
        )
    return sections


def _normalize(text: str) -> str:
    return vnnum.normalize_spaces(text).lower()


def find_section(sections: list[Section], *keywords: str) -> Section | None:
    """Mục đầu tiên có tiêu đề chứa ĐỦ mọi ``keywords`` (đã chuẩn hóa, thứ tự bất kỳ).

    Trả ``None`` khi không khớp — luật gọi phải xử lý an toàn bằng danh sách rỗng.
    """
    needles = [_normalize(keyword) for keyword in keywords]
    for section in sections:
        haystack = _normalize(section.title)
        if all(needle in haystack for needle in needles):
            return section
    return None


def _first_plain_appendix_stop(text: str, start: int) -> int | None:
    """Vị trí dòng đầu tiên (từ ``start``) mang nhãn phụ lục B..Z đứng riêng.

    Chỉ xét dòng bắt đầu bằng nhãn "Phụ lục <chữ cái B..Z>"; câu văn nhắc
    "Phụ lục B" giữa dòng hay "Phụ lục này"/"Phụ lục Bảng" không tính. Trả
    ``None`` nếu không có.
    """
    offset = start
    for line in text[start:].split("\n"):
        if _APPENDIX_LABEL_RE.match(line.strip()):
            return offset + (len(line) - len(line.lstrip()))
        offset += len(line) + 1
    return None


def find_appendix_section(text: str) -> Section | None:
    """Mục "Phụ lục A" với thân MỞ RỘNG tới điểm dừng sớm nhất (K12):

    (a) heading mang nhãn phụ lục B..Z đứng riêng, hoặc
    (b) dòng riêng mang nhãn phụ lục B..Z đứng riêng ("Phụ lục B", "PHỤ LỤC C",
        "Phụ lục B (tiếp theo)"), hoặc hết tài liệu.

    Heading con bên trong Phụ lục A ("(Quy định)", "Mẫu biên bản...",
    "BIÊN BẢN KIỂM ĐỊNH..."), "Phụ lục A (tiếp theo)/(kết thúc)" và các dòng bắt
    đầu bằng một TỪ như "Phụ lục này..." KHÔNG kết thúc mục. Chỉ luật ``phuluc_a``
    dùng hàm này; các luật khác giữ nguyên ngữ nghĩa ``find_section`` (dừng ở
    heading kế tiếp bất kỳ cấp nào).
    """
    sections = split_sections(text)
    section = find_section(sections, "phụ lục a")
    if section is None:
        return None
    candidates: list[int] = []
    for candidate in sections:
        if candidate.start <= section.start:
            continue
        if _APPENDIX_LABEL_RE.match(_normalize(candidate.title)):
            candidates.append(candidate.start)
            break
    plain_stop = _first_plain_appendix_stop(text, section.body_start)
    if plain_stop is not None:
        candidates.append(plain_stop)
    end = min(candidates) if candidates else len(text)
    if end == section.end:
        return section
    return replace(section, end=end, body=text[section.body_start:end])
