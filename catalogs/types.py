"""Kiểu dữ liệu trung gian của bộ đọc danh mục hồ sơ NAS (Biểu 1, 3, 4, 7).

Bộ đọc không chạm DB: trả ``CatalogDraft`` thuần dữ liệu, tầng ghi sổ cái quyết
định lưu thế nào (một ``extraction`` ``pending`` cho mỗi lần đọc, P3).

Bất biến:

- **P1**: mỗi dòng giữ ``quote`` là nguyên văn cả dòng nguồn (ô nối bằng " | ",
  các đoạn trong một ô nối bằng " / "), kể cả chữ "nt" (như trên).
- **P2**: số chỉ tách từ chính ô nguồn; ``interval_months`` chỉ có khi ô ghi rõ
  đơn vị "năm"/"tháng", không đoán.
- ``inherited`` liệt kê các trường lấy từ dòng trên do ô ghi "nt".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class ProcedureCode:
    """Một mã tiêu chuẩn/quy trình ("QTKĐ 1.159 : 2021", "ĐLVN 263 : 2014")."""

    raw: str
    normalized: str
    family: str | None = None  # "QTKĐ", "ĐLVN", "TCVN", "TC", "06.TCN"...; None nếu không nhận dạng
    prefix: str | None = None  # tiền tố cơ quan ("23" trong "23 QTKĐ 1.039 : 2001")
    number: str | None = None
    year: int | None = None

    @property
    def procedure_number(self) -> str | None:
        """Số QTKĐ để khớp ``procedure.number`` ("1.159"); chỉ họ QTKĐ không tiền tố."""
        return self.number if self.family == "QTKĐ" and not self.prefix else None


@dataclass
class LabStandardDraft:
    """Một chuẩn mẫu / PTĐ / PTTN (Biểu 3)."""

    ord: int | None
    name: str
    model: str | None
    serial: str | None
    characteristics: str | None
    interval_text: str | None
    interval_months: int | None
    last_cal_text: str | None
    last_cal_year: int | None
    last_cal_month: int | None
    last_cal_place: str | None
    usage_text: str | None
    usage_refs: list[tuple[str, str]] = field(default_factory=list)
    inherited: list[str] = field(default_factory=list)
    quote: str = ""


@dataclass
class InspectorDraft:
    """Một kiểm định viên (Biểu 7)."""

    ord: int | None
    name: str
    birth_year: int | None
    rank: str | None
    position: str | None
    education: str | None
    specialization: str | None
    fields: list[str] = field(default_factory=list)
    card_no: str | None = None
    card_date: date | None = None
    quote: str = ""


@dataclass
class ProcedureCatalogDraft:
    """Một dòng danh mục tiêu chuẩn, quy trình áp dụng (Biểu 4)."""

    ord: int | None
    domain: str | None
    group_code: str | None
    group_title: str | None
    code_text: str
    codes: list[ProcedureCode]
    title: str
    issuer: str | None
    year_issued: int | None
    inherited: list[str] = field(default_factory=list)
    quote: str = ""

    @property
    def procedure_number(self) -> str | None:
        return next((code.procedure_number for code in self.codes if code.procedure_number), None)


@dataclass
class CapabilityDraft:
    """Một lĩnh vực kiểm định/hiệu chuẩn được công nhận (Biểu 1)."""

    ord: int | None
    group_code: str | None
    group_title: str | None
    name: str
    parameters: list[str]
    procedure_codes: list[ProcedureCode]
    inspector_count: int | None
    recognition: str | None  # "bo_sung_moi" | "mo_rong" | "duy_tri"
    quote: str = ""


CatalogItem = LabStandardDraft | InspectorDraft | ProcedureCatalogDraft | CapabilityDraft


@dataclass
class CatalogDraft:
    """Kết quả đọc một hồ sơ danh mục."""

    kind: str  # "lab_standard" | "inspector" | "procedure_catalog" | "capability"
    title: str | None
    items: list[CatalogItem]
    source_text: str
    warnings: list[str] = field(default_factory=list)
