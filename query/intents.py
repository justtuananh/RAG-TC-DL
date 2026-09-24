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
)

# Mô tả intent + tham số cho prompt phân loại. Giữ ngắn gọn, đúng khoá JSON.
INTENT_CATALOG: dict[str, dict[str, Any]] = {
    "device_history": {
        "mo_ta": "Dòng thời gian các lần kiểm định của MỘT thiết bị theo số hiệu.",
        "params": {"serial": "số hiệu thiết bị (chuỗi)"},
    },
    "latest_record": {
        "mo_ta": "Lần kiểm định GẦN NHẤT của một thiết bị, kèm kết luận.",
        "params": {"serial": "số hiệu thiết bị (chuỗi)"},
    },
    "records_by_period": {
        "mo_ta": "Danh sách hồ sơ kiểm định trong một khoảng thời gian.",
        "params": {
            "date_from": "từ ngày (YYYY-MM-DD hoặc DD/MM/YYYY, có thể bỏ trống)",
            "date_to": "đến ngày (YYYY-MM-DD hoặc DD/MM/YYYY, có thể bỏ trống)",
            "verdict": "kết luận: 'dat' hoặc 'khong_dat' (có thể bỏ trống)",
        },
    },
    "procedure_params": {
        "mo_ta": "Bộ thông số tham chiếu đã duyệt của một QTKĐ (phạm vi, cấp chính xác, chu kỳ…).",
        "params": {
            "procedure_number": "số QTKĐ, ví dụ '1.061' (có thể bỏ trống nếu có device_type)",
            "device_type": "tên loại thiết bị, ví dụ 'van an toàn' (có thể bỏ trống nếu có số QTKĐ)",
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
        "params": {"procedure_number": "số QTKĐ, ví dụ '1.061'"},
    },
    "error_trend": {
        "mo_ta": "Diễn biến sai số của một thiết bị qua các lần kiểm định.",
        "params": {
            "serial": "số hiệu thiết bị (chuỗi)",
            "step_code": "mã mục đo, ví dụ '6.3.1' (có thể bỏ trống)",
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
    | ErrorTrendRequest,
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


def extract_json(raw: Any) -> dict[str, Any] | None:
    """Bóc JSON khỏi câu trả lời LLM (chấp nhận bọc ```json …```)."""
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
    end = text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
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

# Tín hiệu thô buộc phải gọi LLM phân loại. Không có tín hiệu nào → chắc chắn là
# câu hỏi văn bản, bỏ qua LLM (giữ nguyên trải nghiệm RAG văn bản, không thêm độ
# trễ). Cổng này CHỈ bao giờ trả về ``text`` nên không thể định tuyến nhầm sang
# nhánh số liệu. Cố ý KHÔNG khớp các từ chung như "kiểm định"/"thiết bị" — câu hỏi
# quy định (sai số, điều kiện, công thức) vẫn đi thẳng pipeline văn bản.
_DATA_SIGNAL_RE = re.compile(
    r"(số hiệu|so hieu|serial|\bsn[\s\-_]?\w|hồ sơ|ho so|"
    r"lịch sử|lich su|gần nhất|gan nhat|"
    r"từ ngày|tu ngay|đến ngày|den ngay|trong năm|khoảng thời gian|khoang thoi gian|"
    r"phạm vi đo|pham vi do|diễn biến sai số|dien bien sai so|"
    r"phương tiện kiểm định|phuong tien kiem dinh|bảng 2|bang 2|"
    r"bao nhiêu hồ sơ|bao nhieu ho so|đại lượng|dai luong|"
    r"\b\d\.\d{3}\b)",
    re.IGNORECASE,
)


def looks_like_data_question(question: str) -> bool:
    """True nếu câu hỏi có tín hiệu số liệu đáng để gọi LLM phân loại."""
    return bool(_DATA_SIGNAL_RE.search(question or ""))


class IntentClassifier(Protocol):
    """Giao diện bộ phân loại: trả dict/JSON hoặc None (không phân loại được)."""

    def classify(self, question: str) -> dict[str, Any] | str | None: ...


SYSTEM_PROMPT = (
    "Bạn là bộ định tuyến câu hỏi cho trợ lý kiểm định đo lường Việt Nam. "
    "Nhiệm vụ DUY NHẤT: chọn intent và điền tham số. Chỉ trả về JSON hợp lệ, "
    "không giải thích, không viết SQL. Nếu không chắc chắn, trả branch \"text\"."
)


def build_classifier_prompt(question: str) -> str:
    catalog_lines = []
    for name, info in INTENT_CATALOG.items():
        params = ", ".join(f'"{k}": {v}' for k, v in info["params"].items())
        catalog_lines.append(f'- "{name}": {info["mo_ta"]} params: {{{params}}}')
    catalog = "\n".join(catalog_lines)
    return (
        "Danh mục intent:\n"
        f"{catalog}\n\n"
        "Quy tắc:\n"
        '1. Chỉ chọn MỘT intent trong danh mục, hoặc branch "text" nếu câu hỏi là\n'
        "   tra cứu quy định/công thức/khái niệm (không phải số liệu hồ sơ).\n"
        '2. branch = "data" nếu chỉ cần số liệu hồ sơ; "mixed" nếu cần CẢ quy định\n'
        "   trong QTKĐ LẪN số liệu hồ sơ.\n"
        '3. Chỉ điền tham số có trong câu hỏi; KHÔNG bịa. Ví dụ "1.061" là\n'
        '   procedure_number; số hiệu thiết bị là serial.\n'
        "4. Ngày theo YYYY-MM-DD. Không chắc → trả {\"branch\": \"text\"}.\n\n"
        "Định dạng JSON:\n"
        '{"branch": "data", "intent": "device_history", "params": {"serial": "SN-1"}, '
        '"confidence": 0.9}\n\n'
        f"Câu hỏi: {question}"
    )


@dataclass(frozen=True)
class OllamaIntentConfig:
    url: str = DEFAULT_OLLAMA_URL
    model: str = DEFAULT_MODEL
    timeout: int = 60
    num_ctx: int = 4096
    temperature: float = 0.0
    keep_alive: str = "10m"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> OllamaIntentConfig:
        source = os.environ if env is None else env
        return cls(
            url=source.get("INTENT_OLLAMA_URL") or source.get("OLLAMA_URL") or DEFAULT_OLLAMA_URL,
            model=source.get("INTENT_LLM_MODEL") or source.get("OLLAMA_MODEL") or DEFAULT_MODEL,
            timeout=int(source.get("INTENT_LLM_TIMEOUT", "60")),
            num_ctx=int(source.get("INTENT_LLM_NUM_CTX", "4096")),
            temperature=float(source.get("INTENT_LLM_TEMPERATURE", "0.0")),
        )


def _native_chat_url(url: str) -> str:
    return url.replace("/v1/chat/completions", "/api/chat")


class OllamaIntentClassifier:
    """Bộ phân loại gọi Ollama nội bộ; thất bại an toàn (trả None → nhánh text)."""

    def __init__(self, config: OllamaIntentConfig | None = None) -> None:
        self.config = config or OllamaIntentConfig.from_env()

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> OllamaIntentClassifier:
        return cls(OllamaIntentConfig.from_env(env))

    def classify(self, question: str) -> dict[str, Any] | str | None:
        if not looks_like_data_question(question):
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
        return content if isinstance(content, str) and content.strip() else None


def default_classifier() -> IntentClassifier:
    """Bộ phân loại mặc định (điểm chèn cho test/CLI)."""
    return OllamaIntentClassifier.from_env()


def intents_enabled(env: dict[str, str] | None = None) -> bool:
    """Bật/tắt nhánh số liệu qua ``INTENT_ROUTER_ENABLED`` (mặc định bật)."""
    source = os.environ if env is None else env
    return source.get("INTENT_ROUTER_ENABLED", "true").strip().lower() in _TRUTHY
