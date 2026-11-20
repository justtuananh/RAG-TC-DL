"""Câu "… có đạt không?" mà giới hạn phải tra bảng theo thông số câu hỏi chưa nêu: hỏi lại, không kết luận.

"Nhiệt kế thủy tinh chất lỏng có sai số 0,5 °C thì có đạt không?": sai số cho phép của QTKĐ 1.106 nằm ở
Bảng C.1 - C.3.3, tra theo kiểu nhúng, phạm vi đo, loại nhiệt kế, giá trị độ chia nhỏ nhất, cấp chính xác.
LLM chọn đại một ô rồi kết luận "đạt". Ở đây các thông số được lấy từ chính bảng của tài liệu:

- tiêu đề cột không phải cột giới hạn ("Phạm vi đo", "Loại nhiệt kế", "Giá trị độ chia nhỏ nhất");
- phần "(Theo ... và ...)" trong tiêu đề cột giới hạn ("giá trị độ chia nhỏ nhất", "cấp chính xác");
- phần khác nhau giữa tên các bảng ("nhúng toàn phần" / "nhúng một phần" / "theo ΓOCT 28498 - 90").

Câu hỏi đã nêu đủ mọi thông số (hoặc tài liệu không có bảng giới hạn) → ``None``, chat đi tiếp như cũ.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from core.settings_loader import get_settings
from retrieval import doc_profile, router
from retrieval.doc_tables import CaptionedTable, captioned_tables
from retrieval.normalize import fold

_THEO_RE = re.compile(r"\(\s*theo\s+(.+?)\s*\)", re.IGNORECASE)
_THEO_TAIL_RE = re.compile(r"\s+của\s+.*$", re.IGNORECASE)
_SPLIT_RE = re.compile(r"\s+và\s+|\s*,\s*", re.IGNORECASE)
_SKIP_COLUMNS = {"tt", "stt"}
_RANGE_RE = re.compile(r"\b(?:tu\s*-?\s*\d|\d+(?:[.,]\d+)?\s*(?:den|-)\s*-?\s*\d)")
_GRADE_RE = re.compile(r"\bcap\s*(?:chinh xac\s*)?[a-z0-9]\b")
_MAX_OPTIONS = 6
_MAX_OPTION_CHARS = 40
_NUMBER_WORDS = {"tu", "den", "hoac", "va", "duoi", "tren", "khong", "qua", "lon", "nho", "hon"}
_VARIANT_HEAD_WORDS = 2
_NUMBER_RE = re.compile(r"-?\s*\d+(?:[.,]\d+)?")
_QUESTION_RANGE_RE = re.compile(r"\btu\s*(-?\s*\d+(?:[.,]\d+)?)\s*(?:den|-)\s*(-?\s*\d+(?:[.,]\d+)?)")
_MEASURED_RE = re.compile(r"\bsai so(?! cho phep)[^\d-]{0,15}(-?\d+(?:[.,]\d+)?)")
_CLARIFY_MARK = "Chưa đủ thông tin để kết luận đạt hay không đạt"


@dataclass(frozen=True)
class Parameter:
    name: str
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClarifyAnswer:
    text: str
    hits: list[dict]


def _is_limit(text: str) -> bool:
    return bool(re.search(get_settings().limit_clarify.limit_pattern, fold(text)))


def _name(cell: str) -> str:
    return cell.split(",")[0].strip()


def _is_word_value(value: str) -> bool:
    """Ô là chữ ("Thủy ngân"), không phải số / khoảng số ("0,5 hoặc 1,0", "từ - 80 đến 0")."""
    words = [w for w in re.findall(r"[^\W\d_]+", fold(value)) if w not in _NUMBER_WORDS]
    return bool(words) and len(value) <= _MAX_OPTION_CHARS


def _options(table: CaptionedTable, index: int) -> tuple[str, ...]:
    values: list[str] = []
    for value in table.column(index):
        if not _is_word_value(value):
            continue
        if value not in values:
            values.append(value)
    return tuple(values) if len(values) <= _MAX_OPTIONS else ()


def _table_parameters(table: CaptionedTable) -> list[Parameter]:
    params: list[Parameter] = []
    for index, cell in enumerate(table.header):
        if not cell or fold(cell) in _SKIP_COLUMNS:
            continue
        if _is_limit(cell):
            theo = _THEO_RE.search(cell)
            if theo:
                for part in _SPLIT_RE.split(_THEO_TAIL_RE.sub("", theo.group(1))):
                    if part.strip():
                        params.append(Parameter(part.strip()))
            continue
        params.append(Parameter(_name(cell), _options(table, index)))
    return params


def _remainders(tables: list[CaptionedTable]) -> list[str]:
    """Phần riêng của tên từng bảng sau phần đầu chung: "nhúng toàn phần", "nhúng một phần"…; rỗng nếu 1 bảng."""
    if len(tables) < 2:
        return [""] * len(tables)
    words = [t.caption.split() for t in tables]
    common = 0
    while all(len(w) > common for w in words) and len({fold(w[common]) for w in words}) == 1:
        common += 1
    return [" ".join(w[common:]) for w in words]


def _head(text: str) -> str:
    return " ".join(fold(text).split()[:_VARIANT_HEAD_WORDS])


def _narrow(question: str, tables: list[CaptionedTable]) -> tuple[list[CaptionedTable], bool]:
    """(bảng còn lại, câu hỏi đã chỉ bảng chưa). Tên riêng nằm trọn trong câu hỏi thắng; không có thì so phần đầu
    ("nhúng toàn phần" chọn Bảng C.1 chứ không chọn "nhúng toàn phần theo ΓOCT", trừ khi câu nhắc ΓOCT)."""
    remainders = _remainders(tables)
    full = [t for t, r in zip(tables, remainders, strict=True) if r and fold(r) in question]
    if full:
        return full, True
    head = [t for t, r in zip(tables, remainders, strict=True) if r and _head(r) in question]
    if head:
        return head, True
    return tables, not any(remainders)


def _core(name: str) -> str:
    words = fold(name).split()
    if words[:2] == ["gia", "tri"] and len(words) > 2:
        words = words[2:]
    return " ".join(words[:2])


def _given(param: Parameter, question: str) -> bool:
    core = _core(param.name)
    if core and core in question:
        return True
    if any(fold(option) in question for option in param.options):
        return True
    if core.startswith("pham vi") and _RANGE_RE.search(question):
        return True
    return core.startswith("cap") and bool(_GRADE_RE.search(question))


def _missing(question: str, tables: list[CaptionedTable], table_chosen: bool) -> list[str]:
    """Các dòng "thông số còn thiếu" để hỏi lại, theo thứ tự xuất hiện trong bảng."""
    lines: list[str] = []
    if not table_chosen:
        listed = "; ".join(f"{r} ({t.label})" for t, r in zip(tables, _remainders(tables), strict=True) if r)
        lines.append(f"Bảng áp dụng: {listed}")
    seen: set[str] = set()
    for table in tables:
        for param in _table_parameters(table):
            key = _core(param.name)
            if key in seen:
                continue
            seen.add(key)
            if not _given(param, question):
                options = f": {', '.join(param.options)}" if param.options else ""
                lines.append(f"{param.name[:1].upper()}{param.name[1:]}{options}")
    return lines


def _hit(stem: str, table: CaptionedTable) -> dict:
    payload = {"text": table.text, "file_stem": stem, "section_path": table.title, "kind": "table"}
    return {"payload": payload, "rerank_score": 1.0}


def _decimal(text: str) -> Decimal:
    return Decimal(re.sub(r"\s+", "", text).replace(",", "."))


def _numbers(text: str) -> list[Decimal]:
    return [_decimal(m) for m in _NUMBER_RE.findall(fold(text))]


def _row_matches(table: CaptionedTable, index: int, question: str) -> Callable[[tuple[str, ...]], bool] | None:
    """Bộ lọc dòng theo giá trị câu hỏi nêu cho cột ``index``; ``None`` nếu câu hỏi không nêu được giá trị."""
    options = _options(table, index)
    if options:
        chosen = [o for o in options if fold(o) in question]
        if not chosen:
            return None
        best = fold(max(chosen, key=len))
        return lambda row: fold(row[index]) == best
    core = _core(_name(table.header[index]))
    if core.startswith("pham vi"):
        span = _QUESTION_RANGE_RE.search(question)
        if not span:
            return None
        wanted = [_decimal(span.group(1)), _decimal(span.group(2))]
        return lambda row: _numbers(row[index]) == wanted
    value = re.search(re.escape(core) + r"[^\d-]{0,25}(-?\d+(?:[.,]\d+)?)", question)
    if not value:
        return None
    wanted_value = _decimal(value.group(1))
    return lambda row: wanted_value in _numbers(row[index])


def _verdict(stem: str, profile: doc_profile.DocProfile, table: CaptionedTable, question: str) -> ClarifyAnswer | None:
    """Đủ thông số, còn đúng một bảng đơn giản: tra đúng một dòng rồi so sai số đo với sai số cho phép."""
    limits = [i for i, cell in enumerate(table.header) if cell and _is_limit(cell)]
    measured = _MEASURED_RE.findall(question)
    if table.subheaders or len(limits) != 1 or not measured:
        return None
    rows = list(table.rows)
    used: list[int] = []
    for index, cell in enumerate(table.header):
        if index == limits[0] or not cell or fold(cell) in _SKIP_COLUMNS:
            continue
        keep = _row_matches(table, index, question)
        if keep is None:
            return None
        rows = [row for row in rows if len(row) > index and keep(row)]
        used.append(index)
    limit_values = _numbers(rows[0][limits[0]]) if len(rows) == 1 else []
    if len(limit_values) != 1:
        return None  # không đúng một dòng / ô giới hạn không phải một số: để pipeline trả lời
    limit, error = abs(limit_values[0]), abs(_decimal(measured[-1]))
    unit = table.header[limits[0]].split(",", 1)[1].strip() if "," in table.header[limits[0]] else ""
    row = rows[0]
    picked = "\n".join(f"- {_name(table.header[i])}: {row[i]}" for i in used)
    allowed = f"{row[limits[0]]} {unit}".strip()
    verdict = "Đạt" if error <= limit else "Không đạt"
    sign = "≤" if error <= limit else ">"
    header = f"**{profile.label} - {profile.title}**" if profile.title else f"**{profile.label}**"
    text = (
        f"{header}\n\nTheo {table.title} [1]:\n\n{picked}\n- Sai số cho phép: ± {allowed}"
        f"\n\nSai số {measured[-1]} {sign} {row[limits[0]]}: **{verdict}**."
    )
    return ClarifyAnswer(text, [_hit(stem, table)])


def _with_previous_question(question: str, previous: tuple[str, str] | None) -> str:
    """Người dùng trả lời câu hỏi lại ("thủy ngân, nhúng toàn phần, độ chia 0,1"): ghép với câu hỏi ban đầu."""
    if previous is None or _CLARIFY_MARK not in previous[1]:
        return question
    return f"{previous[0]} {question}"


def try_clarify(question: str, previous: tuple[str, str] | None = None) -> ClarifyAnswer | None:
    """Hỏi lại thông số còn thiếu, hoặc kết luận tất định khi đã đủ; ``None`` để chat đi tiếp như cũ.

    ``previous`` = (câu hỏi, câu trả lời) của lượt trước: nếu lượt trước là câu hỏi lại thì lượt này là phần
    trả lời bổ sung thông số, được ghép với câu hỏi ban đầu.
    """
    cfg = get_settings().limit_clarify
    question = _with_previous_question(question, previous)
    q = fold(question)
    if not cfg.enabled or not re.search(cfg.question_pattern, q):
        return None
    stems = router.route_files(question)
    if len(stems) != 1:
        return None
    stem = next(iter(stems))
    path = Path(get_settings().paths.markdown_dir) / f"{stem}.md"
    profile = doc_profile.profile_for(stem)
    if profile is None or not path.exists():
        return None
    tables = [t for t in captioned_tables(path.read_text(encoding="utf-8")) if _is_limit(t.caption)]
    tables = tables[: cfg.max_tables]
    if not tables:
        return None
    tables, table_chosen = _narrow(q, tables)
    missing = _missing(q, tables, table_chosen)
    if not missing:
        return _verdict(stem, profile, tables[0], q) if len(tables) == 1 else None
    hits = [_hit(stem, table) for table in tables]
    header = f"**{profile.label} - {profile.title}**" if profile.title else f"**{profile.label}**"
    listed = "\n".join(f"- {table.title} [{n}]" for n, table in enumerate(tables, 1))
    asks = "\n".join(f"- {line}" for line in missing)
    text = (
        f"{header}\n\n{_CLARIFY_MARK}: giới hạn cho phép trong tài liệu được tra "
        f"theo bảng, phụ thuộc vào các thông số mà câu hỏi chưa nêu.\n\nCác bảng giới hạn trong tài liệu:\n\n{listed}"
        f"\n\nVui lòng cho biết thêm:\n\n{asks}\n\nCó đủ các thông số trên thì mới tra đúng một ô của bảng để kết luận."
    )
    return ClarifyAnswer(text, hits)
