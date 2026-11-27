"""Dải đo trong các file danh mục 877: tách số + đơn vị, quy về đơn vị SI bằng Decimal.

Cột "Tham số đo lường" / "Đặc tính đo lường" ghi dải đo bằng nhiều dạng: "Từ - 0,1 MPa đến 0 MPa",
"(0,2 đến 5 000) bar", "(- 30 ÷ 155) oC", "Dải đo tới 140 MPa", "Từ nhiệt độ môi trường đến 300 oC".
Dải được quy về SI để so sánh với con số trong câu hỏi ("áp kế píttông 3000 bar" với "0 MPa đến
500 MPa"). Cột số chỉ dùng để lọc; câu trả lời luôn trích nguyên văn.

Bảng đơn vị đặt ở đây (không đọc bảng ``unit`` trong DB) vì danh mục dùng cả các đơn vị bảng đó
chưa có (r/min, L/min, mH2O, mS/cm), và để việc tách dải chạy được khi chưa có Postgres.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# đơn vị (viết như trong tài liệu) → (đại lượng, hệ số, độ lệch): si = hệ số * x + độ lệch.
_UNITS: dict[str, tuple[str, str, str]] = {
    "Pa": ("pressure", "1", "0"),
    "kPa": ("pressure", "1000", "0"),
    "MPa": ("pressure", "1000000", "0"),
    "hPa": ("pressure", "100", "0"),
    "bar": ("pressure", "100000", "0"),
    "mbar": ("pressure", "100", "0"),
    "mmHg": ("pressure", "133.322387415", "0"),
    "mH2O": ("pressure", "9806.65", "0"),
    "mmH2O": ("pressure", "9.80665", "0"),
    "kgf/cm2": ("pressure", "98066.5", "0"),
    "kgf/cm²": ("pressure", "98066.5", "0"),
    "psi": ("pressure", "6894.757293168", "0"),
    "°C": ("temperature", "1", "273.15"),
    "oC": ("temperature", "1", "273.15"),
    "ºC": ("temperature", "1", "273.15"),
    "độ C": ("temperature", "1", "273.15"),
    "C": ("temperature", "1", "273.15"),
    "r/min": ("rotation", "1", "0"),
    "vòng/phút": ("rotation", "1", "0"),
    "rpm": ("rotation", "1", "0"),
    "L/min": ("flow", "1", "0"),
    "lít/phút": ("flow", "1", "0"),
    "L/h": ("flow", "0.01666666666666666666666666667", "0"),
    "m3/h": ("flow", "16.66666666666666666666666667", "0"),
    "mL": ("volume", "0.001", "0"),
    "L": ("volume", "1", "0"),
    "lít": ("volume", "1", "0"),
    "m3": ("volume", "1000", "0"),
    "%RH": ("humidity", "1", "0"),
    "pH": ("ph", "1", "0"),
    "mS/cm": ("conductivity", "0.001", "0"),
    "µS/cm": ("conductivity", "0.000001", "0"),
    "μS/cm": ("conductivity", "0.000001", "0"),
    "mg": ("mass", "0.000001", "0"),
    "g": ("mass", "0.001", "0"),
    "kg": ("mass", "1", "0"),
}
# Tên đại lượng hiển thị cho người dùng.
QUANTITY_LABELS = {
    "pressure": "Áp suất",
    "temperature": "Nhiệt độ",
    "rotation": "Tốc độ vòng quay",
    "flow": "Lưu lượng",
    "volume": "Dung tích",
    "humidity": "Độ ẩm",
    "ph": "Hóa lý",
    "conductivity": "Hóa lý",
    "mass": "Khối lượng",
}
_BY_LOWER = {u.lower(): u for u in _UNITS}
_UNIT_ALT = "|".join(re.escape(u) for u in sorted(_UNITS, key=len, reverse=True))


def _unit(name: str) -> str:
    # Đơn vị không được dính tiếp chữ/số ("bar" trong "barrel", "L" trong "Lò", "C" trong "CCX").
    return rf"(?P<{name}>{_UNIT_ALT})(?![\w/²³])"


_NUM = r"[-−–]?\s?(?:\d{1,3}(?:[   ]\d{3})+|\d+)(?:,\d+)?(?!\d)"
_SEP = r"\s*(?:đến|tới|÷|…)\s*"
_RANGE_PATTERNS = (
    # "(0,2 đến 5 000) bar"
    re.compile(rf"\(\s*(?P<lo>{_NUM}){_SEP}(?P<hi>{_NUM})\s*\)\s*{_unit('unit')}", re.IGNORECASE),
    # "Từ - 0,1 MPa đến 500 MPa", "từ 8 mmHg đến 800 mmHg", "-40 oC đến 80 C"
    re.compile(rf"(?P<lo>{_NUM})\s*(?:{_unit('lounit')})?{_SEP}(?P<hi>{_NUM})\s*{_unit('unit')}", re.IGNORECASE),
    # "Dải đo tới 140 MPa", "Từ nhiệt độ môi trường đến 300 oC", "Phạm vi làm việc đến 600 bar"
    re.compile(rf"(?:đến|tới)\s+(?P<hi>{_NUM})\s*{_unit('unit')}", re.IGNORECASE),
)
# Chỉ đoạn có nhãn chỉ dải mới được coi là dải đo: "Độ ổn định nhiệt độ: Đến 0,5 oC" là độ chính xác.
_RANGE_LABEL_RE = re.compile(
    r"dải|phạm vi|giá trị tạo|tạo (?:và đo )?(?:áp|tốc)|làm việc|tiếp xúc|lưu lượng|dung tích|đo tới|đo đến",
    re.IGNORECASE,
)
_QUESTION_QTY_RE = re.compile(rf"(?P<num>{_NUM})\s*{_unit('unit')}", re.IGNORECASE)
_INTERVAL_RE = re.compile(r"(\d+(?:,\d+)?)\s*(năm|tháng)", re.IGNORECASE)


@dataclass(frozen=True)
class CatalogRange:
    """Một dải đo. ``min_si`` ``None`` khi chỉ ghi giới hạn trên ("đến 140 MPa")."""

    label: str
    quantity: str
    min_si: Decimal | None
    max_si: Decimal
    text: str

    def contains(self, value_si: Decimal) -> bool:
        return (self.min_si is None or self.min_si <= value_si) and value_si <= self.max_si


@dataclass(frozen=True)
class Quantity:
    """Một đại lượng nêu trong câu hỏi ("3000 bar")."""

    quantity: str
    value_si: Decimal
    raw: str


def canonical_unit(raw: str) -> str | None:
    return raw if raw in _UNITS else _BY_LOWER.get(raw.lower())


def to_decimal(raw: str) -> Decimal | None:
    """Số kiểu Việt ("- 0,1", "5 000", "1.400") → Decimal; ``None`` nếu không đọc được."""
    text = re.sub(r"[\s  ]", "", raw).replace("−", "-").replace("–", "-")
    if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", text):
        text = text.replace(".", "")
    text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def to_si(value: Decimal, unit: str) -> tuple[str, Decimal] | None:
    canonical = canonical_unit(unit)
    if canonical is None:
        return None
    quantity, factor, offset = _UNITS[canonical]
    return quantity, value * Decimal(factor) + Decimal(offset)


def _segments(text: str) -> list[str]:
    parts = re.split(r"[;\n]|(?<=\D)\.\s+(?=[A-ZĐ])", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def _label(segment: str, start: int) -> str:
    head = segment[:start].strip(" :-–(")
    return head.split(":")[0].strip() if head else ""


def parse_ranges(text: str | None) -> list[CatalogRange]:
    """Mọi dải đo trong một ô danh mục, theo thứ tự xuất hiện."""
    result: list[CatalogRange] = []
    for segment in _segments(text or ""):
        taken: list[tuple[int, int]] = []
        found: list[tuple[int, CatalogRange]] = []
        for pattern in _RANGE_PATTERNS:
            for match in pattern.finditer(segment):
                if any(s < match.end() and match.start() < e for s, e in taken):
                    continue
                label = _label(segment, match.start())
                if not _RANGE_LABEL_RE.search(label or segment):
                    continue
                parsed = _range(match, label, segment)
                if parsed is not None:
                    taken.append((match.start(), match.end()))
                    found.append((match.start(), parsed))
        result.extend(item for _, item in sorted(found, key=lambda pair: pair[0]))
    return result


def _range(match: re.Match, label: str, segment: str) -> CatalogRange | None:
    unit = match.group("unit")
    hi = to_decimal(match.group("hi"))
    hi_si = to_si(hi, unit) if hi is not None else None
    if hi_si is None:
        return None
    quantity, max_si = hi_si
    min_si: Decimal | None = None
    groups = match.groupdict()
    if groups.get("lo") is not None:
        lo = to_decimal(groups["lo"])
        lo_si = to_si(lo, groups.get("lounit") or unit) if lo is not None else None
        if lo_si is None or lo_si[0] != quantity:
            return None
        min_si = lo_si[1]
    if min_si is not None and min_si > max_si:
        min_si, max_si = max_si, min_si
    return CatalogRange(label=label or "Dải đo", quantity=quantity, min_si=min_si, max_si=max_si, text=segment)


def question_quantities(text: str | None) -> list[Quantity]:
    """Các đại lượng "<số> <đơn vị>" trong câu hỏi, đã quy về SI."""
    result: list[Quantity] = []
    for match in _QUESTION_QTY_RE.finditer(text or ""):
        value = to_decimal(match.group("num"))
        converted = to_si(value, match.group("unit")) if value is not None else None
        if converted is not None:
            result.append(Quantity(quantity=converted[0], value_si=converted[1], raw=match.group(0).strip()))
    return result


def interval_months(text: str | None) -> int | None:
    """Chu kỳ "5 năm" → 60, "18 tháng" → 18; ``None`` khi thiếu đơn vị ("1")."""
    match = _INTERVAL_RE.search(text or "")
    if not match:
        return None
    value = to_decimal(match.group(1))
    if value is None:
        return None
    months = value * 12 if match.group(2).lower() == "năm" else value
    return int(months)
