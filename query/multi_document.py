"""Chỉ dẫn trả lời theo TỪNG tài liệu cho câu hỏi không chỉ định một QTKĐ.

Hai tình huống cùng gốc: (1) câu hỏi chung ("Nhiệt kế dùng trong kiểm định phải có phạm vi
đo thế nào?") mà mỗi QTKĐ nêu một giá trị riêng; (2) câu hỏi nêu ≥ 2 QTKĐ/thiết bị. Model 7B
hay chọn một giá trị làm câu trả lời chung hoặc từ chối cả câu. Chỉ dẫn đặt SAU câu hỏi, dạng
MẪU từng dòng (model chép mẫu chắc hơn quy tắc văn xuôi), mỗi tài liệu một dòng.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentRef:
    """Một tài liệu trong ngữ cảnh: nhãn hiển thị và số thứ tự các nguồn [n] của nó."""

    label: str
    refs: tuple[int, ...]


def group_documents(
    stems_in_order: Sequence[str], titles: dict[str, str] | None = None
) -> list[DocumentRef]:
    """Gom các nguồn (theo thứ tự [1], [2], …) thành danh sách tài liệu, giữ thứ tự xuất hiện."""
    titles = titles or {}
    refs: dict[str, list[int]] = {}
    for index, stem in enumerate(stems_in_order, 1):
        refs.setdefault(stem, []).append(index)
    return [
        DocumentRef(label=f"{stem} ({titles[stem]})" if titles.get(stem) else stem, refs=tuple(idx))
        for stem, idx in refs.items()
    ]


def per_document_guidance(
    documents: Sequence[DocumentRef], *, min_documents: int = 2
) -> str | None:
    """Chỉ dẫn mẫu từng dòng; None khi có ít hơn ``min_documents`` tài liệu."""
    if len(documents) < max(min_documents, 2):
        return None
    template = "\n".join(
        f"- **{doc.label}**: <giá trị nguyên văn trong nguồn {''.join(f'[{n}]' for n in doc.refs)}> [n]"
        for doc in documents
    )
    return (
        "LƯU Ý: Câu hỏi không chỉ định một tài liệu duy nhất và mỗi tài liệu có thể nêu giá "
        "trị khác nhau, nên KHÔNG chọn một giá trị làm câu trả lời chung và KHÔNG từ chối "
        "cả câu. Trả lời lần lượt từng tài liệu theo đúng mẫu sau, mỗi dòng trích nguyên "
        "văn số liệu và [n] của nguồn đó; chỉ ghi \"không nêu\" ở dòng nào mà nguồn của tài "
        "liệu đó thực sự không có nội dung được hỏi:\n"
        f"{template}"
    )
