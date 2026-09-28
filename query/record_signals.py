"""Định tuyến tất định cho câu hỏi về biên bản trong sổ cái (Pha R, spec §8).

Chạy SAU bộ phân loại LLM (và sau ``disambiguate_catalogs``). LLM nhỏ hay chọn
intent gần đúng cho câu hỏi về một biên bản cụ thể (``latest_record`` cho câu hỏi
về biên bản ngày X, ``procedure_params`` cho phạm vi đo của một thiết bị, ...). Lớp
này sửa lựa chọn đó bằng BẰNG CHỨNG KHỚP CHÍNH XÁC với sổ cái đã duyệt:

- số hiệu thiết bị / số biên bản có trong sổ cái + trường hoặc ngày được hỏi
  → ``record_lookup`` (kể cả khi LLM trả ``text``: một số hiệu khớp đúng sổ cái
  không thể là câu hỏi quy định chung);
- tên kiểm định viên / người kiểm soát có trong sổ cái + "biên bản"
  → ``records_summary`` lọc theo người;
- từ cực trị ("thấp nhất", "lớn nhất") + trường so sánh được → ``records_summary``
  cực trị; "toàn bộ hồ sơ", "bao nhiêu biên bản", lọc đơn vị phạm vi đo
  → ``records_summary``. Các nhóm này chỉ mở nhánh số liệu khi LLM đã chọn nhánh
  số liệu hoặc câu hỏi nhắc tới biên bản/hồ sơ/thiết bị.

Tham số lấy từ chính câu hỏi (không từ LLM) nên không thể bịa. Chỉ đọc view đã
duyệt (P3); mọi thất bại DB giữ nguyên quyết định LLM.
"""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import text

from knowledge import vnnum
from query.record_fields import Targets, detect_targets, field_catalog

_DMY_RE = re.compile(r"(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})(?!\d)")
_CERT_RE = re.compile(r"(?<![\d/])(\d{1,4}/\d{4})(?![\d/])")
_SERIAL_TOKEN_RE = re.compile(r"[\w\-]+", re.UNICODE)
_RANGE_UNIT_RE = re.compile(
    r"(?:đơn\s+vị|theo)\s+(bar|mbar|mpa|kpa|pa|psi|kgf/cm2|kg/cm2|kgf/cm²|kg/cm²)(?![\w/])",
    re.IGNORECASE,
)
_NOMINAL_RE = re.compile(
    r"(?:tại|ở)\s+(?:điểm\s+(?:đo\s+)?|mức\s+|áp\s+suất\s+)(\d[\d\s.,]*\d|\d)", re.IGNORECASE
)
_MIN_RE = re.compile(r"thấp\s+nhất|nhỏ\s+nhất|ít\s+nhất|bé\s+nhất", re.IGNORECASE)
_MAX_RE = re.compile(r"cao\s+nhất|lớn\s+nhất|nhiều\s+nhất|dài\s+nhất", re.IGNORECASE)
_SUMMARY_RE = re.compile(
    r"toàn\s+bộ\s+hồ\s+sơ|tất\s+cả\s+(?:các\s+)?biên\s+bản|bao\s+nhiêu\s+biên\s+bản|"
    r"mấy\s+biên\s+bản|bao\s+nhiêu\s+thiết\s+bị|có\s+bao\s+nhiêu\s+(?:áp\s+kế|thiết\s+bị)",
    re.IGNORECASE,
)
_RECORD_WORD_RE = re.compile(r"biên\s+bản|hồ\s+sơ", re.IGNORECASE)
# Câu hỏi về danh mục kiểm định viên (Biểu 7), không phải biên bản họ lập.
_INSPECTOR_CATALOG_RE = re.compile(r"số\s+thẻ|chứng\s+nhận|lĩnh\s+vực|trình\s+độ", re.IGNORECASE)
_LEDGER_WORD_RE = re.compile(r"biên\s+bản|hồ\s+sơ|áp\s+kế|thiết\s+bị|sổ\s+cái", re.IGNORECASE)
_SERIAL_WORD_RE = re.compile(r"số\s+hiệu|serial|\bsn\b", re.IGNORECASE)
_MIN_BARE_SERIAL_DIGITS = 4
_HISTORY_INTENTS = frozenset({"device_history", "latest_record", "error_trend"})
_LEDGER_TTL_SECONDS = 30.0


@dataclass(frozen=True)
class LedgerIndex:
    """Định danh có trong sổ cái đã duyệt (khóa đã casefold → nguyên văn)."""

    serials: dict[str, str] = field(default_factory=dict)
    cert_nos: frozenset[str] = frozenset()
    inspectors: dict[str, str] = field(default_factory=dict)
    reviewers: dict[str, str] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return not self.serials and not self.cert_nos


@dataclass(frozen=True)
class RecordSignals:
    serials: tuple[str, ...] = ()
    cert_nos: tuple[str, ...] = ()
    dates: tuple[date, ...] = ()
    inspector: str | None = None
    reviewer: str | None = None
    range_unit: str | None = None
    nominal: float | None = None
    measure: str | None = None
    summary_cue: bool = False
    targets: Targets = Targets()


_LEDGER_CACHE: dict[str, tuple[float, LedgerIndex]] = {}


def _fold(value: str) -> str:
    return unicodedata.normalize("NFC", value.strip()).casefold()


def _cache_key(session: Any) -> str | None:
    try:
        engine = session.get_bind()
        return f"{engine.url}#{id(engine)}"
    except Exception:  # noqa: BLE001 - cache chỉ là tối ưu
        return None


def build_ledger_index(session: Any) -> LedgerIndex:
    """Đọc định danh từ ``v_record_detail``; thất bại DB → chỉ mục rỗng."""
    try:
        rows = session.execute(
            text("SELECT serial_no, cert_no, inspector_name, reviewer_name FROM v_record_detail")
        ).all()
    except Exception:  # noqa: BLE001 - thiếu view/kết nối thì không có tín hiệu sổ cái
        return LedgerIndex()
    serials: dict[str, str] = {}
    inspectors: dict[str, str] = {}
    reviewers: dict[str, str] = {}
    cert_nos: set[str] = set()
    for serial, cert_no, inspector, reviewer in rows:
        if serial and str(serial).strip():
            serials[_fold(str(serial))] = str(serial).strip()
        if cert_no and str(cert_no).strip():
            cert_nos.add(str(cert_no).strip())
        if inspector and str(inspector).strip():
            inspectors[_fold(str(inspector))] = str(inspector).strip()
        if reviewer and str(reviewer).strip():
            reviewers[_fold(str(reviewer))] = str(reviewer).strip()
    return LedgerIndex(serials, frozenset(cert_nos), inspectors, reviewers)


def ledger_index(session: Any) -> LedgerIndex:
    """Chỉ mục sổ cái có cache ngắn hạn, khóa theo engine (tránh lẫn DB test)."""
    key = _cache_key(session)
    now = time.monotonic()
    if key is not None:
        cached = _LEDGER_CACHE.get(key)
        if cached is not None and now - cached[0] < _LEDGER_TTL_SECONDS:
            return cached[1]
    index = build_ledger_index(session)
    if key is not None:
        _LEDGER_CACHE[key] = (now, index)
    return index


def _dates(question: str) -> tuple[date, ...]:
    found = []
    for day, month, year in _DMY_RE.findall(question):
        try:
            found.append(date(int(year), int(month), int(day)))
        except ValueError:
            continue
    return tuple(found)


def _person(question: str, names: dict[str, str]) -> str | None:
    folded = _fold(question)
    # Tên dài trước để một tên ngắn hơn không cắt mất tên dài.
    for key in sorted(names, key=len, reverse=True):
        if key and key in folded:
            return names[key]
    return None


def _nominal(question: str) -> float | None:
    match = _NOMINAL_RE.search(question)
    return vnnum.parse_number(match.group(1).strip()) if match else None


def _ambiguous_serial(token: str) -> bool:
    """Số hiệu toàn chữ số và ngắn dễ trùng một con số bất kỳ trong câu hỏi."""
    return token.isdigit() and len(token) < _MIN_BARE_SERIAL_DIGITS


def extract_signals(question: str, index: LedgerIndex, session: Any) -> RecordSignals:
    """Tín hiệu sổ cái trong câu hỏi, chỉ giữ định danh KHỚP ĐÚNG sổ cái."""
    text_value = question or ""
    without_dates = _DMY_RE.sub(" ", text_value)
    cert_nos = [cert for cert in _CERT_RE.findall(without_dates) if cert in index.cert_nos]
    tokens = [token.casefold() for token in _SERIAL_TOKEN_RE.findall(without_dates)]
    has_serial_word = bool(_SERIAL_WORD_RE.search(text_value))
    serials = [
        index.serials[token]
        for token in tokens
        if token in index.serials and (has_serial_word or not _ambiguous_serial(token))
    ]
    unit_match = _RANGE_UNIT_RE.search(text_value)
    measure = "min" if _MIN_RE.search(text_value) else "max" if _MAX_RE.search(text_value) else None
    return RecordSignals(
        serials=tuple(dict.fromkeys(serials)),
        cert_nos=tuple(dict.fromkeys(cert_nos)),
        dates=_dates(text_value),
        inspector=_person(text_value, index.inspectors),
        reviewer=_person(text_value, index.reviewers),
        range_unit=unit_match.group(1) if unit_match else None,
        nominal=_nominal(text_value),
        measure=measure,
        summary_cue=bool(_SUMMARY_RE.search(text_value)),
        targets=detect_targets(text_value, field_catalog(session)),
    )


def _payload(base: dict[str, Any], intent: str, params: dict[str, Any]) -> dict[str, Any]:
    return {
        **base,
        "branch": "data",
        "intent": intent,
        "params": {key: value for key, value in params.items() if value not in (None, [], "")},
        "confidence": base.get("confidence", 0.9),
    }


def _lookup(base: dict[str, Any], signals: RecordSignals) -> dict[str, Any]:
    return _payload(
        base,
        "record_lookup",
        {
            "serial": signals.serials[0] if signals.serials else None,
            "cert_no": signals.cert_nos[0] if signals.cert_nos else None,
            "calibrated_on": signals.dates[0].isoformat() if signals.dates else None,
            "fields": list(signals.targets.fields),
            "steps": list(signals.targets.steps),
            "nominal": signals.nominal,
        },
    )


def _summary(
    base: dict[str, Any], signals: RecordSignals, question: str, **extra: Any
) -> dict[str, Any]:
    from query.intents import extract_date_range

    params = {"range_unit": signals.range_unit, **extract_date_range(question), **extra}
    return _payload(base, "records_summary", params)


def _is_history_question(payload: dict[str, Any], intent: str, signals: RecordSignals) -> bool:
    """LLM chọn lịch sử/lần gần nhất và câu hỏi không nhắm MỘT biên bản hay trường riêng.

    Nhánh ``mixed`` (quy định QTKĐ + lịch sử thực tế) luôn giữ: trường như "phạm vi
    đo" ở đó là của QTKĐ, phần sổ cái vẫn là lịch sử thiết bị.
    """
    if intent not in _HISTORY_INTENTS or signals.dates or signals.cert_nos:
        return False
    if str(payload.get("branch") or "") == "mixed":
        return True
    return not signals.targets.specific_fields and not signals.targets.steps


def _comparable_field(signals: RecordSignals) -> str | None:
    if signals.targets.steps:
        return signals.targets.steps[0]
    specific = signals.targets.specific_fields
    return specific[0] if specific else None


def _person_filter(question: str, signals: RecordSignals) -> dict[str, str]:
    if not _RECORD_WORD_RE.search(question) or _INSPECTOR_CATALOG_RE.search(question):
        return {}
    if signals.inspector:
        return {"inspector": signals.inspector}
    if signals.reviewer:
        return {"reviewer": signals.reviewer}
    return {}


def disambiguate_records(
    payload: dict[str, Any] | None, question: str, session: Any | None
) -> dict[str, Any] | None:
    """Sửa intent cho câu hỏi về biên bản bằng bằng chứng khớp đúng sổ cái đã duyệt."""
    if not isinstance(payload, dict) or session is None:
        return payload
    index = ledger_index(session)
    if index.empty:
        return payload
    question = question or ""
    signals = extract_signals(question, index, session)
    intent = str(payload.get("intent") or "").strip().lower()

    if signals.serials or signals.cert_nos:
        if not _is_history_question(payload, intent, signals):
            return _lookup(payload, signals)
        params = dict(payload.get("params") or {})
        if signals.serials and _fold(str(params.get("serial") or "")) not in index.serials:
            params["serial"] = signals.serials[0]
        return {**payload, "params": params}

    is_data = str(payload.get("branch") or "") in ("data", "mixed")
    if not (is_data or _LEDGER_WORD_RE.search(question)):
        return payload

    person = _person_filter(question, signals)
    if person:
        return _summary(payload, signals, question, **person)
    comparable = _comparable_field(signals)
    if signals.measure and comparable:
        return _summary(payload, signals, question, measure=signals.measure, field=comparable)
    if signals.summary_cue or signals.range_unit:
        if intent == "records_by_period" and (payload.get("params") or {}).get("date_from"):
            return payload
        return _summary(payload, signals, question)
    return payload
