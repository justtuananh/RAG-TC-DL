"""Mục lục suy ra cho Markdown không có tiêu đề ``#`` nhưng có mục đánh số.

Tài liệu thiết bị chuẩn mẫu (A_*), TCVN ISO/IEC 17025, TCVN 6165 được trích ra không có tiêu đề Word nên
Markdown không có ``#``. Các dòng "1. TỔNG QUAN", "4.1 Tính khách quan", "Phụ lục A" vẫn là mục thật:
``promote_numbered_headings`` đưa chúng thành ``#``/``##``. Chunker (section để nhúng, trích dẫn có số mục)
và ``retrieval.doc_sections`` (trả lời nguyên văn theo mục, mục từ thuật ngữ) dùng chung một cách hiểu.
"""

from __future__ import annotations

import re

_HEADING_RE = re.compile(r"^#{1,6}\s+\S")
_NUMBERED_HEADING_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2})?)\.?\s+(\S.*)$")
_APPENDIX_HEADING_RE = re.compile(r"^Phụ lục\s+[A-Z]\b.{0,80}$")
_MAX_NUMBERED_HEADING_CHARS = 100
_MAX_DOTTED_TITLE_WORDS = 8
_MIN_NUMBERED_SECTIONS = 2
PREAMBLE_HEADING = "Thông tin chung"


def has_headings(text: str) -> bool:
    return any(_HEADING_RE.match(line) for line in text.split("\n"))


def _is_heading_title(title: str) -> bool:
    """Tên mục, không phải mệnh đề đánh số: bắt đầu bằng chữ hoa, không kết thúc bằng ":" ("5.5 Phòng thí
    nghiệm phải:"), dấu chấm cuối chỉ chấp nhận ở tên ngắn ("7.6 Đánh giá độ không đảm bảo đo.")."""
    if not title[0].isupper() or title.endswith(":"):
        return False
    return not title.endswith(".") or len(title.split()) <= _MAX_DOTTED_TITLE_WORDS


def _numbered_candidates(lines: list[str]) -> list[tuple[int, tuple[int, ...]]]:
    """(dòng, số mục) của các dòng trông như tiêu đề "1. TỔNG QUAN" / "4.1 Tính khách quan".

    Loại câu nội dung đánh số ("1.1. Vai trò ...: <đoạn dài>", "4.1.1 Hoạt động ... phải ... ."), giá trị
    đo ("5 bar") - xem ``_is_heading_title``.
    """
    out = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        match = _NUMBERED_HEADING_RE.match(stripped)
        if (
            match
            and len(stripped) <= _MAX_NUMBERED_HEADING_CHARS
            and _is_heading_title(match.group(2).rstrip())
        ):
            out.append((i, tuple(int(n) for n in match.group(1).split("."))))
    return out


def _top_level_run(candidates: list[tuple[int, tuple[int, ...]]]) -> list[int]:
    """Dãy mục cấp 1 liên tiếp 1, 2, 3... dài nhất (bằng nhau thì dãy sau: mục lục đứng trước thân)."""
    tops = [(i, nums[0]) for i, nums in candidates if len(nums) == 1]
    best: list[int] = []
    for start, (_, number) in enumerate(tops):
        if number != 1:
            continue
        run = [tops[start][0]]
        for line_index, next_number in tops[start + 1 :]:
            if next_number == len(run) + 1:
                run.append(line_index)
            elif next_number == 1:
                break
        if len(run) >= len(best):
            best = run
    return best


def _heading_levels(lines: list[str]) -> dict[int, int] | None:
    """Dòng → cấp tiêu đề (1 hoặc 2) cho thân văn bản; None khi không đủ mục đánh số."""
    candidates = _numbered_candidates(lines)
    run = _top_level_run(candidates)
    if len(run) < _MIN_NUMBERED_SECTIONS:
        return None
    levels: dict[int, int] = dict.fromkeys(run, 1)
    appendices = [
        i for i in range(run[0], len(lines)) if _APPENDIX_HEADING_RE.match(lines[i].strip())
    ]
    levels.update(dict.fromkeys(appendices, 1))
    top_numbers = {line_index: number for number, line_index in enumerate(run, 1)}
    current, last_sub = None, 0
    events = sorted([(i, None) for i in appendices] + [c for c in candidates if c[0] >= run[0]])
    for line_index, nums in events:
        if nums is None:  # sau phụ lục không còn mục con đánh số của thân văn bản
            current = None
        elif line_index in top_numbers:
            current, last_sub = top_numbers[line_index], 0
        elif len(nums) == 2 and nums[0] == current and nums[1] > last_sub:
            levels[line_index] = 2
            last_sub = nums[1]
    return levels


def _split_oversized(blocks: list[tuple[str, list[str]]], limit: int, window: int) -> list[str]:
    """Mục dài hơn ``limit`` (bảng thuật ngữ TCVN 6165 ~48K ký tự) chia theo ranh giới dòng thành
    "<tiêu đề> (phần i)" khoảng ``window`` ký tự - không cắt giữa một dòng bảng."""
    out: list[str] = []
    for heading, body in blocks:
        if len("\n".join(body)) <= limit:
            out.extend([heading, *body])
            continue
        parts: list[list[str]] = [[]]
        size = 0
        for line in body:
            if size + len(line) > window and parts[-1]:
                parts.append([])
                size = 0
            parts[-1].append(line)
            size += len(line) + 1
        for i, part in enumerate(parts, 1):
            out.extend([f"{heading} (phần {i})", *part])
    return out


def promote_numbered_headings(
    text: str, *, split_limit: int | None = None, split_window: int = 0
) -> str | None:
    """Đưa dòng mục cấp 1-2 và "Phụ lục X" thành tiêu đề ``#``/``##``; ``None`` khi không có ít nhất 2 mục
    cấp 1 liên tiếp (để người gọi tự xử lý như cũ).

    Mục lục ở đầu tệp cũng đánh số 1, 2, 3...: lấy dãy cuối cùng (thân văn bản). Phần trước mục 1
    (tên, bảng kiểu/số hiệu, mục lục, lời nói đầu) vào mục "Thông tin chung" thay vì bị bỏ. ``split_limit``:
    mục dài hơn thì chia "(phần i)" khoảng ``split_window`` ký tự (chunker cần, trả lời theo mục thì không).
    """
    lines = text.split("\n")
    levels = _heading_levels(lines)
    if levels is None:
        return None
    first = min(levels)
    blocks: list[tuple[str, list[str]]] = []
    if any(line.strip() for line in lines[:first]):
        blocks.append((f"# {PREAMBLE_HEADING}", lines[:first]))
    for i in range(first, len(lines)):
        if i in levels:
            blocks.append((f"{'#' * levels[i]} {lines[i].strip()}", []))
        else:
            blocks[-1][1].append(lines[i])
    if split_limit is None:
        return "\n".join(line for heading, body in blocks for line in (heading, *body))
    return "\n".join(_split_oversized(blocks, split_limit, split_window))
