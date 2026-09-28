"""Phân tích giá trị một trường đầu mục biên bản thành số + đơn vị (Pha R).

Chỉ PHÂN TÍCH chuỗi nguồn, không tính gì mới (P2). Ba dạng gặp trong biên bản:

- khoảng: ``(50 đến 2 500) kgf/cm2;`` → ``range`` 50..2500, đơn vị ``kgf/cm2``;
- một giá trị kèm ký hiệu: ``A0 = 0,59878 × 10-5 , m2`` → ``=`` 5,9878e-6 ``m2``;
  ``uCmax = 787,500 × 10-3 (kG/cm2) tại p = 1 750,0 kG/cm2`` → ``=`` 0,7875
  ``kG/cm2`` (chỉ lấy giá trị ĐẦU; phần "tại p = ..." là ngữ cảnh);
- dung sai ``(20 ± 2) ºC``: giữ nguyên văn, không sinh cận (``±``, không có số).

Chuỗi không có số → không có giá trị số. Quy đổi SI do tầng ghi làm với bảng đơn
vị; đơn vị lạ vẫn giữ ``unit_text`` và số theo đơn vị gốc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from knowledge import vnnum

# Ký hiệu đứng trước dấu "=" ("A0 =", "uCmax =", "d =") không phải đơn vị.
# Ký hiệu mở đầu bằng chữ, có thể chứa số/ngoặc ("A0", "U(p)", "Δ(p)").
_SYMBOL_PREFIX_RE = re.compile(r"^\s*[^\W\d_][\w()]{0,10}\s*=\s*")
_PAREN_UNIT_RE = re.compile(r"^\s*\(\s*([^()\d][^()]{0,15}?)\s*\)")
_COMMA_UNIT_RE = re.compile(r"^\s*,\s*([^\s,;()]{1,12})")
_BARE_UNIT_RE = re.compile(r"^\s*([A-Za-zµ%°º/][\w%°º/²³]{0,11})")
# Giá trị số phải MỞ ĐẦU bằng số (sau ký hiệu "A0 ="): "Áp kế píttông PG7302" hay
# "QTKĐ 1.159 : 2021" là chữ, số bên trong không phải giá trị của trường.
_STARTS_NUMERIC_RE = re.compile(r"^[\s(+\-\u2212]*\d")
# Số dính "/số" là ngày hoặc số biên bản ("19/11/2024", "013/2024"), không phải giá trị.
_SLASH_NUMBER_RE = re.compile(r"^\s*/\s*\d")
# Từ nối mở đầu phần ngữ cảnh, không phải đơn vị ("(với k = 2)", "tại p = ...").
_CONTEXT_WORDS = ("với", "tại")


@dataclass(frozen=True)
class FieldValue:
    """Kết quả phân tích: ``rel_op`` (``range``/``=``/``±``), số theo ĐƠN VỊ GỐC."""

    rel_op: str | None = None
    value_min: float | None = None
    value_max: float | None = None
    unit_text: str | None = None


def _unit_after(rest: str) -> str | None:
    """Đơn vị đứng ngay sau số đầu tiên: ``(kG/cm2)``, ``, m2`` hoặc ``bar``."""
    for pattern in (_PAREN_UNIT_RE, _COMMA_UNIT_RE, _BARE_UNIT_RE):
        match = pattern.match(rest)
        if match is None:
            continue
        unit = match.group(1).strip(" .;,")
        if unit and unit.split()[0].casefold() not in _CONTEXT_WORDS:
            return unit
        return None
    return None


def parse_field_value(text: str | None) -> FieldValue:
    """Phân tích nguyên văn một trường; không nhận dạng được thì trả rỗng."""
    raw = vnnum.normalize_spaces(text or "").strip()
    if not raw or not any(char.isdigit() for char in raw):
        return FieldValue()
    if "±" in raw:
        return FieldValue(rel_op="±")
    body = _SYMBOL_PREFIX_RE.sub("", raw, count=1)
    if not _STARTS_NUMERIC_RE.match(body):
        return FieldValue()
    parsed = vnnum.parse_quantity(body)
    if parsed is not None and parsed.rel_op == "range":
        unit = parsed.unit.strip(" .,;") if parsed.unit else None
        return FieldValue("range", parsed.value_min, parsed.value_max, unit or None)

    # Một giá trị: số đầu tiên (đã gộp ký hiệu khoa học) + đơn vị ngay sau nó.
    prepared = vnnum.prepare_numbers(body)
    match = vnnum.first_number_token(prepared)
    if match is None:
        return FieldValue()
    value = vnnum.parse_number(match.group(0))
    if value is None or _SLASH_NUMBER_RE.match(prepared[match.end() :]):
        return FieldValue()
    return FieldValue("=", value, value, _unit_after(prepared[match.end() :]))
