"""Quy đổi đơn vị đo về SI dựa trên bảng ``unit`` (spec §5.1, §6).

Quy tắc bất di bất dịch: **quy đổi chỉ chạy khi đơn vị được nhận diện chắc
chắn**. Đơn vị lạ → trả ``None`` để tầng gọi bỏ trống ``value_min``/``value_max``
và giữ nguyên ``value_text``, hạ điểm tin cậy cho người duyệt. Thà thiếu dữ liệu
lọc còn hơn lọc ra kết quả sai đơn vị.

Phần toán là thuần hàm (``to_si``/``from_si``/``convert``) để test đối xứng hai
chiều cho từng đơn vị; phần tra cứu chỉ đọc DB và dựng ``UnitDef``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping

from knowledge import vnnum

# Đồng bộ ký tự trước khi tra cứu: micro sign/greek mu, số mũ trên, độ C.
_SUPERSCRIPTS = str.maketrans({"²": "2", "³": "3", "¹": "1"})
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class UnitDef:
    """Định nghĩa đơn vị đã chuẩn hóa: ``si = factor_to_si * x + offset_to_si``."""

    code: str
    factor_to_si: float
    offset_to_si: float = 0.0
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class SiConversion:
    """Kết quả quy đổi một biểu thức; ``resolved=False`` nghĩa là đơn vị lạ."""

    value_min: float | None
    value_max: float | None
    unit_code: str | None
    resolved: bool


def normalize_unit_text(text: str | None) -> str:
    """Chuẩn hóa chuỗi đơn vị để tra cứu: thường hóa, bỏ khoảng trắng, đồng bộ ký tự.

    >>> normalize_unit_text("kgf/cm²")
    'kgf/cm2'
    >>> normalize_unit_text("% RH")
    '%rh'
    >>> normalize_unit_text("độ C")
    'c'
    """
    if not text:
        return ""
    s = vnnum.normalize_spaces(text).lower()
    s = s.replace("\u03bc", "\u00b5")  # greek mu → micro sign
    s = s.translate(_SUPERSCRIPTS)
    s = s.replace("°c", "c").replace("ºc", "c")
    s = s.replace("độ", "")
    s = _WHITESPACE_RE.sub("", s)
    return s.strip(".,;:")


def to_si(value: float, unit: UnitDef) -> float:
    """Đổi giá trị theo đơn vị về SI: ``factor * value + offset``."""
    return unit.factor_to_si * value + unit.offset_to_si


def from_si(si_value: float, unit: UnitDef) -> float:
    """Đổi giá trị SI về đơn vị: ``(si - offset) / factor``."""
    return (si_value - unit.offset_to_si) / unit.factor_to_si


def convert(value: float, from_unit: UnitDef, to_unit: UnitDef) -> float:
    """Đổi giá trị giữa hai đơn vị (đi vòng qua SI)."""
    return from_si(to_si(value, from_unit), to_unit)


def unit_lookup(units: Iterable[UnitDef]) -> dict[str, UnitDef]:
    """Dựng bảng tra ``text đã chuẩn hóa → UnitDef`` từ code và mọi alias."""
    lookup: dict[str, UnitDef] = {}
    for unit in units:
        keys = {unit.code, *unit.aliases}
        for key in keys:
            normalized = normalize_unit_text(key)
            if normalized:
                lookup.setdefault(normalized, unit)
    return lookup


def resolve_unit(text: str | None, units: Iterable[UnitDef]) -> UnitDef | None:
    """Trả ``UnitDef`` nếu đơn vị nhận diện chắc chắn, ngược lại ``None``."""
    return unit_lookup(units).get(normalize_unit_text(text))


def convert_to_si(
    value: float | None, unit_text: str | None, units: Iterable[UnitDef]
) -> float | None:
    """Quy đổi một giá trị về SI; ``None`` nếu thiếu giá trị hoặc đơn vị lạ."""
    if value is None:
        return None
    unit = resolve_unit(unit_text, units)
    if unit is None:
        return None
    return to_si(value, unit)


def convert_quantity_to_si(
    parsed: vnnum.ParsedQuantity, units: Iterable[UnitDef]
) -> SiConversion:
    """Quy đổi một ``ParsedQuantity`` về SI, giữ rõ trạng thái đơn vị lạ.

    Đơn vị lạ: ``resolved=False`` và ``value_min``/``value_max`` để trống —
    tầng gọi vẫn giữ ``parsed.raw`` làm ``value_text``.
    """
    unit = resolve_unit(parsed.unit, units)
    if unit is None:
        return SiConversion(None, None, None, False)
    value_min = to_si(parsed.value_min, unit) if parsed.value_min is not None else None
    value_max = to_si(parsed.value_max, unit) if parsed.value_max is not None else None
    return SiConversion(value_min, value_max, unit.code, True)


def load_unit_defs(session) -> list[UnitDef]:
    """Đọc bảng ``unit`` và dựng ``UnitDef``. Không quy đổi, không ghi."""
    from db.models import Unit

    return [
        UnitDef(
            code=row.code,
            factor_to_si=row.factor_to_si,
            offset_to_si=row.offset_to_si or 0.0,
            aliases=tuple(row.aliases or ()),
        )
        for row in session.query(Unit).all()
    ]


def unit_lookup_from_db(session) -> Mapping[str, UnitDef]:
    """Tiện lợi: tra cứu đơn vị trực tiếp từ DB."""
    return unit_lookup(load_unit_defs(session))
