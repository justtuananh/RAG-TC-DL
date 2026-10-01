"""Schema tham số cho hai intent tra cứu biên bản có cấu trúc (Pha R).

- ``record_lookup``: một (vài) biên bản cụ thể theo số hiệu / số biên bản / ngày /
  ký hiệu, trả các trường được hỏi (phạm vi đo, A0, uCmax...) hoặc cả phiếu.
- ``records_summary``: đếm / liệt kê / cực trị trên sổ cái đã duyệt, lọc theo người
  thực hiện, đơn vị sử dụng, kết luận, đơn vị phạm vi đo, khoảng ngày.

LLM chỉ điền JSON; tham số qua pydantic rồi tới truy vấn tham số hóa ở
``query/record_query.py`` (chỉ view đã duyệt, P3). Không có text-to-SQL. Tên trường
(``fields``/``field``) là khóa của danh mục trường, không bao giờ nối vào SQL.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Measure = Literal["list", "count", "min", "max"]
_KEY_MAX = 128


def _parse_date(value: Any) -> Any:
    from query.intents import parse_date

    return parse_date(value)


def _keys(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        value = value.replace(";", ",").split(",")
    return [str(item).strip()[:_KEY_MAX] for item in value if str(item).strip()]


_PROCEDURE_NUMBER_RE = re.compile(r"(?<![\d/])\d\.\d{3}(?![\d/])")


class RecordLookupParams(BaseModel):
    """Biên bản cụ thể: cần số hiệu, số biên bản, hoặc ký hiệu kèm ngày."""

    serial: str | None = Field(default=None, max_length=128)
    cert_no: str | None = Field(default=None, max_length=64)
    calibrated_on: dt.date | None = None
    model_code: str | None = Field(default=None, max_length=64)
    fields: list[str] = Field(default_factory=list, max_length=24)
    steps: list[str] = Field(default_factory=list, max_length=12)
    # Điểm đo được hỏi ("tại điểm đo 2 500 kG/cm²"): lọc dòng bảng theo giá trị danh nghĩa.
    nominal: float | None = None
    # Từ của câu hỏi: cột bảng mà câu hỏi nhắc tới ("áp suất khí quyển") được đưa lên
    # đầu bảng thay vì nằm khuất bên phải. Chỉ dùng để SẮP cột, không lọc dữ liệu.
    focus_words: list[str] = Field(default_factory=list, max_length=80)
    # "các biên bản có bao nhiêu điểm": đếm dòng bảng được hỏi trên MỌI biên bản cùng QTKĐ.
    across_records: bool = False

    @field_validator("calibrated_on", mode="before")
    @classmethod
    def _date(cls, value: Any) -> Any:
        return _parse_date(value)

    @field_validator("fields", "steps", "focus_words", mode="before")
    @classmethod
    def _list(cls, value: Any) -> list[str]:
        return _keys(value)

    @field_validator("cert_no")
    @classmethod
    def _not_a_procedure(cls, value: str | None) -> str | None:
        # Model nhỏ hay điền số QTKĐ ("1.159") vào ô số biên bản; đó là câu hỏi quy định.
        if value and _PROCEDURE_NUMBER_RE.search(value):
            raise ValueError("Số QTKĐ không phải số biên bản.")
        return value

    @model_validator(mode="after")
    def _require_selector(self) -> RecordLookupParams:
        if not (self.serial or self.cert_no or (self.model_code and self.calibrated_on)):
            raise ValueError("Cần số hiệu, số biên bản, hoặc ký hiệu kèm ngày kiểm định.")
        return self


class RecordsSummaryParams(BaseModel):
    """Tổng hợp sổ cái: mọi bộ lọc đều tùy chọn (không lọc = toàn bộ hồ sơ)."""

    serial: str | None = Field(default=None, max_length=128)
    model_code: str | None = Field(default=None, max_length=64)
    inspector: str | None = Field(default=None, max_length=255)
    reviewer: str | None = Field(default=None, max_length=255)
    owner_org: str | None = Field(default=None, max_length=255)
    verdict: Literal["dat", "khong_dat"] | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    range_unit: str | None = Field(default=None, max_length=32)
    measure: Measure = "list"
    field: str | None = Field(default=None, max_length=_KEY_MAX)
    # QTKĐ sở hữu bảng được so (lớp định tuyến điền từ danh mục, không từ LLM): mã bảng
    # như "A.2" lặp lại giữa các QTKĐ với nghĩa khác.
    procedure_ids: list[int] = Field(default_factory=list, max_length=50)
    # Câu hỏi đếm/liệt kê THIẾT BỊ ("có bao nhiêu áp kế ...") hay biên bản; lớp định tuyến
    # điền từ câu hỏi.
    subject: Literal["records", "devices"] = "records"
    # Trường câu hỏi hỏi kèm ("đơn vị sử dụng của các áp kế …"): nêu trong câu trả lời và
    # thêm cột vào bảng. Khóa của danh mục trường, không bao giờ nối vào SQL.
    fields: list[str] = Field(default_factory=list, max_length=24)

    @field_validator("fields", mode="before")
    @classmethod
    def _field_keys(cls, value: Any) -> list[str]:
        return _keys(value)

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def _dates(cls, value: Any) -> Any:
        return _parse_date(value)

    @model_validator(mode="after")
    def _check(self) -> RecordsSummaryParams:
        if self.measure in ("min", "max") and not self.field:
            raise ValueError("Cực trị cần tên trường so sánh.")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("'từ ngày' phải trước hoặc bằng 'đến ngày'.")
        return self


class RecordLookupRequest(BaseModel):
    intent: Literal["record_lookup"] = "record_lookup"
    params: RecordLookupParams


class RecordsSummaryRequest(BaseModel):
    intent: Literal["records_summary"] = "records_summary"
    params: RecordsSummaryParams


RECORD_INTENT_NAMES: tuple[str, ...] = ("record_lookup", "records_summary")

RECORD_PARAM_MODELS: dict[str, type[BaseModel]] = {
    "record_lookup": RecordLookupParams,
    "records_summary": RecordsSummaryParams,
}

RECORD_REQUESTS: tuple[type[BaseModel], ...] = (RecordLookupRequest, RecordsSummaryRequest)

# Khóa tham số tiếng Việt / gần đúng mà model nhỏ hay trả.
RECORD_PARAM_ALIASES: dict[str, str] = {
    "so_bien_ban": "cert_no",
    "số_biên_bản": "cert_no",
    "bien_ban": "cert_no",
    "certificate": "cert_no",
    "date": "calibrated_on",
    "ngay": "calibrated_on",
    "ngày": "calibrated_on",
    "ngay_kiem_dinh": "calibrated_on",
    "calibrated_at": "calibrated_on",
    "model": "model_code",
    "kiem_dinh_vien": "inspector",
    "kiểm_định_viên": "inspector",
    "inspector_name": "inspector",
    "nguoi_kiem_soat": "reviewer",
    "người_kiểm_soát": "reviewer",
    "reviewer_name": "reviewer",
    "don_vi_su_dung": "owner_org",
    "owner": "owner_org",
    "phep_toan": "measure",
    "aggregate": "measure",
    "truong": "field",
    "trường": "field",
}
