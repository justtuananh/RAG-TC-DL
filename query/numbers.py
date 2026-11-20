"""Đọc số trong câu hỏi tiếng Việt, tất định.

Số viết theo ba kiểu mà người dùng và chính tài liệu QTKĐ đều dùng:
- dấu phẩy thập phân: ``2,5``;
- dấu cách (kể cả NBSP do Word sinh ra) ngăn nghìn: ``1 400``;
- dấu chấm ngăn nghìn kiểu Việt Nam: ``1.400`` hoặc ``1.400.000``.

Nhóm nghìn luôn có đúng 3 chữ số và không bắt đầu bằng 0, nên ``0.125`` và ``2.5`` vẫn là số thập phân.
Đọc sai ở đây làm mất chữ số ("1 400 bar" thành "400 bar"), nên mọi bộ tính tất định dùng chung một mẫu.
"""

from __future__ import annotations

import re

_SPACES = "   "
_GROUPED = rf"[1-9]\d{{0,2}}(?:(?:[{_SPACES}]\d{{3}})+|(?:\.\d{{3}})+)(?:,\d+)?"
_PLAIN = r"\d+(?:[.,]\d+)?"
# Chỉ nhóm không bắt (?:...) để chỗ dùng tự bọc nhóm bắt của mình.
NUMBER = rf"(?<![\d.,])(?:{_GROUPED}|{_PLAIN})(?!\d)"

_DOT_GROUPS = re.compile(r"[1-9]\d{0,2}(?:\.\d{3})+")


def normalize(raw: str) -> str:
    """Đưa số đã khớp ``NUMBER`` (có thể kèm dấu +/-) về dạng chuỗi thập phân: ``"1.400,5"`` -> ``"1400.5"``."""
    sign = raw[0] if raw[:1] in "+-" else ""
    body = re.sub(f"[{_SPACES}]", "", raw[len(sign) :])
    if "," in body:
        whole, frac = body.split(",", 1)
        return f"{sign}{whole.replace('.', '')}.{frac}"
    if _DOT_GROUPS.fullmatch(body):
        return sign + body.replace(".", "")
    return sign + body
