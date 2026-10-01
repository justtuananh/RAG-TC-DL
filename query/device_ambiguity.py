"""Phát hiện câu hỏi nêu loại thiết bị CHUNG CHUNG, khớp nhiều QTKĐ cùng lúc.

"Áp kế pít tông có phạm vi đo bao nhiêu?" khớp cả "Áp kế píttông kiểu H3000" (QTKĐ
1.071) lẫn "Áp kế píttông tiêu chuẩn" (QTKĐ 1.159). Trả lời bằng số liệu của một
loại như thể đó là câu trả lời chung là SAI: người dùng không biết số liệu thuộc loại
nào. Module này nhận diện tình huống đó để nhánh văn bản nêu rõ từng loại.

Mơ hồ khi câu hỏi chứa phần ĐẦU tên chung của ≥ 2 loại thiết bị (≥ 2 từ và ≥ nửa tên)
mà không nêu loại cụ thể nào: tên đầy đủ, alias trong ``device_type`` (vd. "h3000")
hay số QTKĐ. Danh mục đọc từ bảng ``procedure`` + ``device_type`` nên tự mở rộng khi
thêm quy trình mới, không cần sửa mã.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from query.record_fields import tokens

# Phần đầu tên tối thiểu để coi là cùng một họ thiết bị: "thiết bị" (2/6 từ) trùng
# đầu "Thiết bị đo áp suất số" lẫn "Thiết bị hiệu chuẩn áp suất" nhưng không phải
# một họ; "áp kế píttông" (3/5 từ) thì đúng là một họ.
MIN_HEAD_WORDS = 2
MIN_HEAD_SHARE = 0.5
# Quá nhiều lựa chọn thì phễu truy hồi riêng cho từng QTKĐ thành quá tốn; khi đó vẫn
# liệt kê các loại nhưng truy hồi trên toàn kho như bình thường.
MAX_SCOPED_OPTIONS = 6

_NUMBER_RE = re.compile(r"\d+\.\d+")


@dataclass(frozen=True)
class DeviceProcedure:
    """Một QTKĐ và loại thiết bị nó áp dụng (kèm alias để nhận diện câu hỏi cụ thể)."""

    device_type: str
    number: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeviceAmbiguity:
    """Cụm chung người dùng nêu (vd. "áp kế píttông") và mọi QTKĐ nó có thể chỉ tới."""

    phrase: str
    options: tuple[DeviceProcedure, ...]


def load_device_procedures(session) -> list[DeviceProcedure]:
    """Đọc danh mục QTKĐ ↔ loại thiết bị từ DB, sắp theo số QTKĐ."""
    from db.models import Procedure

    result: list[DeviceProcedure] = []
    for procedure in session.query(Procedure).order_by(Procedure.number).all():
        device_type = procedure.device_type
        if device_type is None or not procedure.number:
            continue
        result.append(
            DeviceProcedure(
                device_type=device_type.name_vi,
                number=procedure.number,
                aliases=tuple(device_type.alias_list()),
            )
        )
    return result


def _contains(haystack: Sequence[str], needle: Sequence[str]) -> bool:
    size = len(needle)
    if size == 0 or size > len(haystack):
        return False
    return any(
        list(haystack[i : i + size]) == list(needle) for i in range(len(haystack) - size + 1)
    )


def _head_length(question: Sequence[str], name: Sequence[str]) -> int:
    """Số từ đầu tên dài nhất xuất hiện liền mạch trong câu hỏi."""
    for size in range(len(name), 0, -1):
        if _contains(question, name[:size]):
            return size
    return 0


def _display_head(name: str, size: int) -> str:
    """Cắt ``size`` từ (đã chuẩn hóa) đầu tên gốc, giữ chính tả gốc: "áp kế píttông"."""
    words = name.split()
    for count in range(1, len(words) + 1):
        if len(tokens(" ".join(words[:count]))) >= size:
            head = " ".join(words[:count])
            return head[:1].lower() + head[1:]
    return name


def _names_specific(question: Sequence[str], raw_question: str, item: DeviceProcedure) -> bool:
    if item.number in _NUMBER_RE.findall(raw_question):
        return True
    return any(_contains(question, tokens(phrase)) for phrase in (item.device_type, *item.aliases))


def find_device_ambiguity(
    question: str, catalog: Sequence[DeviceProcedure]
) -> DeviceAmbiguity | None:
    """Trả ``DeviceAmbiguity`` nếu câu hỏi chỉ nêu tên chung của ≥ 2 loại thiết bị."""
    words = tokens(question)
    if not words or any(_names_specific(words, question, item) for item in catalog):
        return None

    best = 0
    matches: list[DeviceProcedure] = []
    for item in catalog:
        name = tokens(item.device_type)
        size = _head_length(words, name)
        if size < MIN_HEAD_WORDS or size < len(name) * MIN_HEAD_SHARE:
            continue
        if size > best:
            best, matches = size, [item]
        elif size == best:
            matches.append(item)

    if len({" ".join(tokens(item.device_type)) for item in matches}) < 2:
        return None
    options = tuple(sorted(matches, key=lambda item: item.number))
    return DeviceAmbiguity(phrase=_display_head(options[0].device_type, best), options=options)


def _option_label(option: DeviceProcedure) -> str:
    return f"{option.device_type} (QTKĐ {option.number})"


def _join_vi(items: Sequence[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} và {items[-1]}"


def ambiguity_preface(ambiguity: DeviceAmbiguity) -> str:
    """Câu mở đầu tất định: nói rõ câu hỏi chưa nêu loại và kể tên mọi loại khớp.

    Viết tất định (không nhờ LLM) để người dùng luôn biết có nhiều loại, kể cả khi
    model bỏ sót một loại trong phần trả lời.
    """
    labels = _join_vi([_option_label(option) for option in ambiguity.options])
    return (
        f"Câu hỏi chưa nêu rõ loại **{ambiguity.phrase}** nào. Tài liệu QTKĐ hiện có "
        f"{len(ambiguity.options)} loại: {labels}. Thông tin của từng loại:\n\n"
    )


def ambiguity_closing(ambiguity: DeviceAmbiguity) -> str:
    return (
        f"\n\nHãy nêu rõ loại {ambiguity.phrase} hoặc số QTKĐ để nhận câu trả lời "
        "cho đúng loại cần tra cứu."
    )


def ambiguity_guidance(ambiguity: DeviceAmbiguity) -> str:
    """Chỉ dẫn cho LLM: trả lời riêng từng loại theo mẫu, không chọn một loại làm câu chung.

    Đưa MẪU từng dòng thay vì quy tắc dài: qwen2.5:3b chép nguyên câu "không tìm thấy"
    trong quy tắc vào mọi dòng khi chỉ dẫn được viết dạng văn xuôi (đo 2026-10-01).
    """
    template = "\n".join(
        f"- **{_option_label(option)}**: <thông tin lấy từ nguồn {option.number}> [n]"
        for option in ambiguity.options
    )
    return (
        f"LƯU Ý: Câu hỏi không nêu rõ loại {ambiguity.phrase} nào, nên KHÔNG chọn một loại "
        "để trả lời chung. Trả lời riêng cho từng loại theo đúng mẫu sau, mỗi dòng chỉ dùng "
        "nguồn có số QTKĐ đó trong tên nguồn, trích nguyên văn số liệu:\n"
        f"{template}"
    )


def scoped_retrieval_query(question: str, ambiguity: DeviceAmbiguity) -> str:
    """Câu truy hồi nêu số QTKĐ của mọi lựa chọn để retriever chạy phễu riêng từng file.

    ``retrieval.router.route_files`` nhận ≥ 2 số QTKĐ → mỗi file một phễu, nên loại
    thiểu số không bị loại kia đè mất khỏi ngữ cảnh.
    """
    if len(ambiguity.options) > MAX_SCOPED_OPTIONS:
        return question
    numbers = ", ".join(f"QTKĐ {option.number}" for option in ambiguity.options)
    return f"{question} ({numbers})"
