"""Mã quy trình trong các file danh mục 877: tách, chuẩn hoá, so khớp.

Ô Word ghi mã rất không thống nhất: "QTKĐ 1.159 : 2021", "QTKĐ 1.160.2021", "QTKĐ 1.023 :2009",
"23 QTKĐ 1.0017 : 2006", "ĐLVN 10: 2017", "QTHC 1.025:2009", kể cả nhiều mã dính liền trong một
đoạn ("QTKĐ 1.005 : 201023 QTKĐ 1.002 : 2002"). Module này là nơi DUY NHẤT hiểu các dạng đó, dùng
chung cho bộ nạp danh mục, bộ khớp câu hỏi và bước liên kết danh mục với tài liệu trong kho.

Khoá của một quy trình là ``tiền tố + số + năm``: danh mục có nhiều cặp trùng số khác năm là hai
quy trình khác nhau (QTKĐ 1.017:2008 tủ sấy, QTKĐ 1.017:2014 chỉ thị nhiệt độ).
Mã không theo mẫu nào ("06.TCN 3.80-88", "A1-04.PP01.05") giữ nguyên văn làm khoá.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_CANONICAL_PREFIX = {"QTKD": "QTKĐ", "QTHC": "QTHC", "DLVN": "ĐLVN", "TCVN": "TCVN"}
# "23 QTKĐ" là bộ quy trình cũ đánh số 4 chữ số (1.0017); giữ tiền tố riêng để không trùng QTKĐ 1.017.
# "23" có thể dính ngay sau năm của mã trước ("1.005 : 201023 QTKĐ 1.002") nên nhận cả sau 4 chữ số.
_PREFIX = r"(?P<series>(?:\b|(?<=\d{4}))23\s*)?(?P<prefix>QTK[ĐD]|QTHC|[ĐD]LVN|TCVN)"
# Năm không đòi ranh giới phía sau vì mã kế tiếp có thể dính liền ("201023 QTKĐ ...").
_CODE_RE = re.compile(
    _PREFIX + r"\s*(?P<number>\d+(?:\.\d+)?)(?:\s*[:.]\s*(?P<year>(?:19|20)\d{2}))?",
    re.IGNORECASE,
)
# Mã trong tên tệp: "QTKD_1.061_2021_ND", "DLVN_08_2011".
_STEM_CODE_RE = re.compile(
    r"(?P<prefix>QTK[ĐD]|QTHC|[ĐD]LVN|TCVN)[_\s]+(?P<number>\d+(?:\.\d+)?)(?:[_\s]+(?P<year>(?:19|20)\d{2}))?",
    re.IGNORECASE,
)
# Mã không theo mẫu chuẩn nhưng có trong danh mục.
_OTHER_CODE_RE = re.compile(r"\d{2}\.TCN\s*[\d.]+-\d{2}|[A-Z]\d-\d{2}\.PP\d{2}\.\d{2}")


@dataclass(frozen=True)
class CatalogCode:
    """Một mã quy trình đã chuẩn hoá. ``prefix`` rỗng khi mã không theo mẫu (khoá là nguyên văn)."""

    raw: str
    prefix: str
    number: str
    year: int | None

    @property
    def key(self) -> str:
        """Khoá đầy đủ ``tiền tố + số + năm`` (hoặc mã nguyên văn đã gộp khoảng trắng)."""
        if not self.prefix:
            return " ".join(self.raw.split())
        return f"{self.prefix} {self.number}" + (f":{self.year}" if self.year else "")

    @property
    def base(self) -> str:
        """Khoá không năm, để so khi người dùng chỉ nói số ("QTKĐ 1.017")."""
        return f"{self.prefix} {self.number}" if self.prefix else self.key


def _canonical(prefix: str, series: str | None = None) -> str:
    folded = prefix.upper().replace("Đ", "D")
    canonical = _CANONICAL_PREFIX.get(folded, prefix.upper())
    return f"23 {canonical}" if series else canonical


def _code(match: re.Match, *, series: str | None = None) -> CatalogCode:
    year = match.group("year")
    return CatalogCode(
        raw=" ".join(match.group(0).split()),
        prefix=_canonical(match.group("prefix"), series),
        number=match.group("number"),
        year=int(year) if year else None,
    )


def parse_codes(text: str | None) -> list[CatalogCode]:
    """Mọi mã trong một đoạn văn bản, theo thứ tự xuất hiện, không trùng lặp."""
    source = unicodedata.normalize("NFC", text or "")
    found = [(m.start(), _code(m, series=m.group("series"))) for m in _CODE_RE.finditer(source)]
    for match in _OTHER_CODE_RE.finditer(source):
        raw = " ".join(match.group(0).split())
        found.append((match.start(), CatalogCode(raw=raw, prefix="", number=raw, year=None)))
    result: list[CatalogCode] = []
    seen: set[str] = set()
    for _, code in sorted(found, key=lambda item: item[0]):
        if code.key not in seen:
            seen.add(code.key)
            result.append(code)
    return result


def parse_code(text: str | None) -> CatalogCode | None:
    """Mã đầu tiên trong văn bản, ``None`` nếu không có."""
    codes = parse_codes(text)
    return codes[0] if codes else None


def stem_codes(file_stem: str) -> list[CatalogCode]:
    """Mã nằm trong tên tệp ("QTKD_1.061_2021_ND" → QTKĐ 1.061:2021)."""
    return [_code(m) for m in _STEM_CODE_RE.finditer(unicodedata.normalize("NFC", file_stem or ""))]


def same_procedure(a: CatalogCode, b: CatalogCode) -> bool:
    """Cùng tiền tố + số, và cùng năm nếu cả hai đều ghi năm."""
    if a.base != b.base:
        return False
    return a.year is None or b.year is None or a.year == b.year
