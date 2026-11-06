"""Số trang của một mục, lấy từ chính Mục lục in trong tài liệu (không suy đoán).

Mỗi QTKĐ có Mục lục dạng ``5.1 Điều kiện kiểm định 6`` (số mục, tên, số trang). Mục không có
dòng riêng trong Mục lục (mục con sâu hơn) lấy trang của mục cha gần nhất và đánh dấu
``exact=False``; mục không khớp tên trong Mục lục thì không trả trang.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from core.settings_loader import get_settings

_TOC_HEAD = re.compile(r"^\s*mục\s+lục\s*$", re.IGNORECASE)
_TOC_LINE = re.compile(r"^(?P<num>\d+(?:\.\d+)*|Phụ lục [A-Z])\s+(?P<title>.+?)\s+(?P<page>\d{1,3})\s*$")
_SECTION_KEY = re.compile(r"^(\d+(?:\.\d+)*|Phụ lục [A-Z])\b")
_MAX_SCAN = 120
_MAX_ORPHANS = 2


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return re.sub(r"[^a-z0-9]+", "", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def parse_toc(lines: list[str]) -> dict[str, tuple[int, str]]:
    """{số mục: (trang, tên đã chuẩn hóa)} từ các dòng đầu file markdown."""
    start = next((i for i, ln in enumerate(lines) if _TOC_HEAD.match(ln)), None)
    if start is None:
        return {}
    out: dict[str, tuple[int, str]] = {}
    orphans = 0
    for ln in lines[start + 1 : start + 1 + _MAX_SCAN]:
        text = ln.strip()
        if not text:
            continue
        m = _TOC_LINE.match(text)
        if m:
            out.setdefault(m.group("num"), (int(m.group("page")), _fold(m.group("title"))))
            orphans = 0
        else:
            orphans += 1
            if out and orphans > _MAX_ORPHANS:
                break
    return out


@lru_cache(maxsize=64)
def _toc(file_stem: str) -> dict[str, tuple[int, str]]:
    path = Path(get_settings().paths.markdown_dir) / f"{file_stem}.md"
    try:
        with path.open(encoding="utf-8") as f:
            return parse_toc([next(f, "") for _ in range(_MAX_SCAN + 40)])
    except OSError:
        return {}


def page_for(file_stem: str, section_path: str) -> tuple[int | None, bool]:
    """(trang, chính xác?) của mục cuối trong ``section_path``; (None, False) nếu không rõ."""
    toc = _toc(file_stem)
    if not toc:
        return None, False
    last = section_path.split(">")[-1].strip()
    m = _SECTION_KEY.match(last)
    if not m:
        return None, False
    key = m.group(1)
    title = _fold(last[m.end() :])
    parts = key.split(".") if key[0].isdigit() else [key]
    while parts:
        cand = ".".join(parts)
        if cand in toc:
            page, toc_title = toc[cand]
            exact = len(parts) == len(key.split(".")) if key[0].isdigit() else True
            if exact and title and toc_title and not (toc_title[:12] in title or title[:12] in toc_title):
                return None, False
            return page, exact
        parts = parts[:-1] if key[0].isdigit() else []
    return None, False


def label(file_stem: str, section_path: str) -> str:
    """"tr. 7" (chính xác) / "từ tr. 7" (theo mục cha) / "" (không rõ)."""
    page, exact = page_for(file_stem, section_path)
    if page is None:
        return ""
    return f"tr. {page}" if exact else f"từ tr. {page}"
