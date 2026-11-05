"""Tên tài liệu (đối tượng của QTKĐ) rút từ khối tiêu đề đầu file markdown nguồn.

Định dạng chung của mọi QTKĐ: dòng ``QTKĐ <mã> : <năm>``, tiếp đó là tên đối tượng
(một hoặc nhiều dòng), kết thúc ở dòng ``QUY TRÌNH KIỂM ĐỊNH``. Không có bảng tra cứng:
tài liệu nạp thêm cùng định dạng tự có tên. Không tìm được thì trả chuỗi rỗng.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_DIRS = (Path("/app/build/spike_a"), Path(__file__).resolve().parents[1] / "build" / "spike_a")
_CODE = re.compile(r"^QTK[DĐ]\s*[\d.]+\s*:\s*\d{4}", re.IGNORECASE)
_END = re.compile(r"^QUY\s+TR[ÌI]NH\s+KI[ỂE]M\s+Đ[ỊI]NH", re.IGNORECASE)
_MAX = 140


def parse_title(head_lines: list[str]) -> str:
    lines = [ln.strip() for ln in head_lines if ln.strip()]
    for i, ln in enumerate(lines):
        if _CODE.match(ln):
            parts: list[str] = []
            for nxt in lines[i + 1 : i + 6]:
                if _END.match(nxt):
                    break
                parts.append(nxt)
            return " ".join(" ".join(parts).split())[:_MAX]
    return ""


@lru_cache(maxsize=256)
def title_for(file_stem: str) -> str:
    for d in _DIRS:
        path = d / f"{file_stem}.md"
        if path.is_file():
            try:
                with path.open(encoding="utf-8") as f:
                    return parse_title([next(f, "") for _ in range(40)])
            except OSError:
                return ""
    return ""
