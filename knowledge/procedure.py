"""Đọc đầu mục QTKĐ và suy luận loại thiết bị (thuần hàm).

Dùng bởi ``scripts/generate_procedures.py`` để sinh bản ghi ``procedure`` cho các
QTKĐ đang có. Không phụ thuộc DB: nhận text Markdown + danh sách ứng viên.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from knowledge.reference import normalize_alias

# Dòng mã QTKĐ: "QTKĐ 1.061 : 2021" / "QTKĐ 1.062 :2021".
_HEADER_RE = re.compile(
    r"QTKĐ\s*([0-9]+(?:\.[0-9]+)?)\s*[:\-]?\s*(\d{4})",
    re.IGNORECASE,
)
_STOP_RE = re.compile(r"^(QUY TRÌNH KIỂM ĐỊNH|HÀ NỘI|HỒ CHÍ MINH)\b", re.IGNORECASE)
_STEM_RE = re.compile(r"QTKD[_\s]*([0-9.]+)[_\s]+(\d{4})[_\s]+(.+)$", re.IGNORECASE)


@dataclass(frozen=True)
class ProcedureHeader:
    """Đầu mục một QTKĐ rút từ Markdown."""

    number: str
    year: int | None
    title: str
    edition: str | None = None


def parse_procedure_header(text: str) -> ProcedureHeader | None:
    """Rút số, năm và tiêu đề QTKĐ từ Markdown; ``None`` nếu không thấy mã."""
    lines = [line.strip() for line in (text or "").splitlines()]
    number: str | None = None
    year: int | None = None
    index = -1
    for i, line in enumerate(lines):
        match = _HEADER_RE.search(line)
        if match:
            number, year = match.group(1), int(match.group(2))
            index = i
            break
    if number is None:
        return None

    title_lines: list[str] = []
    for line in lines[index + 1 :]:
        if not line:
            continue
        if _STOP_RE.match(line):
            break
        title_lines.append(line)
    title = " ".join(title_lines).strip()
    return ProcedureHeader(number=number, year=year, title=title)


def parse_edition(stem: str) -> str | None:
    """Rút phần phiên bản sau năm từ file_stem, ví dụ ``ND_V2`` hay ``FINAL``."""
    match = _STEM_RE.search(stem or "")
    if not match:
        return None
    edition = match.group(3).strip(" _")
    return edition or None


def infer_device_type(title: str, candidates) -> str | None:
    """Khớp tiêu đề với tên/alias loại thiết bị, chọn khớp dài nhất.

    ``candidates`` là iterable ``(key, aliases)``; trả ``key`` khớp tốt nhất.
    Khớp dài nhất giúp ưu tiên alias đặc thù (``h3000``) hơn tên chung.
    """
    normalized_title = normalize_alias(title)
    best: str | None = None
    best_length = 0
    for key, aliases in candidates:
        for alias in aliases:
            normalized = normalize_alias(alias)
            if normalized and normalized in normalized_title and len(normalized) > best_length:
                best, best_length = key, len(normalized)
    return best
