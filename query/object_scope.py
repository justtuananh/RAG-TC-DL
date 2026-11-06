"""Đối tượng kiểm định có thuộc các QTKĐ trong kho không?

Câu hỏi về quy trình/điều kiện/chu kỳ kiểm định của một phương tiện đo KHÔNG phải đối tượng của bất
kỳ QTKĐ nào thì model 7B hay trả lời bằng nội dung của QTKĐ khác. Tập đối tượng lấy từ TIÊU ĐỀ các
tài liệu và alias thiết bị của router, cộng mục "Phạm vi áp dụng" của các nguồn truy hồi. Phương tiện
chỉ được NHẮC trong tài liệu như thiết bị kiểm định (nhiệt kế, đồng hồ bấm giây...) không thuộc tập này.
Phần logic thuần: không mạng/GPU.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.schema import ObjectScopeSettings

_WORD = re.compile(r"\w+")
_AFTER = re.compile(r"ki[ểe]m đ[ịi]nh\s+(.*)", re.IGNORECASE)


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _words(text: str) -> list[str]:
    return _WORD.findall(unicodedata.normalize("NFC", text).casefold())


def object_phrase(question: str, cfg: ObjectScopeSettings) -> list[str]:
    """Các từ đặc trưng của đối tượng đứng ngay sau "kiểm định" ([] = không phải câu loại này)."""
    if not re.search(cfg.trigger_pattern, question, re.IGNORECASE):
        return []
    m = _AFTER.search(unicodedata.normalize("NFC", question))
    if not m:
        return []
    stop = set(cfg.stop_words)
    phrase: list[str] = []
    for w in re.findall(r"[^\W_]+|[?.,;:!()]", m.group(1).casefold()):
        if w in stop or not re.match(r"\w", w):
            break
        phrase.append(w)
    skip = set(cfg.generic_words) | set(cfg.ignore_words)
    return [w for w in phrase if w not in skip and not w.isdigit()]


def _matches(core: list[str], text: str) -> bool:
    folded = [_fold(w) for w in core]
    tokens = set(_words(_fold(text)))
    if set(folded) <= tokens:
        return True
    return "".join(folded) in "".join(_words(_fold(text)))


def is_out_of_scope(
    question: str, objects: Iterable[str], scope_texts: Iterable[str], cfg: ObjectScopeSettings
) -> bool:
    """True khi đối tượng được hỏi không khớp tiêu đề/alias/phạm vi áp dụng nào."""
    if not cfg.enabled:
        return False
    core = object_phrase(question, cfg)
    if not core:
        return False
    return not any(_matches(core, t) for t in [*objects, *scope_texts] if t)
