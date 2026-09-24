"""Phân tích số, khoảng, sai số ``±`` và tách đơn vị kiểu Việt Nam.

Module này chịu trách nhiệm DUY NHẤT cho việc đọc con số trong corpus đo lường
(spec §6). Nó thuần hàm, không phụ thuộc DB, nên test được bằng bảng liệt kê
mọi biến thể gặp trong tài liệu.

Quy ước Việt Nam:

- dấu phẩy là dấu thập phân: ``0,15``;
- dấu cách là dấu phân nhóm hàng nghìn: ``1 400`` — kể cả khoảng trắng hẹp
  không ngắt (U+202F) và khoảng trắng không ngắt (U+00A0) do PDF/Word sinh ra;
- khoảng viết bằng ``÷`` trong ngoặc ``(0 ÷ 100)`` hoặc bằng ``đến``/``tới``;
- sai số viết bằng ``±`` (có thể kèm giá trị trung tâm ``(1000 ± 40)``);
- đơn vị có thể dính hoặc tách khỏi số.

Nguyên tắc: khi không chắc chắn, trả ``None`` thay vì đoán. Thà thiếu dữ liệu
lọc còn hơn lọc ra kết quả sai đơn vị (spec §6, §12).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Mọi loại khoảng trắng có thể xuất hiện giữa các chữ số trong corpus.
_SPACE_CHARS = "\u00a0\u202f\u2009\u200a\u2007\u2028\u2029\u2060\ufeff"
_SPACE_RE = re.compile(f"[{re.escape(_SPACE_CHARS)}]")

# Dấu trừ Unicode (minus sign, en/em dash) → ASCII '-' cho việc phân tích số.
_MINUS_CHARS = "\u2212\u2013\u2014"

# Số: dấu, phần nguyên, phần thập phân (',' hoặc '.'), số mũ khoa học tùy chọn.
# Lookbehind loại chữ số nằm trong ký hiệu đơn vị (m2, cm2, H2O, kgf/cm2) để
# không nhặt nhầm "2" của đơn vị thành một giá trị đo.
_NUMBER_TOKEN_RE = re.compile(r"(?<![A-Za-zµ%°])([+\-\u2212]?\d+(?:[.,]\d+)?(?:e[+\-]?\d+)?)")

# Ký hiệu khoa học kiểu tài liệu: "8,051516×10-5" / "2,91x10^-9".
_SCIENTIFIC_RE = re.compile(r"[×xX]\s*10\s*\^?\s*([+\-\u2212]?\d+)")

# Từ khóa mô tả khoảng (không phải đơn vị).
_RANGE_WORD_RE = re.compile(r"\b(?:từ|đến|tới|to)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedRange:
    """Một khoảng giá trị ``low .. high`` (một đầu có thể None nếu mở)."""

    low: float | None
    high: float | None
    raw: str


@dataclass(frozen=True)
class ParsedTolerance:
    """Sai số dạng ``±``: giá trị trung tâm tùy chọn + sai số cộng/trừ."""

    center: float | None
    plus: float
    minus: float
    raw: str


@dataclass(frozen=True)
class ParsedQuantity:
    """Kết quả phân tích một biểu thức đo lường đầy đủ.

    ``rel_op`` nhận ``"="`` (vô hướng), ``"range"`` (khoảng) hoặc ``"±"`` (sai số).
    Với ``"="``, ``value_min == value_max ==`` giá trị. Với ``"±"``, ``value_min``
    và ``value_max`` giữ giá trị trung tâm (nếu có), còn ``plus``/``minus`` giữ sai số.
    """

    rel_op: str
    value_min: float | None
    value_max: float | None
    plus: float | None
    minus: float | None
    unit: str | None
    raw: str


def normalize_spaces(text: str | None) -> str:
    """Chuẩn hóa mọi loại khoảng trắng (gồm NBSP/NNBSP) về dấu cách thường."""
    if not text:
        return ""
    s = _SPACE_RE.sub(" ", text)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _normalize_minus(s: str) -> str:
    for ch in _MINUS_CHARS:
        s = s.replace(ch, "-")
    return s


def _normalize_scientific(s: str) -> str:
    return _SCIENTIFIC_RE.sub(lambda m: "e" + _normalize_minus(m.group(1)), s)


def _strip_grouping(s: str) -> str:
    """Bỏ dấu cách phân nhóm hàng nghìn nằm giữa hai chữ số: ``1 400`` → ``1400``."""
    return re.sub(r"(?<=\d) (?=\d)", "", s)


def parse_number(text: str | None) -> float | None:
    """Chuyển một chuỗi số kiểu Việt sang ``float``; trả ``None`` nếu mơ hồ.

    >>> parse_number("0,15")
    0.15
    >>> parse_number("1 400")
    1400.0
    >>> parse_number("1\\u202f400")
    1400.0
    """
    if not text:
        return None
    s = _normalize_minus(_normalize_scientific(normalize_spaces(text)))
    s = _strip_grouping(s)
    m = re.fullmatch(r"([+\-]?)(\d+(?:[.,]\d+)?)(?:e([+\-]?\d+))?", s)
    if not m:
        return None
    sign, body, exponent = m.group(1), m.group(2), m.group(3)

    if "," in body and "." in body:
        # Dấu phân tách xuất hiện sau cùng là dấu thập phân.
        if body.rfind(",") > body.rfind("."):
            body = body.replace(".", "").replace(",", ".")
        else:
            body = body.replace(",", "")
    elif "," in body:
        if body.count(",") > 1:
            return None
        body = body.replace(",", ".")
    elif "." in body:
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", body):
            body = body.replace(".", "")  # 1.061 → 1061 (phân nhóm hàng nghìn)
        elif body.count(".") != 1:
            return None

    try:
        return float(f"{sign}{body}" + (f"e{exponent}" if exponent else ""))
    except ValueError:
        return None


def _numbers(text: str) -> list[float]:
    prepared = _strip_grouping(_normalize_scientific(normalize_spaces(text)))
    values: list[float] = []
    for token in _NUMBER_TOKEN_RE.findall(prepared):
        value = parse_number(token)
        if value is not None:
            values.append(value)
    return values


def numbers(text: str | None) -> list[float]:
    """Danh sách mọi số đọc được trong ``text`` theo quy ước Việt.

    Khác ``parse_number`` (một chuỗi số đơn), hàm này quét cả câu và trả về mọi
    giá trị tìm thấy. Dùng cho hàng rào chống bịa số ở §6: ``quote`` mà LLM khai
    báo phải chứa đúng con số nó gán.

    >>> numbers("± 3% áp suất, không nhỏ hơn ± 0,15 bar")
    [3.0, 0.15]
    >>> numbers(None)
    []
    """
    if not text:
        return []
    return _numbers(text)


def _extract_unit(text: str) -> str | None:
    """Lấy phần đơn vị còn lại sau khi bỏ số, ngoặc, ``±``, ``÷`` và từ khóa khoảng."""
    prepared = _strip_grouping(_normalize_scientific(normalize_spaces(text)))
    cleaned = _NUMBER_TOKEN_RE.sub(" ", prepared)
    cleaned = cleaned.replace("±", " ")
    cleaned = re.sub(r"[()\[\]]", " ", cleaned)
    cleaned = cleaned.replace("÷", " ")
    cleaned = _RANGE_WORD_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,;:-")
    if not cleaned:
        return None
    tokens = cleaned.split()
    if len(set(tokens)) == 1:
        return tokens[0]
    return cleaned


def _is_range(text: str) -> bool:
    prepared = normalize_spaces(text)
    return "÷" in prepared or bool(_RANGE_WORD_RE.search(prepared))


def parse_quantity(text: str | None) -> ParsedQuantity | None:
    """Phân tích một biểu thức đo lường đầy đủ (số/khoảng/sai số + đơn vị)."""
    if not text:
        return None
    raw = text
    prepared = _strip_grouping(_normalize_scientific(normalize_spaces(text)))
    unit = _extract_unit(prepared)
    values = _numbers(prepared)
    if not values:
        return None

    if "±" in prepared:
        plus = abs(values[-1])
        center = values[0] if len(values) >= 2 else None
        return ParsedQuantity("±", center, center, plus, plus, unit, raw)

    if _is_range(prepared):
        if len(values) < 2:
            return None
        low, high = values[0], values[1]
        if low > high:
            low, high = high, low
        return ParsedQuantity("range", low, high, None, None, unit, raw)

    value = values[0]
    return ParsedQuantity("=", value, value, None, None, unit, raw)


def parse_range(text: str | None) -> ParsedRange | None:
    """Nhận diện khoảng; trả ``None`` nếu không phải khoảng."""
    parsed = parse_quantity(text)
    if parsed is None or parsed.rel_op != "range":
        return None
    return ParsedRange(parsed.value_min, parsed.value_max, parsed.raw)


def parse_tolerance(text: str | None) -> ParsedTolerance | None:
    """Nhận diện sai số ``±``; trả ``None`` nếu không có ``±``."""
    parsed = parse_quantity(text)
    if parsed is None or parsed.rel_op != "±":
        return None
    return ParsedTolerance(parsed.value_min, parsed.plus or 0.0, parsed.minus or 0.0, parsed.raw)


def split_value_unit(text: str | None) -> tuple[str | None, str | None]:
    """Tách giá trị (token số cuối) và đơn vị đứng sau nó.

    >>> split_value_unit("1 400 bar")
    ('1400', 'bar')
    >>> split_value_unit("(0 ÷ 100) %RH")
    ('100', '%RH')
    """
    if not text:
        return None, None
    prepared = _strip_grouping(_normalize_scientific(normalize_spaces(text)))
    matches = list(_NUMBER_TOKEN_RE.finditer(prepared))
    if not matches:
        return None, _extract_unit(prepared)
    last = matches[-1]
    value_text = prepared[last.start() : last.end()]
    unit = prepared[last.end() :].strip(" .,;:-()[]")
    return value_text, (unit or None)
