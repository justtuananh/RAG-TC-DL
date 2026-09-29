"""Danh mục intent tra cứu số liệu + schema tham số pydantic (spec §8).

LLM chỉ làm đúng MỘT việc: chọn intent và điền tham số dưới dạng JSON. Mọi tham
số phải qua pydantic trước khi tới câu SQL do người viết; **không có text-to-SQL
tự do**. Mỗi intent ứng với đúng một truy vấn tham số hóa ở ``query.records`` /
``query.approved`` (chỉ đọc view đã duyệt, P3).

Bất biến:
- P1: tham số chỉ là bộ lọc/định danh; kết quả vẫn kèm tham chiếu xuất xứ.
- P2: không có phép tính nào trên số liệu nguồn ở đây.
- P3: tham số không bao giờ được nối vào SQL — tầng thực thi bind tham số.

Khi không chắc chắn (LLM không sẵn sàng, JSON hỏng, intent/ tham số không hợp lệ)
hệ thống rơi về nhánh ``text``: trả lời thiếu số liệu nhưng đúng nguồn tốt hơn
trả lời số liệu sai nhánh.
"""

from __future__ import annotations

import calendar
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Any, Literal, Protocol

from pydantic import (
    BaseModel,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from query.catalog_intents import (
    CATALOG_INTENT_NAMES,
    CATALOG_PARAM_ALIASES,
    CATALOG_PARAM_MODELS,
    CATALOG_REQUESTS,
)
from query.intent_prompt import (
    SYSTEM_PROMPT,
    render_classifier_prompt,
)
from query.record_intents import (
    RECORD_INTENT_NAMES,
    RECORD_PARAM_ALIASES,
    RECORD_PARAM_MODELS,
    RECORD_REQUESTS,
)
from query.record_signals import disambiguate_records
from query.signals import disambiguate_catalogs, looks_like_data_question

logger = logging.getLogger(__name__)

# ── Danh mục intent (spec §8) ─────────────────────────────────────────────────

IntentName = Literal[
    "device_history",
    "latest_record",
    "records_by_period",
    "procedure_params",
    "devices_by_range",
    "standards_for",
    "error_trend",
    "lab_standard_lookup",
    "inspector_lookup",
    "procedure_catalog_lookup",
    "capability_lookup",
    "record_lookup",
    "records_summary",
]

Branch = Literal["text", "data", "mixed"]
Verdict = Literal["dat", "khong_dat"]

INTENT_NAMES: tuple[str, ...] = (
    "device_history",
    "latest_record",
    "records_by_period",
    "procedure_params",
    "devices_by_range",
    "standards_for",
    "error_trend",
    *CATALOG_INTENT_NAMES,
    *RECORD_INTENT_NAMES,
)

# Mô tả intent + tham số cho prompt phân loại. Giữ ngắn gọn, đúng khoá JSON.
INTENT_CATALOG: dict[str, dict[str, Any]] = {
    "device_history": {
        "mo_ta": "Dòng thời gian các lần kiểm định của MỘT thiết bị theo số hiệu.",
        "params": {"serial": "số hiệu thiết bị (chuỗi)"},
    },
    "latest_record": {
        "mo_ta": "Kết quả kiểm mới nhất của một thiết bị, kèm kết luận.",
        "params": {"serial": "số hiệu thiết bị (chuỗi)"},
    },
    "records_by_period": {
        "mo_ta": (
            "Danh sách HOẶC đếm số hồ sơ kiểm định trong một khoảng thời gian, "
            "có thể lọc đạt/không đạt."
        ),
        "params": {
            "date_from": "từ ngày (YYYY-MM-DD hoặc DD/MM/YYYY, có thể bỏ trống)",
            "date_to": "đến ngày (YYYY-MM-DD hoặc DD/MM/YYYY, có thể bỏ trống)",
            "verdict": "kết luận: 'dat' hoặc 'khong_dat' (có thể bỏ trống)",
        },
    },
    "procedure_params": {
        "mo_ta": (
            "Bộ thông số tham chiếu đã duyệt của một QTKĐ: phạm vi đo, cấp chính xác, "
            "chu kỳ. Dùng khi hỏi 'thông số', 'phạm vi đo', 'cấp chính xác', 'chu kỳ'."
        ),
        "params": {
            "procedure_number": "số QTKĐ (có thể bỏ trống nếu có device_type)",
            "device_type": "tên loại thiết bị (có thể bỏ trống nếu có số QTKĐ)",
        },
    },
    "devices_by_range": {
        "mo_ta": "Thiết bị có phạm vi đo nằm trong một khoảng.",
        "params": {
            "quantity": "đại lượng đo, ví dụ 'áp suất'",
            "min_value": "giá trị nhỏ nhất (số)",
            "max_value": "giá trị lớn nhất (số)",
            "unit": "đơn vị, ví dụ 'bar' (có thể bỏ trống)",
        },
    },
    "standards_for": {
        "mo_ta": "Bảng 2 phương tiện kiểm định của một QTKĐ.",
        "params": {"procedure_number": "số QTKĐ"},
    },
    "error_trend": {
        "mo_ta": "Diễn biến/xu hướng sai số của một thiết bị qua các lần kiểm định.",
        "params": {
            "serial": "số hiệu thiết bị (chuỗi)",
            "step_code": "mã mục đo, ví dụ '6.3.1' (có thể bỏ trống)",
        },
    },
    "lab_standard_lookup": {
        "mo_ta": (
            "Danh mục chuẩn mẫu/PTĐ/PTTN: tên, ký hiệu (model), số hiệu, đặc tính đo lường, "
            "chu kỳ KĐ/HC, lần KĐ/HC gần nhất và nơi thực hiện, hạn kế tiếp ước tính. "
            "Dùng khi câu hỏi nhắc tới CHUẨN (chuẩn mẫu, PTĐ, PTTN), kể cả khi chỉ nêu KÝ "
            "HIỆU/MODEL (có thể nhiều từ, ví dụ 'Fluke 5624-20-B', 'Thunder 1200', 'TESON II') "
            "mà không nói 'chuẩn'; KHÔNG phải thiết bị cần kiểm."
        ),
        "params": {
            "query": "tên/ký hiệu/số hiệu chuẩn mẫu (có thể bỏ trống nếu có usage_ref)",
            "usage_ref": "mục sử dụng, ví dụ 'IV.1' (có thể bỏ trống nếu có query)",
        },
    },
    "inspector_lookup": {
        "mo_ta": (
            "Danh sách kiểm định viên: họ tên, cấp bậc/chức vụ, trình độ, chuyên ngành, "
            "lĩnh vực được chứng nhận, số thẻ. Dùng khi hỏi kiểm định viên/KĐV, 'ai được', "
            "'ai có thể', 'kiểm định viên nào' kiểm định/hiệu chuẩn một loại thiết bị hay "
            "đại lượng (điền loại thiết bị/đại lượng vào field), hoặc hỏi số thẻ."
        ),
        "params": {
            "name": "họ tên kiểm định viên (có thể bỏ trống)",
            "field": "loại thiết bị/đại lượng được chứng nhận, ví dụ 'nhiệt độ' (có thể bỏ trống)",
        },
    },
    "procedure_catalog_lookup": {
        "mo_ta": (
            "Danh mục tiêu chuẩn, quy trình áp dụng (Biểu 4): nhóm lĩnh vực, số hiệu, tên quy "
            "trình, cấp ban hành, năm ban hành. Dùng khi hỏi MỘT quy trình/tiêu chuẩn 'là gì', "
            "mã quy trình X 'là gì', cấp nào ban hành, hoặc liệt kê quy trình theo nhóm lĩnh "
            "vực/tên thiết bị ('danh mục quy trình nhóm Y'). KHÔNG dùng cho câu hỏi về lĩnh "
            "vực được công nhận của phòng (dải đo, số KĐV)."
        ),
        "params": {
            "code": "số hiệu quy trình, ví dụ 'QTKĐ 1.019:2014' (có thể bỏ trống)",
            "keyword": "tên thiết bị, ví dụ 'nhiệt kế thủy tinh' (có thể bỏ trống)",
            "group": "nhóm lĩnh vực, ví dụ 'dung tích, lưu lượng' (có thể bỏ trống)",
        },
    },
    "record_lookup": {
        "mo_ta": (
            "MỘT biên bản kiểm định cụ thể trong sổ cái, xác định bằng số biên bản (dạng "
            "011/2024) hoặc số hiệu thiết bị kèm ngày kiểm định: các trường ghi trên biên "
            "bản (A0, uCmax, U(p), điều kiện môi trường, kết luận) và bảng kết quả."
        ),
        "params": {
            "serial": "số hiệu thiết bị (có thể bỏ trống nếu có cert_no)",
            "cert_no": "số biên bản, ví dụ '011/2024' (có thể bỏ trống)",
            "calibrated_on": "ngày kiểm định YYYY-MM-DD (có thể bỏ trống)",
        },
    },
    "records_summary": {
        "mo_ta": (
            "Tổng hợp TOÀN BỘ sổ cái biên bản: đếm/liệt kê biên bản, số thiết bị, biên bản "
            "không đạt; lọc theo kiểm định viên, người kiểm soát, đơn vị sử dụng, đơn vị của "
            "phạm vi đo; biên bản có giá trị nhỏ nhất/lớn nhất."
        ),
        "params": {
            "inspector": "họ tên kiểm định viên (có thể bỏ trống)",
            "reviewer": "họ tên người kiểm soát (có thể bỏ trống)",
            "owner_org": "tên đơn vị sử dụng, nguyên văn (có thể bỏ trống)",
            "range_unit": "đơn vị phạm vi đo, ví dụ 'bar' (có thể bỏ trống)",
            "measure": "'list', 'count', 'min' hoặc 'max'",
        },
    },
    "capability_lookup": {
        "mo_ta": (
            "Lĩnh vực KĐ/HC được công nhận (Biểu 1): tên đại lượng/trang bị, dải đo/cấp chính "
            "xác, quy trình áp dụng, số kiểm định viên, hình thức công nhận. Dùng khi hỏi PHÒNG "
            "hoặc 'lĩnh vực <thiết bị>' được công nhận kiểm định/hiệu chuẩn ra sao, áp dụng "
            "quy trình nào, dải đo/CCX nào, mấy KĐV. KHÔNG dùng cho câu hỏi 'quy trình <thiết "
            "bị> là gì' hay 'mã quy trình X là gì' (đó là procedure_catalog_lookup)."
        ),
        "params": {
            "keyword": "tên đại lượng/trang bị, ví dụ 'van an toàn'",
        },
    },
}


# ── Tiện ích phân tích tham số ────────────────────────────────────────────────


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


_DATE_RE = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$")


def parse_date(value: Any) -> date | None:
    """Nhận ISO hoặc DD/MM/YYYY (người Việt hay viết); None nếu rỗng."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    match = _DATE_RE.match(text)
    if match:
        day, month, year = (int(part) for part in match.groups())
        try:
            return date(year, month, day)
        except ValueError as exc:
            raise ValueError(f"Ngày không hợp lệ: {value!r}") from exc
    try:
        return datetime.fromisoformat(text).date()
    except ValueError as exc:
        raise ValueError(f"Ngày không hợp lệ: {value!r}") from exc


_VERDICT_ALIASES: dict[str, str] = {
    "dat": "dat",
    "đạt": "dat",
    "khong_dat": "khong_dat",
    "khong dat": "khong_dat",
    "không đạt": "khong_dat",
    "khongdat": "khong_dat",
}


def normalize_verdict(value: Any) -> Any:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    return _VERDICT_ALIASES.get(text, text)


# Từ đồng nghĩa khoá tham số (LLM có thể trả tiếng Việt hoặc snake_case khác).
_PARAM_KEY_ALIASES: dict[str, str] = {
    "so_hieu": "serial",
    "số_hiệu": "serial",
    "serial_no": "serial",
    "thiet_bi": "serial",
    "device": "serial",
    "tu_ngay": "date_from",
    "từ_ngày": "date_from",
    "from_date": "date_from",
    "start_date": "date_from",
    "den_ngay": "date_to",
    "đến_ngày": "date_to",
    "to_date": "date_to",
    "end_date": "date_to",
    "ket_luan": "verdict",
    "kết_luận": "verdict",
    "so_qtkd": "procedure_number",
    "số_qtkd": "procedure_number",
    "qtkd": "procedure_number",
    "procedure": "procedure_number",
    "procedure_no": "procedure_number",
    "loai_thiet_bi": "device_type",
    "loại_thiết_bị": "device_type",
    "device_type_name": "device_type",
    "dai_luong": "quantity",
    "đại_lượng": "quantity",
    "quantity_name": "quantity",
    "min": "min_value",
    "max": "max_value",
    "min_value": "min_value",
    "max_value": "max_value",
    "don_vi": "unit",
    "đơn_vị": "unit",
    "unit_code": "unit",
    "ma_muc": "step_code",
    "mã_mục": "step_code",
    "step": "step_code",
    "buoc": "step_code",
}

# Gộp từ đồng nghĩa riêng của bốn intent danh mục (không trùng khoá trên).
_PARAM_KEY_ALIASES.update(CATALOG_PARAM_ALIASES)
_PARAM_KEY_ALIASES.update(RECORD_PARAM_ALIASES)


def normalize_param_keys(params: dict[str, Any] | None) -> dict[str, Any]:
    """Đưa khoá tham số về tên chuẩn; bỏ khoá rỗng."""
    if not params:
        return {}
    result: dict[str, Any] = {}
    for key, value in params.items():
        canonical = _PARAM_KEY_ALIASES.get(str(key).strip().lower(), str(key).strip())
        value = _clean(value)
        if value is None or value == "":
            continue
        if canonical == "verdict":
            value = normalize_verdict(value)
        result[canonical] = value
    return result


# ── Chuẩn hoá tham số tất định sau LLM ────────────────────────────────────────
# Đây là kiểm tra/chuẩn hoá THAM SỐ, không phải luật chọn nhánh: chỉ loại giá trị
# không có căn cứ trong câu hỏi (chống LLM bịa số hiệu) và suy verdict từ chính câu
# hỏi. Nhánh vẫn do LLM chọn; tham số không hợp lệ vẫn rơi về ``text`` như cũ.

_VERDICT_NEG_RE = re.compile(r"kh[oô]ng\s*đạt|khong[_\s]?dat", re.IGNORECASE)
_VERDICT_POS_RE = re.compile(r"\bđạt\b|\bdat\b", re.IGNORECASE)


def _appears_in(value: Any, question: str) -> bool:
    """True nếu ``value`` xuất hiện nguyên văn (bỏ hoa/thường) trong câu hỏi."""
    needle = str(value).strip().casefold()
    return bool(needle) and needle in (question or "").casefold()


_IDENTIFIER_PREFIX_RE = re.compile(
    r"^\s*(?:áp\s*kế|thiết\s*bị|máy|phương\s*tiện|số\s*hiệu|qtkđ|qtkd|quy\s*trình|procedure)"
    r"\s*[:#.\-]?\s*",
    re.IGNORECASE | re.UNICODE,
)
_LETTER_PREFIX_RE = re.compile(r"^\s*[^\W\d_]{1,6}\s*[-:#.]\s*", re.UNICODE)


def _clean_identifier(value: str) -> str:
    """Bỏ tiền tố từ chỉ thiết bị/quy trình hoặc tiền tố chữ La-tinh một ký tự.

    Ví dụ: "Máy 58-3312" -> "58-3312", "Quy trình 3.204" -> "3.204",
    "AP-0391" -> "0391". Giữ nguyên "SN-1" (tiền tố một ký tự, còn lại quá ngắn).
    """
    text = value.strip()
    cleaned = _IDENTIFIER_PREFIX_RE.sub("", text).strip()
    if cleaned and cleaned != text:
        return cleaned
    match = _LETTER_PREFIX_RE.match(text)
    if match:
        remainder = text[match.end() :].strip()
        if len(remainder) >= 2 and any(char.isdigit() for char in remainder):
            return remainder
    return text


def ground_params(params: dict[str, Any] | None, question: str) -> dict[str, Any]:
    """Loại tham số định danh không xuất hiện trong câu hỏi; suy verdict từ câu hỏi.

    Số hiệu thiết bị và số QTKĐ là định danh: nếu LLM trả một giá trị không hề có
    trong câu hỏi (thường do sao chép ví dụ), bỏ đi để tham số không hợp lệ và hệ
    thống rơi an toàn về ``text``. Nếu giá trị chỉ bị thêm tiền tố từ ngữ (ví dụ
    "Máy 58-3312", "AP-0391"), cắt tiền tố rồi đối chiếu lại câu hỏi. Verdict bịa
    cũng bị bỏ khi câu hỏi không nói đạt/không đạt.
    """
    if not params:
        return {}
    result = dict(params)
    for key in ("serial", "procedure_number"):
        value = result.get(key)
        if value is None:
            continue
        cleaned = _clean_identifier(str(value))
        if _appears_in(cleaned, question):
            result[key] = cleaned
        else:
            result.pop(key, None)
    if result.get("verdict") is not None:
        if _VERDICT_NEG_RE.search(question or ""):
            result["verdict"] = "khong_dat"
        elif _VERDICT_POS_RE.search(question or ""):
            result["verdict"] = "dat"
        else:
            result.pop("verdict", None)
    return result


_RANGE_DMY_RE = re.compile(
    r"từ\s+(?:ngày\s+)?(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4})\s+đến\s+"
    r"(?:ngày\s+)?(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4})",
    re.IGNORECASE,
)
_RANGE_YEAR_RE = re.compile(r"từ\s+(?:năm\s+)?(\d{4})\s+đến\s+(?:năm\s+)?(\d{4})", re.IGNORECASE)
_MONTH_RE = re.compile(r"tháng\s+(\d{1,2})\s*(?:[/\-]\s*|năm\s+)(\d{4})", re.IGNORECASE)
_YEAR_RE = re.compile(r"năm\s+(\d{4})", re.IGNORECASE)


def extract_date_range(question: str) -> dict[str, str]:
    """Suy khoảng ngày từ chính câu hỏi; rỗng nếu không nhận ra mẫu rõ ràng.

    Giữ ĐÚNG thứ tự 'từ ... đến ...' của câu hỏi (không tự đảo), để khoảng đảo
    ngược vẫn bị pydantic từ chối như mong đợi. Đây là chuẩn hoá tham số, không đổi
    nhãn intent/nhánh.
    """
    text = question or ""
    match = _RANGE_DMY_RE.search(text)
    if match:
        try:
            start, end = parse_date(match.group(1)), parse_date(match.group(2))
        except ValueError:
            start = end = None
        if start is not None and end is not None:
            return {"date_from": start.isoformat(), "date_to": end.isoformat()}
    match = _RANGE_YEAR_RE.search(text)
    if match:
        return {"date_from": f"{match.group(1)}-01-01", "date_to": f"{match.group(2)}-12-31"}
    match = _MONTH_RE.search(text)
    if match:
        month, year = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12:
            last_day = calendar.monthrange(year, month)[1]
            return {
                "date_from": f"{year:04d}-{month:02d}-01",
                "date_to": f"{year:04d}-{month:02d}-{last_day:02d}",
            }
    match = _YEAR_RE.search(text)
    if match:
        year = match.group(1)
        return {"date_from": f"{year}-01-01", "date_to": f"{year}-12-31"}
    return {}


_INTENT_ALIASES: dict[str, str] = {
    "lab_standard": "lab_standard_lookup",
    "standard_lookup": "lab_standard_lookup",
    "standards_lookup": "lab_standard_lookup",
    "inspector": "inspector_lookup",
    "inspectors_lookup": "inspector_lookup",
    "capability": "capability_lookup",
    "capabilities_lookup": "capability_lookup",
    "procedure_catalog": "procedure_catalog_lookup",
    "catalog_lookup": "procedure_catalog_lookup",
}


_STANDARDS_CUE_RE = re.compile(r"phương\s+tiện\s+kiểm\s+định|bảng\s+2\b", re.IGNORECASE)


def _resolve_intent_alias(intent: str, params: dict[str, Any], question: str) -> str:
    """Đưa tên intent gần đúng của model nhỏ về tên chuẩn; giữ nguyên nếu lạ."""
    if intent == "procedure_lookup":
        # Có số QTKĐ thì là thông số QTKĐ, ngược lại là danh mục quy trình.
        return "procedure_params" if params.get("procedure_number") else "procedure_catalog_lookup"
    if intent in ("mixed", "data") and params.get("procedure_number"):
        # Model nhỏ đôi khi điền tên nhánh vào ô intent; số QTKĐ (đã grounding) cho biết
        # đây là tra QTKĐ, còn loại bảng suy theo quy tắc 8 của prompt.
        return "standards_for" if _STANDARDS_CUE_RE.search(question) else "procedure_params"
    return _INTENT_ALIASES.get(intent, intent)


def sanitize_classification(payload: dict[str, Any] | None, question: str) -> dict[str, Any] | None:
    """Chuẩn hoá payload LLM trước ``decide``: khoá chuẩn + tham số có căn cứ."""
    if not isinstance(payload, dict):
        return payload
    result = dict(payload)
    params = ground_params(normalize_param_keys(payload.get("params")), question)
    intent = str(result.get("intent") or "").strip().lower()
    intent = _resolve_intent_alias(intent, params, question)
    result["intent"] = intent
    if intent == "records_by_period":
        dates = extract_date_range(question)
        if dates:
            params.update(dates)
    result["params"] = params
    return result


# ── Schema tham số từng intent ────────────────────────────────────────────────


class DeviceHistoryParams(BaseModel):
    serial: str = Field(min_length=1, max_length=128)


class LatestRecordParams(BaseModel):
    serial: str = Field(min_length=1, max_length=128)


class RecordsByPeriodParams(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    verdict: Verdict | None = None

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def _parse_dates(cls, value: Any) -> Any:
        return parse_date(value)

    @model_validator(mode="after")
    def _require_order(self) -> RecordsByPeriodParams:
        if self.date_from is None and self.date_to is None:
            raise ValueError("Cần ít nhất một mốc thời gian (từ ngày hoặc đến ngày).")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("'từ ngày' phải trước hoặc bằng 'đến ngày'.")
        return self


class ProcedureParamsParams(BaseModel):
    procedure_number: str | None = Field(default=None, max_length=64)
    device_type: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _require_selector(self) -> ProcedureParamsParams:
        if not (self.procedure_number or self.device_type):
            raise ValueError("Cần số QTKĐ hoặc loại thiết bị.")
        return self


class DevicesByRangeParams(BaseModel):
    quantity: str = Field(min_length=1, max_length=255)
    min_value: float
    max_value: float
    unit: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def _require_order(self) -> DevicesByRangeParams:
        if self.min_value > self.max_value:
            raise ValueError("'min_value' phải nhỏ hơn hoặc bằng 'max_value'.")
        return self


class StandardsForParams(BaseModel):
    procedure_number: str = Field(min_length=1, max_length=64)


class ErrorTrendParams(BaseModel):
    serial: str = Field(min_length=1, max_length=128)
    step_code: str | None = Field(default=None, max_length=32)


class DeviceHistoryRequest(BaseModel):
    intent: Literal["device_history"] = "device_history"
    params: DeviceHistoryParams


class LatestRecordRequest(BaseModel):
    intent: Literal["latest_record"] = "latest_record"
    params: LatestRecordParams


class RecordsByPeriodRequest(BaseModel):
    intent: Literal["records_by_period"] = "records_by_period"
    params: RecordsByPeriodParams


class ProcedureParamsRequest(BaseModel):
    intent: Literal["procedure_params"] = "procedure_params"
    params: ProcedureParamsParams


class DevicesByRangeRequest(BaseModel):
    intent: Literal["devices_by_range"] = "devices_by_range"
    params: DevicesByRangeParams


class StandardsForRequest(BaseModel):
    intent: Literal["standards_for"] = "standards_for"
    params: StandardsForParams


class ErrorTrendRequest(BaseModel):
    intent: Literal["error_trend"] = "error_trend"
    params: ErrorTrendParams


IntentRequest = Annotated[
    DeviceHistoryRequest
    | LatestRecordRequest
    | RecordsByPeriodRequest
    | ProcedureParamsRequest
    | DevicesByRangeRequest
    | StandardsForRequest
    | ErrorTrendRequest
    | CATALOG_REQUESTS[0]
    | CATALOG_REQUESTS[1]
    | CATALOG_REQUESTS[2]
    | CATALOG_REQUESTS[3]
    | RECORD_REQUESTS[0]
    | RECORD_REQUESTS[1],
    Field(discriminator="intent"),
]

IntentRequestAdapter: TypeAdapter[IntentRequest] = TypeAdapter(IntentRequest)

PARAM_MODELS: dict[str, type[BaseModel]] = {
    "device_history": DeviceHistoryParams,
    "latest_record": LatestRecordParams,
    "records_by_period": RecordsByPeriodParams,
    "procedure_params": ProcedureParamsParams,
    "devices_by_range": DevicesByRangeParams,
    "standards_for": StandardsForParams,
    "error_trend": ErrorTrendParams,
    **CATALOG_PARAM_MODELS,
    **RECORD_PARAM_MODELS,
}


def parse_intent(payload: dict[str, Any] | None) -> IntentRequest | None:
    """Kiểm tra ``{"intent": ..., "params": {...}}``; None nếu sai schema."""
    if not isinstance(payload, dict):
        return None
    intent = payload.get("intent")
    if intent not in INTENT_NAMES:
        return None
    params = normalize_param_keys(payload.get("params"))
    try:
        return IntentRequestAdapter.validate_python({"intent": intent, "params": params})
    except ValidationError as exc:
        logger.debug("Tham số intent không hợp lệ (%s): %s", intent, exc)
        return None


# ── Kết quả phân loại + quyết định định tuyến ─────────────────────────────────


@dataclass(frozen=True)
class IntentDecision:
    """Quyết định định tuyến: nhánh + intent đã kiểm (nếu có) + lý do."""

    branch: Branch
    request: IntentRequest | None
    confidence: float
    reason: str


def text_decision(reason: str) -> IntentDecision:
    return IntentDecision(branch="text", request=None, confidence=0.0, reason=reason)


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_JSON_DECODER = json.JSONDecoder()


def extract_json(raw: Any) -> dict[str, Any] | None:
    """Bóc JSON khỏi câu trả lời LLM (chấp nhận bọc ```json …```).

    Nếu model nối liền nhiều object, chỉ lấy object hợp lệ ĐẦU TIÊN.
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    block = _JSON_BLOCK_RE.search(text)
    if block:
        text = block.group(1).strip()
    start = text.find("{")
    if start < 0:
        return None
    try:
        payload, _ = _JSON_DECODER.raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def decide(raw: Any, *, min_confidence: float = 0.0) -> IntentDecision:
    """Biến đầu ra LLM thành quyết định định tuyến; mặc định rơi về ``text``.

    ``raw`` có thể là dict, chuỗi JSON, hoặc None (LLM không sẵn sàng). Mọi bất
    định (JSON hỏng, intent lạ, tham số sai schema, độ tin cậy thấp) đều → text.
    """
    payload = extract_json(raw)
    if payload is None:
        return text_decision("classifier_unavailable" if raw is None else "invalid_json")

    branch = str(payload.get("branch") or "").strip().lower()
    intent = str(payload.get("intent") or "").strip().lower() or None
    confidence_raw = payload.get("confidence")
    try:
        confidence = float(confidence_raw) if confidence_raw is not None else 0.0
    except (TypeError, ValueError):
        confidence = 0.0

    if intent == "text" or intent == "":
        intent = None
    if branch not in ("text", "data", "mixed"):
        branch = "data" if intent else "text"
    if branch == "text" or intent is None:
        return text_decision("classifier_text")

    if confidence < min_confidence:
        return text_decision("low_confidence")

    request = parse_intent({"intent": intent, "params": payload.get("params")})
    if request is None:
        return text_decision("invalid_params")

    return IntentDecision(branch=branch, request=request, confidence=confidence, reason="ok")


# ── Bộ phân loại LLM (thất bại an toàn) ───────────────────────────────────────

DEFAULT_OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
DEFAULT_MODEL = "qwen2.5:1.5b"
_TRUTHY = {"1", "true", "yes", "on"}


class IntentClassifier(Protocol):
    """Giao diện bộ phân loại: trả dict/JSON hoặc None (không phân loại được)."""

    def classify(self, question: str) -> dict[str, Any] | str | None: ...


def build_classifier_prompt(question: str) -> str:
    return render_classifier_prompt(question, INTENT_CATALOG)


@dataclass(frozen=True)
class OllamaIntentConfig:
    url: str = DEFAULT_OLLAMA_URL
    model: str = DEFAULT_MODEL
    timeout: int = 60
    # Prompt phân loại (danh mục + quy tắc + ví dụ) đã ~4 000 token: 4096 cắt mất câu hỏi.
    # 8192 trùng ``generation.NUM_CTX`` nên Ollama không nạp lại model giữa hai lời gọi.
    num_ctx: int = 8192
    temperature: float = 0.0
    keep_alive: str = "10m"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> OllamaIntentConfig:
        source = os.environ if env is None else env
        return cls(
            url=source.get("INTENT_OLLAMA_URL") or source.get("OLLAMA_URL") or DEFAULT_OLLAMA_URL,
            model=source.get("INTENT_LLM_MODEL") or source.get("OLLAMA_MODEL") or DEFAULT_MODEL,
            timeout=int(source.get("INTENT_LLM_TIMEOUT", "60")),
            num_ctx=int(source.get("INTENT_LLM_NUM_CTX", "8192")),
            temperature=float(source.get("INTENT_LLM_TEMPERATURE", "0.0")),
        )


def _native_chat_url(url: str) -> str:
    return url.replace("/v1/chat/completions", "/api/chat")


def _open_default_session() -> Any | None:
    """Mở session CSDL mặc định để đối chiếu số hiệu sổ cái; None nếu không có."""
    try:
        from db import SessionLocal

        return SessionLocal()
    except Exception:  # noqa: BLE001 - thiếu DB thì bỏ qua tín hiệu sổ cái
        return None


class OllamaIntentClassifier:
    """Bộ phân loại gọi Ollama nội bộ; thất bại an toàn (trả None → nhánh text)."""

    def __init__(
        self,
        config: OllamaIntentConfig | None = None,
        session_factory: Any | None = None,
    ) -> None:
        self.config = config or OllamaIntentConfig.from_env()
        self.session_factory = session_factory or _open_default_session

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> OllamaIntentClassifier:
        return cls(OllamaIntentConfig.from_env(env))

    def classify(self, question: str) -> dict[str, Any] | str | None:
        session = None
        try:
            session = self.session_factory() if self.session_factory else None
        except Exception as exc:  # noqa: BLE001 - thiếu DB thì bỏ qua tín hiệu sổ cái
            logger.debug("Không mở được session cho tín hiệu sổ cái: %s", exc)
        try:
            if not looks_like_data_question(question, session=session):
                return {"branch": "text", "confidence": 1.0}
            import requests

            try:
                response = requests.post(
                    _native_chat_url(self.config.url),
                    json={
                        "model": self.config.model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": build_classifier_prompt(question)},
                        ],
                        "stream": False,
                        "keep_alive": self.config.keep_alive,
                        "options": {
                            "num_ctx": self.config.num_ctx,
                            "temperature": self.config.temperature,
                        },
                    },
                    timeout=self.config.timeout,
                )
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:  # noqa: BLE001 - thất bại an toàn có chủ đích
                logger.warning("Phân loại intent thất bại: %s", exc)
                return None
            content = (payload.get("message") or {}).get("content")
            if not (isinstance(content, str) and content.strip()):
                return None
            parsed = extract_json(content)
            if parsed is not None:
                sanitized = sanitize_classification(parsed, question)
                corrected = disambiguate_catalogs(sanitized, question, session)
                return disambiguate_records(corrected, question, session)
            return content
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception:  # noqa: BLE001 - đóng session lỗi không quan trọng
                    pass


def default_classifier() -> IntentClassifier:
    """Bộ phân loại mặc định (điểm chèn cho test/CLI)."""
    return OllamaIntentClassifier.from_env()


def intents_enabled(env: dict[str, str] | None = None) -> bool:
    """Bật/tắt nhánh số liệu qua ``INTENT_ROUTER_ENABLED`` (mặc định bật)."""
    source = os.environ if env is None else env
    return source.get("INTENT_ROUTER_ENABLED", "true").strip().lower() in _TRUTHY
