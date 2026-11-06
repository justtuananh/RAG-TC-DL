"""Trả lời TỪNG tài liệu riêng cho câu hỏi không chỉ định một QTKĐ.

Hai tình huống cùng gốc: (1) câu hỏi chung ("Nhiệt kế dùng trong kiểm định phải có phạm vi đo
thế nào?") mà mỗi QTKĐ nêu một giá trị riêng; (2) câu hỏi nêu ≥ 2 QTKĐ/thiết bị. Một lượt sinh
duy nhất trên ngữ cảnh trộn nhiều tài liệu làm model 7B gán giá trị của tài liệu này cho tài
liệu khác, lặp một giá trị cho mọi tài liệu hoặc ghi "không nêu" dù nguồn có. Ở đây mỗi tài liệu
được hỏi RIÊNG với ngữ cảnh chỉ gồm nguồn của nó; module này chứa phần logic thuần (chọn tài
liệu, lọc câu trả lời rỗng, gộp dòng) để chạy được không cần mạng/GPU.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

_REF_RE = re.compile(r"\[(\d+)\]")
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
_EMPTY_RE = re.compile(
    r"^\W*(không nêu|không tìm thấy|không có thông tin|không được nêu|không đề cập)", re.IGNORECASE
)
_EMPTY_MAX_CHARS = 160
NO_INFO = "không nêu"


@dataclass(frozen=True)
class DocumentGroup:
    """Một tài liệu trong kết quả truy hồi: file_stem và vị trí (0-based) các nguồn của nó."""

    stem: str
    positions: tuple[int, ...]


def group_by_document(stems_in_order: Sequence[str]) -> list[DocumentGroup]:
    """Gom các nguồn theo tài liệu, giữ thứ tự xuất hiện (tài liệu xếp hạng cao đứng trước)."""
    positions: dict[str, list[int]] = {}
    for index, stem in enumerate(stems_in_order):
        positions.setdefault(stem, []).append(index)
    return [DocumentGroup(stem, tuple(idx)) for stem, idx in positions.items()]


def select_documents(
    groups: Sequence[DocumentGroup],
    named: frozenset[str],
    *,
    min_documents: int = 2,
    max_documents: int = 6,
) -> list[DocumentGroup] | None:
    """Các tài liệu cần hỏi riêng, hoặc None khi nên trả lời một lượt như thường.

    ``named`` là tập tài liệu câu hỏi nhắc tới: đúng 1 → câu hỏi đơn tài liệu (None); ≥ 2 → chỉ
    các tài liệu đó; rỗng → mọi tài liệu có nguồn (câu chung chung).
    """
    if len(named) == 1:
        return None
    chosen = [g for g in groups if not named or g.stem in named]
    chosen = chosen[: max(max_documents, 1)]
    return chosen if len(chosen) >= max(min_documents, 2) else None


def document_note(label: str) -> str:
    """Chỉ dẫn đặt sau câu hỏi khi chỉ xét một tài liệu."""
    return (
        f"LƯU Ý: Câu hỏi áp dụng cho nhiều tài liệu; lượt này CHỈ xét tài liệu {label} "
        "(các nguồn ở trên là toàn bộ nguồn của tài liệu đó). Trả lời riêng cho tài liệu này "
        "trong một đến hai câu, trích nguyên văn số liệu kèm [n] của nguồn. Không nhắc tài "
        f"liệu khác. Chỉ khi các nguồn thật sự không có nội dung được hỏi thì trả lời đúng hai "
        f"chữ: {NO_INFO}."
    )


def is_empty_answer(text: str) -> bool:
    """Câu trả lời ngắn kiểu "không nêu"/"không tìm thấy" (không mang giá trị nào)."""
    stripped = text.strip()
    return not stripped or (len(stripped) <= _EMPTY_MAX_CHARS and bool(_EMPTY_RE.match(stripped)))


def _signature(text: str) -> tuple[str, ...]:
    return tuple(sorted(_NUM_RE.findall(_REF_RE.sub("", text))))


def merge_identical(entries: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    """Gộp các tài liệu có cùng bộ số liệu (câu trả lời giống hệt về giá trị) thành một dòng.

    Câu hỏi chung mà mọi tài liệu cùng một giá trị thì liệt kê từng tài liệu là dài dòng và dễ
    bị coi là mâu thuẫn; dòng gộp giữ tên mọi tài liệu và [n] của chúng.
    """
    merged: list[tuple[list[str], str, tuple[str, ...]]] = []
    for label, text in entries:
        sig = _signature(text)
        for item in merged:
            if sig and item[2] == sig:
                item[0].append(label)
                known = set(_REF_RE.findall(item[1]))
                extra = [n for n in _REF_RE.findall(text) if n not in known]
                if extra:
                    item_text = item[1].rstrip() + " " + "".join(f"[{n}]" for n in dict.fromkeys(extra))
                    merged[merged.index(item)] = (item[0], item_text, sig)
                break
        else:
            merged.append(([label], text, sig))
    return [("; ".join(labels), text) for labels, text, _ in merged]


def render(entries: Sequence[tuple[str, str]]) -> str:
    """Mỗi tài liệu một dòng: ``- **tên**: câu trả lời``."""
    return "\n".join(f"- **{label}**: {' '.join(text.split())}" for label, text in entries)
