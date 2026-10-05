"""Đoạn trích nguồn cho panel "Nguồn của câu trả lời".

Đoạn con khớp nhất của một mục hay là dòng định nghĩa ký hiệu ("trong đó: $A_{0s}$ là …")
hoặc câu dẫn ("… được tính từ công thức sau:"); công thức là một đoạn con riêng chỉ có LaTeX
nên ít khi lọt top. Chỉ hiện đoạn con thì nguồn trích không có công thức dù câu trả lời có
(QTKĐ 1.159 mục 6.3.2, đo 2026-10-05). ``build_quote`` mở rộng từng đoạn con thành khúc
nguyên văn của mục cha có đủ công thức nó nói tới; không viết lại chữ nào.
"""

from __future__ import annotations

import re

_BLOCK = re.compile(r"\S(?:.|\n(?!\s*\n))*")  # khối Markdown: các dòng liền nhau
_TRONG_DO = re.compile(r"^trong đó\b", re.IGNORECASE)
_GAP = "…"


def _blocks(parent: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _BLOCK.finditer(parent)]


def _is_formula(text: str) -> bool:
    """Khối công thức: bảng chứa LaTeX (cách ingestion đặt công thức hiển thị) hoặc ``$$…$$``."""
    if text.startswith("$$"):
        return True
    lines = text.splitlines()
    return "$" in text and all(line.lstrip().startswith("|") for line in lines)


def _is_lead_in(text: str) -> bool:
    return text.rstrip().endswith(":")


def _is_definition(text: str) -> bool:
    return bool(_TRONG_DO.match(text)) or (" là " in text and not _is_lead_in(text))


def _formula_above(texts: list[str], i: int) -> list[int]:
    """Khối công thức liền trên khối ``i`` cùng câu dẫn của nó (nếu có)."""
    k = i
    while k > 0 and _is_formula(texts[k - 1]):
        k -= 1
    if k == i:
        return []
    if k > 0 and _is_lead_in(texts[k - 1]) and not _is_formula(texts[k - 1]):
        k -= 1
    return list(range(k, i))


def _formula_below(texts: list[str], i: int) -> list[int]:
    k = i + 1
    while k < len(texts) and _is_formula(texts[k]):
        k += 1
    return list(range(i + 1, k))


def _definition_context(texts: list[str], i: int) -> list[int]:
    """Dòng định nghĩa ký hiệu: dòng "trong đó" của danh sách và công thức ngay trên nó."""
    j = i
    while j >= 0 and _is_definition(texts[j]) and not _is_formula(texts[j]):
        if _TRONG_DO.match(texts[j]):
            above = _formula_above(texts, j)
            return above + [j] if above else []
        j -= 1
    return []


def _expand(texts: list[str], first: int, last: int) -> set[int]:
    keep = set(range(first, last + 1))
    head, tail = texts[first], texts[last]
    if _is_formula(head):
        keep.update(_formula_above(texts, first + 1))  # nhóm công thức chứa ``first`` + câu dẫn
    elif _is_definition(head):
        keep.update(_definition_context(texts, first))
    if _is_lead_in(tail):
        keep.update(_formula_below(texts, last))
    return keep


def _locate(parent: str, spans: list[tuple[int, int]], anchor: str) -> tuple[int, int] | None:
    text = anchor.strip()
    pos = parent.find(text)
    if pos < 0:
        pos = parent.find(text[:80])
        end = pos + len(text[:80])
    else:
        end = pos + len(text)
    if pos < 0:
        return None
    hit = [n for n, (a, b) in enumerate(spans) if a < end and pos < b]
    return (hit[0], hit[-1]) if hit else None


def build_quote(parent: str, anchors: list[str]) -> str:
    """Khúc nguyên văn của ``parent`` chứa mọi đoạn con ``anchors`` và công thức chúng nói tới.

    Câu dẫn kết thúc bằng ":" kéo theo các khối công thức liền sau; khối công thức kéo theo
    câu dẫn liền trước; dòng định nghĩa trong danh sách "trong đó" kéo theo công thức ngay
    trên danh sách (và câu dẫn của công thức). Các khối giữ thứ tự trong mục; chỗ bỏ qua
    đánh dấu "…". Đoạn con không tìm thấy trong mục cha được trích nguyên văn.
    """
    if not anchors:
        return ""
    spans = _blocks(parent)
    texts = [parent[a:b] for a, b in spans]
    keep: set[int] = set()
    missing: list[str] = []
    for anchor in anchors:
        found = _locate(parent, spans, anchor)
        if found is None:
            missing.append(anchor.strip())
        else:
            keep |= _expand(texts, *found)
    parts: list[str] = []
    prev = None
    for n in sorted(keep):
        if prev is not None and n > prev + 1:
            parts.append(_GAP)
        parts.append(texts[n])
        prev = n
    return "\n\n".join(parts + missing)
