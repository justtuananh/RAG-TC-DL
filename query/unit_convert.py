"""Quy đổi đơn vị thuần túy, tất định (không qua LLM, không cần công thức duyệt).

Câu chỉ có MỘT đại lượng ``<số> <đơn vị>`` và MỘT đơn vị đích ("quy đổi 5 bar sang kPa", "5 bar bằng
bao nhiêu kPa") thì không phải bài toán kiểm định: chỉ cần hệ số của bảng ``UNITS`` (bộ tính Decimal
``formula_lab.engine``). Câu có đại lượng thứ hai hoặc không đúng mẫu trả ``None`` để chat đi tiếp như cũ.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from core.settings_loader import get_settings
from formula_lab.engine import UNITS
from query.chat_calc import _fmt

_NON_UNITS = {"1", "%", "delta_degC"}
_BY_LOWER = {k.lower(): k for k in UNITS if k not in _NON_UNITS}
_UNIT_ALIASES = {"phút": "min", "giây": "s", "giờ": "h"}
_BY_LOWER |= {k: v for k, v in _UNIT_ALIASES.items() if v in UNITS}
_UNIT = "|".join(re.escape(u) for u in sorted(_BY_LOWER, key=len, reverse=True))
_NUM = r"(\d+(?:[.,]\d+)?)"
_END = r"(?![\w/.]*\w)"  # đơn vị không được dính tiếp chữ/số/'/' (tránh "bar" trong "barrel", "m" trong "mm/s")
_NUMBER_ANY = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class Conversion:
    text: str


def _patterns() -> list[re.Pattern]:
    verbs = get_settings().calc.convert_verbs
    pre = r"(?:hãy\s+|vui lòng\s+|giúp\s+|cho\s+(?:tôi|mình)\s+)*"
    return [
        re.compile(rf"^\W*{pre}(?:{verbs})\s+{_NUM}\s*({_UNIT}){_END}\s+(?:sang|ra|thành|về|qua)\s+({_UNIT}){_END}\W*$", re.I),
        re.compile(rf"^\W*{pre}{_NUM}\s*({_UNIT}){_END}\s+(?:bằng|=|là|tương đương)\s+bao nhiêu\s+({_UNIT}){_END}\W*$", re.I),
        re.compile(rf"^\W*{pre}(?:{verbs})\s+{_NUM}\s*({_UNIT}){_END}\s+(?:sang|ra|thành|về|qua)\s+đơn vị\s+({_UNIT}){_END}\W*$", re.I),
    ]


def _canon(raw: str) -> str:
    return _BY_LOWER[raw.lower()]


def try_convert(message: str) -> Conversion | None:
    cfg = get_settings().calc
    if not cfg.convert_enabled or len(_NUMBER_ANY.findall(message)) != 1:
        return None
    for pat in _patterns():
        m = pat.match(message.strip())
        if not m:
            continue
        value, src, dst = m.group(1), _canon(m.group(2)), _canon(m.group(3))
        num = Decimal(value.replace(",", "."))
        (cat_s, f_s), (cat_d, f_d) = UNITS[src], UNITS[dst]
        if cat_s != cat_d:
            return Conversion(f"Không quy đổi được: {src} và {dst} không cùng loại đại lượng.")
        factor = Decimal(f_s) / Decimal(f_d)
        return Conversion(
            f"{_fmt(num)} {src} = {_fmt(num * factor)} {dst} (hệ số: 1 {src} = {_fmt(factor)} {dst})."
        )
    return None
