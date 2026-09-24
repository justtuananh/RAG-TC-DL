"""Bộ luật trích xuất tri thức QTKĐ (spec §7).

Mỗi mô đun phụ trách một mục; tất cả thuần hàm, không chạm DB, trả ``RuleHit``
kèm xuất xứ nguyên văn (P1). ``extract_all`` chạy toàn bộ và trả danh sách ứng
viên để tầng ghi (``knowledge.extract``) dựng bản ghi ``pending``.
"""

from __future__ import annotations

from knowledge.rules import bang1, bang2, chuky, dieukien, phamvi, phuluc_a, thuatngu
from knowledge.rules.types import RuleHit

# Thứ tự chạy không ảnh hưởng kết quả vì mỗi luật tra mục riêng.
_RULES = (phamvi, thuatngu, bang1, bang2, dieukien, chuky)

__all__ = ["RuleHit", "extract_all", "extract_appendix", "rule_modules"]


def rule_modules():
    """Danh sách mô đun luật, phục vụ kiểm tra/ghi log."""
    return _RULES


def extract_all(text: str) -> list[RuleHit]:
    """Chạy mọi luật trên văn bản Markdown QTKĐ; rỗng khi không có gì khớp."""
    hits: list[RuleHit] = []
    for module in _RULES:
        hits.extend(module.extract(text))
    return hits


def extract_appendix(text: str) -> list[RuleHit]:
    """Rút trường Phụ lục A (bước riêng, không nằm trong ``extract_all``)."""
    return phuluc_a.extract(text)
