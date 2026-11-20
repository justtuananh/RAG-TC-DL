"""Tên tài liệu (đối tượng của QTKĐ) rút từ khối tiêu đề đầu file markdown nguồn.

Định dạng chung của mọi QTKĐ: dòng ``QTKĐ <mã> : <năm>``, tiếp đó là tên đối tượng
(một hoặc nhiều dòng), kết thúc ở dòng ``QUY TRÌNH KIỂM ĐỊNH``. Không có bảng tra cứng:
tài liệu nạp thêm cùng định dạng tự có tên. Không tìm được thì trả chuỗi rỗng.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from core.settings_loader import get_settings

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
    path = Path(get_settings().paths.markdown_dir) / f"{file_stem}.md"
    try:
        with path.open(encoding="utf-8") as f:
            title = parse_title([next(f, "") for _ in range(40)])
    except OSError:
        return ""
    if title:
        return title
    # Dạng khác QTKĐ mới (tài liệu thiết bị chuẩn mẫu "THIẾT BỊ: ...", QTKĐ cũ, TCVN): tên trong hồ sơ.
    from retrieval import doc_profile

    profile = doc_profile.profile_for(file_stem)
    return profile.title[:_MAX] if profile is not None else ""


def code_for(file_stem: str) -> str:
    """Mã tài liệu ("QTKĐ 1.071:2022", "TCVN 6165:1996") để LLM gọi đúng tên thay cho tên tệp; rỗng nếu không rõ."""
    from retrieval import doc_profile

    profile = doc_profile.profile_for(file_stem)
    return profile.code.label if profile is not None and profile.code is not None else ""


def display_label(file_stem: str) -> str:
    """"QTKĐ 1.071:2022 - ÁP KẾ ..." khi biết mã; nếu không "<file_stem> (<tên>)" hoặc chỉ file_stem."""
    code = code_for(file_stem)
    title = title_for(file_stem)
    if code:
        return f"{code} - {title}" if title else code
    return f"{file_stem} ({title})" if title else file_stem
