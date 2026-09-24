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
from dataclasses import dataclass

from knowledge import vnnum

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)
_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+(.*)$")


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
