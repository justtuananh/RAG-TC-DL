"""Phạm vi tài liệu theo loại câu hỏi: chỉ tìm trong nhóm tài liệu thuộc câu hỏi, không tìm cả kho.

Mỗi loại (``doc_scopes.scopes`` trong settings) gồm mẫu nhận câu hỏi và bộ chọn tài liệu theo tên
tệp, tên tài liệu hoặc tên mục trong hồ sơ (``retrieval.doc_profile``). Bộ chọn đọc từ chính tài liệu
nên tài liệu mới nạp tự vào đúng nhóm, không cần liệt kê tên tệp.

- Loại ``priority`` (vd. "thiết bị chuẩn mẫu" → A_*) thắng tên thiết bị router nhận ra ngoài nhóm:
  ``restrict_named`` giữ phần giao, rỗng thì để ``match`` chọn trong nhóm.
- Loại thường chỉ dùng khi câu hỏi không nêu đích danh tài liệu nào; nhiều loại khớp thì hợp nhóm.
- Câu nêu số QTKĐ hoặc mã TCVN/ISO: router quyết định, không áp phạm vi.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache

from core.schema import DocScope
from core.settings_loader import get_settings
from retrieval import doc_profile
from retrieval.normalize import fold


@dataclass(frozen=True)
class ScopeMatch:
    names: tuple[str, ...]
    stems: frozenset[str]
    priority: bool


def _matched(question: str) -> list[DocScope]:
    cfg = get_settings().doc_scopes
    if not cfg.enabled:
        return []
    folded = fold(question)
    return [scope for scope in cfg.scopes if re.search(scope.question_pattern, folded)]


def _belongs(stem: str, stem_pattern: str, title_pattern: str, section_pattern: str) -> bool:
    if stem_pattern and re.search(stem_pattern, stem):
        return True
    if not (title_pattern or section_pattern):
        return False
    profile = doc_profile.profile_for(stem)
    if profile is None:
        return False
    if title_pattern and re.search(title_pattern, fold(profile.title)):
        return True
    return bool(section_pattern) and any(
        re.search(section_pattern, fold(section.title)) for section in profile.sections
    )


@lru_cache(maxsize=64)
def _members(selector: tuple[str, str, str], known: frozenset[str]) -> frozenset[str]:
    return frozenset(stem for stem in known if _belongs(stem, *selector))


def _stems(scopes: Iterable[DocScope], known: frozenset[str]) -> frozenset[str]:
    out: frozenset[str] = frozenset()
    for scope in scopes:
        out |= _members((scope.stem_pattern, scope.title_pattern, scope.section_pattern), known)
    return out


def match(question: str, known: frozenset[str]) -> ScopeMatch | None:
    """Nhóm tài liệu của loại câu hỏi; ``None`` khi không loại nào khớp hoặc nhóm rỗng.

    Có loại ``priority`` khớp thì chỉ các loại đó quyết định ("thiết bị chuẩn mẫu áp kế" không bị
    loại "áp suất" kéo thêm QTKĐ áp kế vào).
    """
    scopes = _matched(question)
    priority = [scope for scope in scopes if scope.priority]
    chosen = priority or scopes
    stems = _stems(chosen, known)
    if not stems:
        return None
    return ScopeMatch(tuple(scope.name for scope in chosen), stems, bool(priority))


def restrict_named(question: str, named: frozenset[str], known: frozenset[str]) -> frozenset[str]:
    """Tài liệu router nhận ra qua tên thiết bị, thu về nhóm của loại ``priority`` nếu có.

    "Thiết bị chuẩn mẫu MP-600" giữ A_06; "thiết bị chuẩn mẫu áp kế píttông" bỏ QTKĐ 1.159/1.071
    (tên chung) để retriever tìm trong mọi tài liệu A_*.
    """
    scope = match(question, known)
    if scope is None or not scope.priority:
        return named
    return named & scope.stems


def asks_priority(question: str) -> bool:
    """Câu hỏi khớp một loại ``priority`` (chỉ so mẫu câu hỏi, không đọc tài liệu)."""
    return any(scope.priority for scope in _matched(question))


def invalidate() -> None:
    _members.cache_clear()
