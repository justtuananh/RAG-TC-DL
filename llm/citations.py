"""Trích dẫn tất định: khối "Nguồn:" dựng từ chính các nguồn truy hồi, không để mô hình tự viết.

Sau khi sinh câu trả lời: (1) bỏ khối nguồn do mô hình tự viết; (2) bỏ [n] trỏ tới nguồn không có;
(3) nếu câu trả lời có nội dung mà không còn [n] nào thì gắn nguồn điểm rerank cao nhất mà đoạn
trích chứa con số/từ khóa của câu trả lời, không có thì ghi "chưa xác định được nguồn";
(4) nối khối "Nguồn:" gồm tên văn bản, mục sâu nhất, trang ("tr. ~N" nếu trang chỉ suy ra từ mục cha).
Câu từ chối không thêm gì.
"""

from __future__ import annotations

import re
import unicodedata

from core.settings_loader import get_settings
from llm.guards import REFUSAL_SENTENCE

UNKNOWN_SOURCE = "chưa xác định được nguồn"

_CITE = re.compile(r"\s*\[(\d+(?:\s*,\s*\d+)*)\]")
_OWN_BLOCK = re.compile(r"\n\s*(?:\*\*|#+\s*)?(?:Nguồn|Trích dẫn|Tài liệu tham khảo)\s*(?:\*\*)?\s*:")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def strip_own_block(body: str) -> str:
    """Bỏ khối "Nguồn:/Trích dẫn:" mô hình tự viết ở cuối câu trả lời."""
    m = _OWN_BLOCK.search(body)
    return body[: m.start()].rstrip() if m else body


def drop_invalid_refs(body: str, valid: set[int]) -> str:
    """Giữ trong mỗi [n] / [n, m] chỉ các số là nguồn có thật; nhóm rỗng thì bỏ cả ngoặc."""

    def repl(m: re.Match) -> str:
        keep = [n for n in re.split(r"\s*,\s*", m.group(1)) if int(n) in valid]
        return f" [{', '.join(keep)}]" if keep else ""

    return _CITE.sub(repl, body)


def cited_indices(body: str) -> list[int]:
    out: list[int] = []
    for m in _CITE.finditer(body):
        for n in re.split(r"\s*,\s*", m.group(1)):
            if int(n) not in out:
                out.append(int(n))
    return out


def _source_text(src: dict) -> str:
    return " ".join(str(src.get(k) or "") for k in ("child_text", "parent_text", "snippet"))


def pick_source(body: str, sources: list[dict], *, min_len: int, min_hits: int, limit: int = 1) -> list[int]:
    """Nguồn điểm rerank cao nhất mà đoạn trích chứa số/từ khóa của câu trả lời."""
    numbers = {n for n in _NUMBER.findall(body) if len(n.replace(".", "").replace(",", "")) >= 2}
    words = {_fold(w) for w in _WORD.findall(body) if len(w) >= min_len}
    ranked = sorted(sources, key=lambda s: s.get("rerank_score", 0.0), reverse=True)
    picked: list[int] = []
    for src in ranked:
        text = _source_text(src)
        folded = _fold(text)
        if numbers:
            ok = any(re.search(r"(?<![\d.,])" + re.escape(n) + r"(?![\d])", text) for n in numbers)
        else:
            ok = sum(1 for w in words if w in folded) >= min_hits
        if ok:
            picked.append(src["index"])
            if len(picked) >= limit:
                break
    return picked


def source_line(src: dict, title: str = "") -> str:
    """"[n] <file_stem> (<tên văn bản>) — <mục sâu nhất>, tr. <trang>"."""
    stem = src["file_stem"]
    label = f"{stem} ({title})" if title else stem
    section = (src.get("section_path") or "").split(">")[-1].strip()
    page = src.get("page")
    page_txt = ""
    if page is not None:
        page_txt = f"tr. {page}" if src.get("page_exact", True) else f"tr. ~{page}"
    where = ", ".join(x for x in (section, page_txt) if x)
    return f"[{src['index']}] {label}" + (f" — {where}" if where else "")


def add_citations(body: str, sources: list[dict], title_for=None) -> str:
    """Hậu xử lý trích dẫn (xem docstring module). ``title_for(file_stem) -> str`` tra tên văn bản."""
    cfg = get_settings().llm.citation
    if not cfg.enabled or not body.strip() or REFUSAL_SENTENCE in body:
        return body
    text = strip_own_block(body)
    by_idx = {s["index"]: s for s in sources}
    text = drop_invalid_refs(text, set(by_idx))
    used = [n for n in cited_indices(text) if n in by_idx]
    unknown = False
    if not used and by_idx:
        used = pick_source(
            text, sources, min_len=cfg.min_keyword_len, min_hits=cfg.min_keyword_hits, limit=cfg.max_auto_sources
        )
        if used:
            text = text.rstrip() + " " + "".join(f"[{n}]" for n in used)
        else:
            unknown = True
    elif not used:
        unknown = True
    if unknown:
        return f"{text}\n\nNguồn: {UNKNOWN_SOURCE}"
    title_for = title_for or (lambda stem: "")
    lines = [source_line(by_idx[n], title_for(by_idx[n]["file_stem"])) for n in sorted(used)]
    return f"{text}\n\nNguồn:\n" + "\n".join(f"- {ln}" for ln in lines)
