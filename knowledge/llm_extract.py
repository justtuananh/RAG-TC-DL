"""Trích xuất §6 Tiến hành kiểm định bằng LLM: schema + hàng rào chống bịa số.

Spec §7 (ràng buộc bộ trích xuất LLM ở §6) và §9 Sprint 5:

- đầu ra JSON theo schema pydantic; **mọi trường số bắt buộc đi kèm ``quote``**
  chứa nguyên văn con số đó;
- bộ xác minh từ chối dòng có ``quote`` không khớp nguyên văn trong mục, chuẩn
  hóa dấu cách (gồm NBSP U+00A0 và khoảng trắng hẹp không ngắt U+202F) trước khi so;
- chấm điểm tin cậy dựa trên: khớp nguyên văn, đơn vị nhận diện được, giá trị nằm
  trong khoảng hợp lý so với phạm vi đo của chính QTKĐ đó;
- gọi Ollama nội bộ qua HTTP, cấu hình bằng biến môi trường, **thất bại an toàn**
  (trả rỗng thay vì ném ra ngoài, để không chặn ingestion).

P1/P2: module chỉ ĐỌC nguyên văn và gắn xuất xứ; không bao giờ tính lại số liệu
nguồn. Quy đổi SI (nếu có) do ``knowledge.units`` làm lúc ghi, và chỉ khi đơn vị
được nhận diện chắc chắn.

Phần lõi (schema, xác minh, chấm điểm, dựng prompt) thuần hàm, không chạm DB và
không bắt buộc ``requests``; chỉ ``OllamaClient.chat`` mới gọi mạng.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from knowledge import units as units_module
from knowledge import vnnum
from knowledge.rules.sections import Section, find_section, split_sections

logger = logging.getLogger(__name__)

EXTRACTOR_VERSION = "v1"
SECTION_KEYWORD = "tiến hành"
# Tên loại dữ kiện §6 theo spec §5.4.
MAX_ERROR_KIND = "max_permissible_error"
FORMULA_KIND = "formula"

# ── Cấu hình Ollama (đọc tại thời điểm gọi để test đặt env được) ───────────────
DEFAULT_OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
DEFAULT_MODEL = "qwen2.5:7b"
_TRUTHY = {"1", "true", "yes", "on"}


# ── Schema pydantic: mọi số phải kèm quote ────────────────────────────────────


class NumericClaim(BaseModel):
    """Một con số trong §6. ``quote`` bắt buộc: nguyên văn chứa con số đó.

    Ràng buộc ở tầng kiểu dữ liệu: không thể dựng một ``NumericClaim`` mà thiếu
    ``quote`` — đó là hàng rào cấu trúc chống bịa số, độc lập với việc kiểm tra
    nội dung ở ``verify_fact``.
    """

    value: float
    unit: str | None = None
    quote: str = Field(min_length=1)


class Section6Fact(BaseModel):
    """Một dữ kiện §6 do LLM đề xuất, trước khi xác minh.

    ``fact_kind`` nhận ``max_permissible_error`` hoặc ``formula``. Dữ kiện sai
    số có ``limit`` (giới hạn chính) và tùy chọn ``floor`` (ràng buộc sàn, ví dụ
    "không nhỏ hơn ± 0,15 bar" trong spec §5.4).
    """

    fact_kind: Literal["max_permissible_error", "formula"]
    label: str | None = None
    rel_op: str | None = None
    value_text: str | None = None
    condition_text: str | None = None
    limit: NumericClaim | None = None
    floor: NumericClaim | None = None
    formula: str | None = None
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def _require_shape(self) -> Section6Fact:
        if self.fact_kind == MAX_ERROR_KIND:
            if self.limit is None:
                raise ValueError("max_permissible_error phải có 'limit' kèm quote")
        elif not (self.formula or "").strip():
            raise ValueError("formula phải có nội dung")
        return self


class Section6Extraction(BaseModel):
    """Vỏ JSON mà LLM phải trả về: danh sách dữ kiện §6."""

    facts: list[Section6Fact] = Field(default_factory=list)


def numeric_claims(fact: Section6Fact) -> list[tuple[str, NumericClaim]]:
    """Các trường số của một dữ kiện, kèm tên trường (để báo lý do từ chối)."""
    claims: list[tuple[str, NumericClaim]] = []
    if fact.limit is not None:
        claims.append(("limit", fact.limit))
    if fact.floor is not None:
        claims.append(("floor", fact.floor))
    return claims


# ── Xác minh quote: khớp nguyên văn hoặc sau chuẩn hóa dấu cách ───────────────


@dataclass(frozen=True)
class QuoteMatch:
    """Kết quả tìm ``quote`` trong văn bản mục."""

    found: bool
    start: int | None = None
    end: int | None = None
    exact: bool = False


# Ký tự điều khiển mà ``vnnum.normalize_spaces`` coi là khoảng trắng nhưng
# ``str.isspace()`` không (word joiner, BOM) — giữ hai bên khớp nhau.
_EXTRA_SPACE_CHARS = "\u2060\ufeff"


def _normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Chuẩn hóa dấu cách về một dấu cách, trả kèm bản đồ vị trí gốc.

    Mọi khoảng trắng (space, tab, xuống dòng, NBSP, NNBSP…) gộp thành một dấu
    cách; khoảng trắng đầu/cuối bị bỏ. ``map[i]`` là chỉ số trong ``text`` gốc
    của ký tự thứ ``i`` trong chuỗi đã chuẩn hóa.
    """
    chars: list[str] = []
    mapping: list[int] = []
    pending_space = False
    for index, ch in enumerate(text):
        if ch.isspace() or ch in _EXTRA_SPACE_CHARS:
            if chars:  # bỏ khoảng trắng đầu
                pending_space = True
            continue
        if pending_space:
            chars.append(" ")
            mapping.append(index)
            pending_space = False
        chars.append(ch)
        mapping.append(index)
    return "".join(chars), mapping


def locate_quote(quote: str | None, text: str) -> QuoteMatch:
    """Tìm ``quote`` trong ``text``: ưu tiên khớp nguyên văn, rồi khớp đã chuẩn hóa.

    Trả ``found=False`` khi không thấy — đây là cơ chế từ chối quote bịa. Khớp
    sau chuẩn hóa vẫn tính là hợp lệ (tài liệu Việt hay lệch NBSP/NNBSP), và trả
    khoảng ký tự gốc để giữ xuất xứ P1.
    """
    if not quote:
        return QuoteMatch(False)
    index = text.find(quote)
    if index >= 0:
        return QuoteMatch(True, index, index + len(quote), exact=True)

    normalized_quote, _ = _normalize_with_map(quote)
    if not normalized_quote:
        return QuoteMatch(False)
    normalized_text, mapping = _normalize_with_map(text)
    position = normalized_text.find(normalized_quote)
    if position < 0:
        return QuoteMatch(False)
    start = mapping[position]
    end = mapping[position + len(normalized_quote) - 1] + 1
    return QuoteMatch(True, start, end, exact=False)


def quote_contains_value(quote: str, value: float, *, tol: float = 1e-9) -> bool:
    """True nếu ``quote`` chứa một con số bằng ``value`` (sai số tương đối nhỏ)."""
    tolerance = max(tol, abs(value) * 1e-6)
    return any(abs(number - value) <= tolerance for number in vnnum.numbers(quote))


@dataclass(frozen=True)
class FactVerdict:
    """Phán quyết xác minh một dữ kiện §6."""

    ok: bool
    reasons: tuple[str, ...]
    quote_match: QuoteMatch
    numeric_matches: tuple[QuoteMatch, ...]


def verify_fact(fact: Section6Fact, text: str) -> FactVerdict:
    """Xác minh quote của dữ kiện và của MỌI trường số so với nguyên văn mục.

    Từ chối (``ok=False``) khi: quote dữ kiện không tìm thấy; quote của một trường
    số không tìm thấy; hoặc quote đó không chứa đúng con số đã khai (bịa số). Đây
    là hàng rào độc lập với việc người duyệt có đọc kỹ hay không (spec §7).
    """
    reasons: list[str] = []
    quote_match = locate_quote(fact.quote, text)
    if not quote_match.found:
        reasons.append("fact_quote_not_found")

    numeric_matches: list[QuoteMatch] = []
    for name, claim in numeric_claims(fact):
        match = locate_quote(claim.quote, text)
        if not match.found:
            reasons.append(f"{name}_quote_not_found")
        elif not quote_contains_value(claim.quote, claim.value):
            reasons.append(f"{name}_value_not_in_quote")
        numeric_matches.append(match)

    if fact.fact_kind == FORMULA_KIND and not (fact.formula or "").strip():
        reasons.append("formula_empty")

    return FactVerdict(
        ok=not reasons,
        reasons=tuple(reasons),
        quote_match=quote_match,
        numeric_matches=tuple(numeric_matches),
    )


# ── Chấm điểm tin cậy: quote + đơn vị + khoảng hợp lý ────────────────────────

QUOTE_WEIGHT = 0.45
NUMBER_WEIGHT = 0.20
UNIT_WEIGHT = 0.15
RANGE_WEIGHT = 0.20

# Đơn vị tương đối (tỷ lệ/độ ẩm) không đối chiếu được với phạm vi đo áp suất.
_RELATIVE_UNIT_CODES = {"%", "%RH"}


def _is_absolute(unit_def: units_module.UnitDef) -> bool:
    return unit_def.code not in _RELATIVE_UNIT_CODES


def _value_in_range(
    value: float,
    unit_def: units_module.UnitDef,
    working_range_si: tuple[float | None, float | None],
) -> bool:
    """True nếu giá trị (đổi sang SI) nằm trong phạm vi đo, có nới 50% biên độ.

    Nới để không phạt oan các giá trị biên hoặc phạm vi một đầu (ví dụ "đến
    1 400 bar"). Phạm vi không xác định thì coi là hợp lệ.
    """
    low, high = working_range_si
    if low is None and high is None:
        return True
    si_value = units_module.to_si(value, unit_def)
    bounds = [bound for bound in (low, high) if bound is not None]
    lo, hi = min(bounds), max(bounds)
    if lo == hi:
        return True
    slack = (hi - lo) * 0.5
    if low is not None and si_value < lo - slack:
        return False
    if high is not None and si_value > hi + slack:
        return False
    return True


def score_confidence(
    fact: Section6Fact,
    text: str,
    *,
    unit_defs: Iterable[units_module.UnitDef] = (),
    working_range_si: tuple[float | None, float | None] | None = None,
    verdict: FactVerdict | None = None,
) -> float:
    """Điểm tin cậy [0,1] từ khớp nguyên văn, đơn vị nhận diện, khoảng hợp lý.

    Dữ kiện không xác minh được nhận 0.0 (và bị loại trước đó). Dữ kiện hợp lệ
    cộng dồn bốn thành phần; đơn vị lạ hoặc giá trị ngoài phạm vi đo bị trừ đúng
    phần tương ứng để người duyệt chú ý (spec §6).
    """
    verdict = verdict or verify_fact(fact, text)
    if not verdict.ok:
        return 0.0

    claims = numeric_claims(fact)
    resolved = [units_module.resolve_unit(claim.unit, unit_defs) for _, claim in claims]

    score = QUOTE_WEIGHT
    # verify_fact đã bảo đảm mọi numeric quote khớp nguồn và chứa đúng giá trị.
    score += NUMBER_WEIGHT

    if all(unit_def is not None for unit_def in resolved):
        score += UNIT_WEIGHT

    if not claims or working_range_si is None:
        score += RANGE_WEIGHT
    else:
        plausible = all(
            unit_def is None
            or not _is_absolute(unit_def)
            or _value_in_range(claim.value, unit_def, working_range_si)
            for (_, claim), unit_def in zip(claims, resolved, strict=True)
        )
        if plausible:
            score += RANGE_WEIGHT

    return round(min(score, 1.0), 4)


# ── Kết quả trích xuất ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class VerifiedFact:
    """Dữ kiện §6 đã qua xác minh, sẵn sàng ghi ở trạng thái ``pending``."""

    fact: Section6Fact
    confidence: float
    section_path: str
    char_start: int | None
    char_end: int | None


@dataclass(frozen=True)
class RejectedFact:
    """Dữ kiện bị loại, kèm lý do và payload thô để rà soát."""

    fact: Section6Fact | None
    reasons: tuple[str, ...]
    raw: dict | None = None


@dataclass
class Section6Result:
    """Kết quả một lần trích xuất §6."""

    facts: list[VerifiedFact] = field(default_factory=list)
    rejected: list[RejectedFact] = field(default_factory=list)
    raw: str | None = None
    error: str | None = None
    model: str | None = None

    @property
    def accepted(self) -> list[VerifiedFact]:
        return self.facts


def numeric_hallucinations(result: Section6Result, text: str) -> int:
    """Số con số đã lọt vào kết quả chấp nhận mà quote không có trong nguồn.

    Cổng Sprint 5 yêu cầu giá trị này bằng 0 trên toàn bộ tập kiểm. Về thiết kế
    nó luôn bằng 0 vì ``verify_fact`` loại dữ kiện trước khi vào ``facts``; hàm
    kiểm lại độc lập để bắt hồi quy.
    """
    count = 0
    for verified in result.facts:
        for _, claim in numeric_claims(verified.fact):
            if not locate_quote(claim.quote, text).found or not quote_contains_value(
                claim.quote, claim.value
            ):
                count += 1
    return count


# ── Chia mục §6 (gồm cả các tiểu mục) ────────────────────────────────────────


def subtree_sections(sections: list[Section], root: Section) -> list[Section]:
    """Các mục con trực thuộc ``root`` theo số mục (``6`` → ``6.1``, ``6.2``…)."""
    parts = [root]
    start = sections.index(root)
    for section in sections[start + 1 :]:
        if root.number and section.number and section.number.startswith(f"{root.number}."):
            parts.append(section)
        else:
            break
    return parts


def section_path_at(sections: list[Section], position: int) -> str | None:
    """Đường dẫn mục cụ thể nhất chứa ``position`` (giữ xuất xứ P1)."""
    best: Section | None = None
    for section in sections:
        if section.start <= position < section.end and (
            best is None or section.level >= best.level
        ):
            best = section
    return best.path if best is not None else None


def find_section6(text: str) -> tuple[str, int, str] | None:
    """Trả ``(văn bản mục §6 gồm tiểu mục, offset tuyệt đối, đường dẫn)``."""
    sections = split_sections(text)
    root = find_section(sections, SECTION_KEYWORD)
    if root is None:
        return None
    parts = subtree_sections(sections, root)
    body = text[root.body_start : parts[-1].end]
    return body, root.body_start, root.path


# ── Prompt theo schema ────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "Bạn là bộ trích xuất dữ kiện đo lường từ quy trình kiểm định Việt Nam. "
    "Chỉ trả về JSON hợp lệ, không kèm giải thích hay văn bản ngoài JSON."
)

_PROMPT_TEMPLATE = """Trích các dữ kiện sau từ mục "{section_path}" của một QTKĐ:

- "max_permissible_error": giới hạn sai số cho phép (ví dụ "± 3% ... nhưng không
  nhỏ hơn ± 0,15 bar", "không được vượt quá 5% ...").
- "formula": công thức tính sai số/đại lượng, giữ nguyên LaTeX trong $...$.

QUY TẮC BẮT BUỘC:
1. MỌI con số phải nằm trong một trường "quote" SAO CHÉP NGUYÊN VĂN từ văn bản
   dưới đây. Không đổi số, không làm tròn, không đổi đơn vị.
2. Trường "quote" cấp dữ kiện là câu/cụm nguyên văn chứa dữ kiện đó.
3. Không suy luận, không tính toán, không bịa số hay công thức không có trong văn bản.
4. Nếu mục không có dữ kiện nào, trả đúng {{"facts": []}}.

Định dạng JSON:
{{"facts": [
  {{"fact_kind": "max_permissible_error", "label": "...", "rel_op": "±",
    "limit": {{"value": 3, "unit": "%", "quote": "..."}},
    "floor": {{"value": 0.15, "unit": "bar", "quote": "..."}},
    "condition_text": "...", "quote": "..."}},
  {{"fact_kind": "formula", "label": "...", "formula": "\\\\Delta = ...",
    "quote": "$\\\\Delta = ...$"}}
]}}

VĂN BẢN MỤC:
{body}
"""


def build_section6_prompt(body: str, section_path: str) -> str:
    """Dựng prompt yêu cầu LLM trả JSON theo schema cho một mục."""
    return _PROMPT_TEMPLATE.format(section_path=section_path, body=body.strip())


# ── Client Ollama (thất bại an toàn) ─────────────────────────────────────────


@dataclass(frozen=True)
class OllamaConfig:
    """Cấu hình client Ollama, đọc từ biến môi trường tại thời điểm gọi."""

    url: str = DEFAULT_OLLAMA_URL
    model: str = DEFAULT_MODEL
    timeout: int = 120
    num_ctx: int = 8192
    temperature: float = 0.0
    keep_alive: str = "10m"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> OllamaConfig:
        source = os.environ if env is None else env
        return cls(
            url=source.get("SECTION6_OLLAMA_URL") or source.get("OLLAMA_URL") or DEFAULT_OLLAMA_URL,
            model=source.get("SECTION6_LLM_MODEL") or source.get("OLLAMA_MODEL") or DEFAULT_MODEL,
            timeout=int(source.get("SECTION6_LLM_TIMEOUT", "120")),
            num_ctx=int(source.get("SECTION6_LLM_NUM_CTX", "8192")),
            temperature=float(source.get("SECTION6_LLM_TEMPERATURE", "0.0")),
        )


def _native_chat_url(url: str) -> str:
    """Map URL OpenAI-compat (.../v1/chat/completions) → Ollama native /api/chat."""
    return url.replace("/v1/chat/completions", "/api/chat")


class OllamaClient:
    """Client gọi Ollama nội bộ. ``chat`` trả ``None`` khi có bất kỳ lỗi nào.

    Thất bại an toàn là yêu cầu thiết kế: §6 là bước nạp ngoài giờ, Ollama chưa
    lên hoặc model chưa pull không được làm hỏng ingestion (spec §9 Sprint 5).
    """

    def __init__(self, config: OllamaConfig | None = None) -> None:
        self.config = config or OllamaConfig.from_env()

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> OllamaClient:
        return cls(OllamaConfig.from_env(env))

    @property
    def model_name(self) -> str:
        return self.config.model

    def chat(self, prompt: str, system: str | None = None) -> str | None:
        """Một lượt chat không streaming; ``None`` nếu lỗi/kết nối thất bại."""
        import requests

        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            response = requests.post(
                _native_chat_url(self.config.url),
                json={
                    "model": self.config.model,
                    "messages": messages,
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
            logger.warning("Gọi Ollama trích xuất §6 thất bại: %s", exc)
            return None
        message = payload.get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        return None


def default_client() -> OllamaClient:
    """Client mặc định đọc cấu hình từ env (điểm chèn cho test/CLI)."""
    return OllamaClient.from_env()


def llm_extraction_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Bật/tắt trích xuất §6 bằng LLM qua ``SECTION6_LLM_ENABLED`` (mặc định tắt)."""
    source = os.environ if env is None else env
    return source.get("SECTION6_LLM_ENABLED", "").strip().lower() in _TRUTHY


# ── Trích xuất ────────────────────────────────────────────────────────────────

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_json_payload(raw: str | None) -> dict | None:
    """Bóc JSON khỏi câu trả lời LLM (chấp nhận bọc trong ```json ... ```)."""
    if not raw:
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


def extract_section6(
    text: str,
    client: OllamaClient | None = None,
    *,
    unit_defs: Iterable[units_module.UnitDef] = (),
    working_range_si: tuple[float | None, float | None] | None = None,
    section_path: str | None = None,
    model_name: str | None = None,
) -> Section6Result:
    """Chạy LLM trên mục §6 và trả các dữ kiện đã xác minh + bị loại.

    Không chạm DB. Thất bại an toàn: không tìm thấy mục, LLM lỗi, JSON hỏng đều
    trả ``Section6Result`` với ``facts=[]`` và ``error`` mô tả — không ném ra ngoài.
    """
    client = client or default_client()
    if model_name is None:
        model_name = getattr(client, "model_name", None)

    found = find_section6(text)
    if found is None:
        return Section6Result(error="section_not_found", model=model_name)
    body, body_start, root_path = found
    if section_path is None:
        section_path = root_path

    raw = client.chat(build_section6_prompt(body, section_path), system=SYSTEM_PROMPT)
    if raw is None:
        return Section6Result(error="llm_unavailable", model=model_name)

    payload = parse_json_payload(raw)
    if payload is None:
        return Section6Result(raw=raw, error="invalid_json", model=model_name)

    raw_facts = payload.get("facts")
    if not isinstance(raw_facts, list):
        return Section6Result(raw=raw, error="invalid_shape", model=model_name)

    sections = split_sections(text)
    result = Section6Result(raw=raw, model=model_name)
    for item in raw_facts:
        if not isinstance(item, dict):
            result.rejected.append(RejectedFact(None, ("schema_invalid",), None))
            continue
        try:
            fact = Section6Fact.model_validate(item)
        except ValidationError as exc:
            result.rejected.append(RejectedFact(None, ("schema_invalid",), item))
            logger.debug("Dữ kiện §6 sai schema: %s", exc)
            continue

        verdict = verify_fact(fact, body)
        if not verdict.ok:
            result.rejected.append(RejectedFact(fact, verdict.reasons, item))
            continue

        confidence = score_confidence(
            fact,
            body,
            unit_defs=unit_defs,
            working_range_si=working_range_si,
            verdict=verdict,
        )
        match = verdict.quote_match
        if match.start is not None and match.end is not None:
            absolute_start = body_start + match.start
            absolute_end = body_start + match.end
            resolved_path = section_path_at(sections, absolute_start) or section_path
        else:  # pragma: no cover - locate_quote luôn trả offset khi found
            absolute_start = absolute_end = None
            resolved_path = section_path
        result.facts.append(
            VerifiedFact(
                fact=fact,
                confidence=confidence,
                section_path=resolved_path,
                char_start=absolute_start,
                char_end=absolute_end,
            )
        )
    return result
