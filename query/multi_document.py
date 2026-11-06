"""Trả lời TỪNG tài liệu riêng cho câu hỏi không chỉ định một QTKĐ.

Hai tình huống cùng gốc: (1) câu hỏi chung ("<Phương tiện đo> dùng trong kiểm định phải có đặc
trưng nào?") mà mỗi QTKĐ nêu một giá trị riêng; (2) câu hỏi nêu ≥ 2 QTKĐ/thiết bị. Một lượt sinh
duy nhất trên ngữ cảnh trộn nhiều tài liệu làm model 7B gán giá trị của tài liệu này cho tài
liệu khác, lặp một giá trị cho mọi tài liệu hoặc ghi "không nêu" dù nguồn có. Ở đây mỗi tài liệu
được hỏi RIÊNG với ngữ cảnh chỉ gồm nguồn của nó; module này chứa phần logic thuần (chọn tài
liệu, lọc câu trả lời rỗng, gộp dòng) để chạy được không cần mạng/GPU.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

_REF_RE = re.compile(r"\[(\d+)\]")
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
_EMPTY_RE = re.compile(
    r"^\W*(không nêu|không tìm thấy|không có thông tin|không được nêu|không đề cập)", re.IGNORECASE
)
_EMPTY_MAX_CHARS = 160
NO_INFO = "không nêu"
_NEGATION_RE = re.compile(r"không\s+(?:nêu|có|đề cập|tìm thấy|quy định|được nêu)", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.;!?])\s+|\n+")
_UNIT = (
    r"(?:tháng|năm|ngày|giờ|phút|giây|lần|điểm|%|°\s?[CF]|[oº]C|℃|mm|cm|km|m|kPa|MPa|Pa|mbar|bar"
    r"|kg|mg|g|mA|kV|V|A|kHz|Hz|N|s)"
)
_VALUE_RE = re.compile(rf"[±≤≥<>]?\s*\d+(?:[.,]\d+)?(?:\s*{_UNIT}(?!\w))?")

# Mã văn bản ngoài kho: quy chuẩn/tiêu chuẩn có mã (QCVN 01:2008, ISO 5167...) và văn bản pháp luật có số.
_DOC_CODE_RE = re.compile(
    r"\b(?:QCVN|TCVN|ISO|IEC|OIML|ASTM|DIN)\s*[-:]?\s*\d[\w.\-:/]*"
    r"|\b(?:nghị định|thông tư|quyết định)\s+(?:số\s+)?\d+(?:/[\w\-]+)*",
    re.IGNORECASE,
)


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


def names_device(
    question: str, aliases: Mapping[str, Sequence[str]], generic_words: Collection[str] = ()
) -> bool:
    """Câu hỏi nêu một loại thiết bị (từ đầu của alias thiết bị) dù không đủ tên đầy đủ để định tuyến.

    ``aliases``: alias thiết bị → các số QTKĐ (từ điển thiết bị của tài liệu). Từ đầu của alias là
    "từ nhận diện" khi nó chỉ xuất hiện ở alias của đúng một QTKĐ (ở bất kỳ vị trí nào) và không
    nằm trong ``generic_words``; câu hỏi chứa từ đó là câu về MỘT loại thiết bị, đi nhánh một lượt
    (không tách theo từng tài liệu)."""
    owners: dict[str, set[str]] = {}
    heads: set[str] = set()
    for alias, numbers in aliases.items():
        words = _plain_tokens(alias)
        for word in words:
            owners.setdefault(word, set()).update(numbers)
        if words:
            heads.add(words[0])
    generic = {w.casefold() for w in generic_words}
    keys = {h for h in heads if len(owners.get(h, ())) == 1 and h not in generic}
    return bool(keys.intersection(_plain_tokens(question)))


def _plain_tokens(text: str) -> list[str]:
    return re.findall(r"\w+", unicodedata.normalize("NFC", text).casefold())


def followup_groups(
    missing: Sequence[DocumentGroup],
    scores: Sequence[float],
    *,
    limit: int,
    min_score: float = 0.0,
) -> list[DocumentGroup]:
    """Các tài liệu đáng hỏi bổ sung: điểm rerank cao nhất trong nguồn của tài liệu ≥ ``min_score``
    (``scores[i]`` là điểm nguồn vị trí i), lấy tối đa ``limit`` theo thứ tự đã xếp hạng."""
    ok = [g for g in missing if max((scores[i] for i in g.positions), default=0.0) >= min_score]
    return ok[: max(limit, 0)]


def within_budget(elapsed_s: float, budget_s: float) -> bool:
    """Còn ngân sách thời gian cho thêm một lượt hỏi riêng?"""
    return elapsed_s < budget_s


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


def _normalize(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.casefold())


def names_unknown_document(question: str, source_texts: Sequence[str]) -> bool:
    """Câu hỏi nêu mã văn bản (QCVN, TCVN, ISO, nghị định, thông tư...) mà không nguồn nào nhắc tới.

    Văn bản ấy không có trong kho: không tách theo tài liệu (mỗi lượt riêng dễ bịa giá trị cho
    văn bản không tồn tại) mà để một lượt như thường, nơi cơ chế từ chối sẵn có hoạt động."""
    codes = [_normalize(m.group(0)) for m in _DOC_CODE_RE.finditer(question)]
    if not codes:
        return False
    corpus = _normalize("\n".join(source_texts))
    return any(code not in corpus for code in codes)


def uncovered_groups(answer: str, groups: Sequence[DocumentGroup]) -> list[DocumentGroup]:
    """Các tài liệu mà câu trả lời chung chưa có câu khẳng định nào trích [n] tới nguồn của nó.

    Câu phủ định ("không nêu"...) không tính là khẳng định. ``positions`` là chỉ số 0-based nên
    nguồn [n] ứng với vị trí n-1."""
    cited: set[int] = set()
    for sentence in _SENTENCE_SPLIT_RE.split(answer):
        if _NEGATION_RE.search(sentence):
            continue
        cited.update(int(n) - 1 for n in _REF_RE.findall(sentence))
    return [g for g in groups if not cited.intersection(g.positions)]


def _value_span(text: str, max_chars: int) -> str | None:
    """Đoạn ngắn nhất của câu trả lời bao mọi số liệu (kèm đơn vị), bỏ [n]; None nếu không có/quá dài."""
    clean = _REF_RE.sub("", text)
    found = list(_VALUE_RE.finditer(clean))
    if not found:
        return None
    span = " ".join(clean[found[0].start() : found[-1].end()].split()).strip(" ,;.:")
    return span if span and len(span) <= max_chars else None


def merge_identical(entries: Sequence[tuple[str, str]], max_value_chars: int = 80) -> list[tuple[str, str]]:
    """Gộp các tài liệu cùng bộ số liệu thành một dòng trung tính: ``tên1, tên2: giá trị [1][2]``.

    Dòng gộp được DỰNG từ giá trị đã trích (đoạn quanh các số, không lấy nguyên câu của một tài
    liệu vì câu đó nêu tên thiết bị của riêng nó) và dồn mọi [n] liền sau giá trị. Không rút
    được giá trị gọn thì không gộp."""
    groups: list[list[tuple[str, str]]] = []
    sigs: list[tuple[str, ...]] = []
    for label, text in entries:
        sig = _signature(text)
        if sig and sig in sigs:
            groups[sigs.index(sig)].append((label, text))
        else:
            groups.append([(label, text)])
            sigs.append(sig)
    out: list[tuple[str, str]] = []
    for members in groups:
        span = _value_span(members[0][1], max_value_chars) if len(members) > 1 else None
        if span is None:
            out.extend(members)
            continue
        refs = dict.fromkeys(n for _, t in members for n in _REF_RE.findall(t))
        out.append((", ".join(label for label, _ in members), f"{span} {''.join(f'[{n}]' for n in refs)}".strip()))
    return out


def render(entries: Sequence[tuple[str, str]]) -> str:
    """Mỗi tài liệu một dòng: ``- **tên**: câu trả lời``."""
    return "\n".join(f"- **{label}**: {' '.join(text.split())}" for label, text in entries)
