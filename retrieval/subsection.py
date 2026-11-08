"""Định vị MỤC CON đánh số bên trong section cha để trích dẫn nguồn đúng mức chi tiết.

Chunker chỉ tách section tới một mức tiêu đề; các mục con như "6.3.2 Xác định độ chênh áp" hay
"5.3.1.2" nằm trong thân section cha dưới dạng dòng đánh số. Nguồn hiển thị chỉ mang
``section_path`` của section cha nên không phân biệt được 6.3.1 với 6.3.2 dù đoạn khớp nằm ở
mục con. ``locate`` tìm dòng tiêu đề mục con gần nhất đứng TRƯỚC đoạn neo trong thân section cha
và nối vào đường dẫn. Thuần chuỗi, không gọi dịch vụ ngoài.
"""

from __future__ import annotations

import re

_NUM_RE = re.compile(r"^\s*(\d+(?:\.\d+)+)\.?\s+(\S.*)$")
_LEADING_NUM_RE = re.compile(r"^\s*#*\s*(\d+(?:\.\d+)*)[\s.]")


def section_number(section_path: str) -> str | None:
    """Số mục của thành phần cuối trong đường dẫn ("6 X > 6.3 Y" -> "6.3")."""
    last = (section_path or "").split(">")[-1]
    m = _LEADING_NUM_RE.match(last + " ")
    return m.group(1) if m else None


def subsection_headings(parent_text: str, base_number: str, max_title_chars: int) -> list[tuple[int, str]]:
    """Các dòng tiêu đề mục con ``<base>.<n>...`` trong thân section: [(vị trí ký tự, "số tiêu_đề")]."""
    out: list[tuple[int, str]] = []
    pos = 0
    for line in parent_text.split("\n"):
        m = _NUM_RE.match(line.lstrip("#"))
        if m:
            num, title = m.group(1), m.group(2).strip()
            if (
                num.startswith(base_number + ".")
                and len(title) <= max_title_chars
                and not title[0].isdigit()
                and not title.endswith((";", ","))
            ):
                out.append((pos, f"{num} {title}"))
        pos += len(line) + 1
    return out


def locate(
    section_path: str,
    parent_text: str,
    anchor_text: str,
    *,
    max_title_chars: int = 120,
) -> str:
    """Trả ``section_path`` kèm mục con chứa ``anchor_text``; giữ nguyên nếu không xác định được."""
    base = section_number(section_path)
    if not base or not parent_text or not anchor_text.strip():
        return section_path
    headings = subsection_headings(parent_text, base, max_title_chars)
    if not headings:
        return section_path
    at = parent_text.find(anchor_text)
    if at < 0:
        at = parent_text.find(anchor_text[:80])
    if at < 0:
        return section_path
    best = None
    for pos, heading in headings:
        if pos <= at:
            best = heading
        else:
            break
    if best is None:
        return section_path
    # Mục con lồng nhau (6.3.2 rồi 6.3.2.1): giữ mục sâu nhất đứng trước neo.
    return f"{section_path} > {best}"
