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


def linearize_tables(text: str) -> str:
    """Thay mỗi khối bảng markdown phân tích được bằng các dòng "- TT. Tên: cột = giá trị"."""
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
            conv = _one(block)
        except (IndexError, ValueError):
            conv = None
        out.extend(conv if conv else block)
        i = j
    return "\n".join(out)
