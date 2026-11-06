"""Chuyển bảng markdown có cột TT thành các dòng văn bản "Tên: nhãn cột = giá trị".

Model 7B hay đọc nhầm cột/dòng của bảng markdown có tiêu đề hai tầng (hàng tiêu đề gộp ô, hàng
nhãn con nằm dưới dòng phân cách) và dòng nối tiếp (ô TT và tên trống). Hàm thuần túy, không
mạng: giữ nguyên từng ký tự của giá trị ô; bảng không phân tích chắc chắn được thì trả nguyên văn.
"""

from __future__ import annotations

import re

_TT = re.compile(r"^(TT|STT|No\.?|Số TT)$", re.IGNORECASE)
_SEQ = re.compile(r"^\d+(\.\d+)*\.?$")
_LONG = 30
_ABBR = re.compile(r"tắt là", re.IGNORECASE)
_SEP_CELL = re.compile(r"^:?-{3,}:?$")


def _cells(line: str) -> list[str]:
    s = line.strip()
    s = s[1:] if s.startswith("|") else s
    s = s[:-1] if s.endswith("|") else s
    return [c.strip() for c in s.split(" | ")] if " | " in s else [c.strip() for c in s.split("|")]


def _labels(header_rows: list[list[str]], n: int) -> list[str]:
    """Nhãn mỗi cột = tầng tiêu đề dưới cùng có giá trị (nhãn ngắn, đỡ tốn ngữ cảnh); tầng
    trên có ô gộp trống nên không dùng làm nhãn riêng."""
    labels = []
    for j in range(n):
        parts: list[str] = []
        for k, row in enumerate(header_rows):
            v = row[j]
            if not v and k < len(header_rows) - 1 and any(r[j] for r in header_rows[k + 1 :]):
                i = j
                while i > 0 and not row[i]:
                    i -= 1
                v = row[i]
            if v and v not in parts:
                parts.append(v)
        labels.append(parts[-1] if parts else "")  # nhãn ngắn: tầng dưới cùng
    return labels


def _short(label: str) -> str:
    """Nhãn dài kiểu "Cấp chính xác hoặc độ chính xác hoặc sai số ..." lặp ở MỌI dòng làm tốn ngữ
    cảnh: rút về cụm đầu trước " hoặc " (nhãn đầy đủ in một lần ở dòng chú giải cột)."""
    if len(label) <= _LONG:
        return label
    head = re.split(r"\s+hoặc\s+", label, maxsplit=1)[0].strip(" /")
    return head or label


def _value(v: str) -> str:
    """Ô có định nghĩa viết tắt ("sau đây viết tắt là X") đặt trong «» để X không bị đọc thành
    viết tắt của tên thiết bị đầu dòng."""
    return f"«{v}»" if _ABBR.search(v) else v


def _one(lines: list[str]) -> list[str] | None:
    rows = [_cells(ln) for ln in lines]
    n = len(rows[0])
    if n < 3 or any(len(r) != n for r in rows):
        return None
    sep = next((i for i, r in enumerate(rows) if all(_SEP_CELL.match(c) for c in r)), None)
    if sep is None or sep == 0 or not _TT.match(rows[0][0]):
        return None
    body = rows[sep + 1 :]
    first = next((i for i, r in enumerate(body) if _SEQ.match(r[0])), None)
    if first is None:
        return None
    labels = _labels(rows[:sep] + body[:first], n)
    if any(not labels[j] for j in (1, 2)):
        return None
    out: list[str] = []
    short = [_short(x) for x in labels]
    legend = [f'(Cột "{short[j]}" = "{labels[j]}")' for j in range(2, n) if short[j] != labels[j]]
    out.extend(legend)
    for r in body[first:]:
        pairs = [f"{short[j]} = {_value(r[j])}" for j in range(2, n) if r[j]]
        if _SEQ.match(r[0]):
            out.append(f"- {r[0]}. {r[1]}: " + "; ".join(pairs))
        elif not r[0] and not r[1] and pairs:  # dòng nối tiếp của dòng trước
            out[-1] += " ; (tiếp) " + "; ".join(pairs)
        else:
            return None
    return out


def _value_table(lines: list[str]) -> list[str] | None:
    """Bảng tra giá trị không có cột TT: một hàng tiêu đề (ô trên gộp nhiều cột), một hàng nhãn con
    (cột đầu trống) rồi các hàng dữ liệu đủ ô ("Giới hạn đo | cấp 0,01 | cấp 0,02 ..."). Mỗi hàng
    thành một dòng "- nhãn hàng = giá trị hàng: nhãn cột = giá trị; ..." để model 7B khỏi đọc lệch
    cột/hàng; không đúng dạng này thì None (giữ nguyên bảng)."""
    rows = [_cells(ln) for ln in lines]
    n = len(rows[0])
    if n < 3 or len(rows) < 5 or any(len(r) != n for r in rows):
        return None
    top, sep, sub, body = rows[0], rows[1], rows[2], rows[3:]
    if not all(_SEP_CELL.match(c) for c in sep) or not top[0] or not top[1]:
        return None
    if sub[0] or not all(sub[1:]) or any(not all(r) for r in body):
        return None
    labels: list[str] = []
    current = ""
    for j in range(1, n):
        current = top[j] or current
        labels.append(f"{_short(current)} {sub[j]}")
    legend = [
        f'(Nhãn "{_short(top[j])}" = "{top[j]}")' for j in range(1, n) if top[j] and _short(top[j]) != top[j]
    ]
    out = list(legend)
    for r in body:
        pairs = "; ".join(f"{labels[j - 1]} = {r[j]}" for j in range(1, n))
        out.append(f"- {top[0]} = {r[0]}: {pairs}")
    return out


_WORD = re.compile(r"\w+", re.UNICODE)
_MIN_KEYWORD = 3


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.casefold()) if len(w) >= _MIN_KEYWORD}


def _prune_block(block: list[str], query_words: set[str], max_rows: int) -> list[str] | None:
    """Bảng dài (> max_rows dòng dữ liệu): giữ dòng tiêu đề + các dòng có từ khóa của câu hỏi; None
    nếu không cần/không chọn chắc được dòng nào (giữ nguyên)."""
    cells = [_cells(ln) for ln in block]
    sep = next((i for i, r in enumerate(cells) if all(_SEP_CELL.match(c) for c in r)), None)
    if sep is None or len(block) - sep - 1 <= max_rows:
        return None
    head_end = sep + 1
    while head_end < len(block) and not cells[head_end][0].strip():
        if len(cells[head_end]) > 1 and cells[head_end][1].strip():
            head_end += 1  # hàng nhãn con của tiêu đề hai tầng
        else:
            break
    groups: list[list[int]] = []
    for i in range(head_end, len(block)):
        row = cells[i]
        if groups and not row[0].strip() and not (row[1].strip() if len(row) > 1 else ""):
            groups[-1].append(i)  # dòng nối tiếp thuộc dòng trước
        else:
            groups.append([i])
    if len(groups) <= max_rows:
        return None
    sets = [_words(" ".join(block[i] for i in g)) for g in groups]
    # Từ có ở hơn nửa số dòng không giúp chọn dòng.
    keys = {w for w in query_words if sum(w in s for s in sets) * 2 <= len(sets)}
    kept = [g for g, s in zip(groups, sets, strict=True) if s & keys]
    if not kept or len(kept) == len(groups):
        return None
    out = block[:head_end] + [block[i] for g in kept for i in g]
    return out + [f"(Bảng rút gọn: giữ {len(kept)}/{len(groups)} dòng khớp câu hỏi)"]


def prune_long_tables(text: str, query: str, max_rows: int) -> str:
    """Bảng markdown dài chỉ giữ dòng tiêu đề và các dòng khớp từ khóa của ``query``; không đưa nguyên
    bảng dài vào ngữ cảnh. ``max_rows`` <= 0 hoặc ``query`` rỗng: giữ nguyên."""
    query_words = _words(query)
    if max_rows <= 0 or not query_words:
        return text
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("|"):
            out.append(lines[i])
            i += 1
            continue
        j = i
        while j < len(lines) and lines[j].lstrip().startswith("|"):
            j += 1
        block = lines[i:j]
        try:
            pruned = _prune_block(block, query_words, max_rows)
        except IndexError:
            pruned = None
        out.extend(pruned or block)
        i = j
    return "\n".join(out)


def linearize_tables(text: str, *, value_tables: bool = True) -> str:
    """Thay mỗi khối bảng markdown phân tích được bằng các dòng "- TT. Tên: cột = giá trị"
    (``value_tables``: cả bảng tra giá trị không có cột TT, xem ``_value_table``)."""
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("|"):
            out.append(lines[i])
            i += 1
            continue
        j = i
        while j < len(lines) and lines[j].lstrip().startswith("|"):
            j += 1
        block = lines[i:j]
        try:
            conv = _one(block) or (_value_table(block) if value_tables else None)
        except (IndexError, ValueError):
            conv = None
        out.extend(conv if conv else block)
        i = j
    return "\n".join(out)
