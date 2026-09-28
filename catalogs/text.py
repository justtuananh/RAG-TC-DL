"""Chuẩn hóa văn bản tiếng Việt cho tìm kiếm không dấu (dùng chung D1).

``fold`` hạ chữ thường và bỏ dấu, giữ nguyên dấu câu (``QTKĐ 1.159:2021`` →
``qtkd 1.159:2021``) để tìm kiếm con khớp tự nhiên. Cột ``search_text`` của bốn
bảng danh mục được sinh bằng chính hàm này lúc ghi, nên truy vấn chỉ cần so khớp
một cột trên cả SQLite lẫn PostgreSQL.
"""

from __future__ import annotations

import unicodedata

# Dải dấu tổ hợp tiếng Việt sau khi tách NFD (U+0300..U+036F).
_DIACRITICS = "".join(chr(code) for code in range(0x0300, 0x0370))


def fold(text: str | None) -> str:
    """Bản không dấu, chữ thường, gộp khoảng trắng (``Áp kế`` → ``ap ke``)."""
    normalized = unicodedata.normalize("NFD", text or "")
    normalized = "".join(ch for ch in normalized if ch not in _DIACRITICS)
    normalized = normalized.replace("đ", "d").replace("Đ", "D").casefold()
    return " ".join(normalized.split())
