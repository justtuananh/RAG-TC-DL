"""Định tuyến tất định cho câu hỏi về biên bản trong sổ cái (Pha R, spec §8).

Chạy SAU bộ phân loại LLM (và sau ``disambiguate_catalogs``). LLM nhỏ hay chọn
intent gần đúng cho câu hỏi về một biên bản cụ thể (``latest_record`` cho câu hỏi
về biên bản ngày X, ``procedure_params`` cho phạm vi đo của một thiết bị, ...). Lớp
này sửa lựa chọn đó bằng BẰNG CHỨNG KHỚP CHÍNH XÁC với sổ cái đã duyệt:

- số hiệu thiết bị / số biên bản có trong sổ cái + trường hoặc ngày được hỏi
  → ``record_lookup`` (kể cả khi LLM trả ``text``: một số hiệu khớp đúng sổ cái
  không thể là câu hỏi quy định chung);
- tên kiểm định viên / người kiểm soát có trong sổ cái + "biên bản"
  → ``records_summary`` lọc theo người; tên đơn vị sử dụng có trong sổ cái (đủ tên,
  hoặc phần đuôi riêng như "Đông Phương") + "biên bản"/liệt kê/đếm → lọc theo đơn vị;
- từ cực trị ("thấp nhất", "lớn nhất") + trường so sánh được → ``records_summary``
  cực trị; "toàn bộ hồ sơ", "bao nhiêu biên bản", lọc đơn vị phạm vi đo
  → ``records_summary``. Các nhóm này chỉ mở nhánh số liệu khi LLM đã chọn nhánh
  số liệu hoặc câu hỏi nói rõ về biên bản/hồ sơ.

Số hiệu toàn chữ số chỉ được nhận khi có chữ "số hiệu" hoặc đứng ngay sau từ chỉ
thiết bị, để một con số trong câu hỏi quy định không bị hiểu thành số hiệu.

Tham số lấy từ chính câu hỏi (không từ LLM) nên không thể bịa. Chỉ đọc view đã
duyệt (P3); mọi thất bại DB giữ nguyên quyết định LLM.
"""

from __future__ import annotations

import logging
import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from knowledge import vnnum
from query.record_fields import Targets, content_tokens, detect_targets, field_catalog

logger = logging.getLogger(__name__)

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
_SERIAL_WORD_RE = re.compile(r"số\s+hiệu|serial|\bsn\b", re.IGNORECASE)
# Token ngay sau từ chỉ thiết bị ("áp kế 1045", "thiết bị 6112", "số hiệu 0391").
_DEVICE_CONTEXT_RE = re.compile(
    r"(?:áp\s*kế|thiết\s*bị|máy|số\s*hiệu|sn|serial)\s*[:#.\-]?\s*([\w\-]*\d[\w\-]*)",
    re.IGNORECASE | re.UNICODE,
)
# Liệt kê / đếm: điều kiện để bộ lọc đơn vị phạm vi đo mở tổng hợp sổ cái.
_LIST_CUE_RE = re.compile(
    r"liệt\s+kê|danh\s+sách|bao\s+nhiêu|mấy\s|những\s+(?:áp\s+kế|thiết\s+bị|biên\s+bản)|"
    r"các\s+(?:áp\s+kế|thiết\s+bị|biên\s+bản)",
    re.IGNORECASE,
)
# Kết luận là TIÊU CHÍ chọn ("biên bản nào không đạt", "có bao nhiêu biên bản không đạt").
# Chỉ khi câu hỏi đếm NHIỀU thứ ("bao nhiêu biên bản, bao nhiêu thiết bị và bao nhiêu biên
# bản không đạt") thì kết luận là một phép đếm cạnh tổng số, không lọc.
_VERDICT_RE = re.compile(
    r"(?:biên\s+bản|hồ\s+sơ|thiết\s+bị|áp\s+kế)\s+(?:nào\s+)?(?:bị\s+)?(?:kết\s+luận\s+)?"
    r"(?:là\s+)?(không\s+)?đạt(?!\s+được)",
    re.IGNORECASE,
)
_COUNT_BEFORE_RE = re.compile(r"(?:bao\s+nhiêu|mấy)\s*$", re.IGNORECASE)
_COUNT_RE = re.compile(r"bao\s+nhiêu|mấy\s", re.IGNORECASE)
_WORD_RE = re.compile(r"[\w\-]+", re.UNICODE)
# Từ chung của tên đơn vị: một phần đuôi chỉ gồm các từ này ("đo lường", "trung tâm")
# có mặt trong câu hỏi quy định nên không đủ để nhận ra một đơn vị cụ thể.
_GENERIC_ORG_WORDS = frozenset(
    "công ty cp tnhh nhà máy trung tâm viện phòng đo lường kiểm định kỹ thuật an toàn "
    "khu vực cơ khí năng lượng nhiệt điện áp suất nhiệt-áp thủy lực lọc hóa hoá dầu "
    "khí công nghiệp miền và của".split()
)
# Liệt kê thật sự (không gồm "bao nhiêu", vốn có mặt cả trong câu hỏi quy định).
_ENUMERATE_RE = re.compile(
    r"liệt\s+kê|danh\s+sách|(?:những|các)\s+(?:áp\s+kế|thiết\s+bị|biên\s+bản)", re.IGNORECASE
)
_HISTORY_INTENTS = frozenset({"device_history", "latest_record", "error_trend"})
_LEDGER_TTL_SECONDS = 30.0


@dataclass(frozen=True)
class LedgerIndex:
    """Định danh có trong sổ cái đã duyệt (khóa đã casefold → nguyên văn)."""

    serials: dict[str, str] = field(default_factory=dict)
    cert_nos: frozenset[str] = frozenset()
    inspectors: dict[str, str] = field(default_factory=dict)
    reviewers: dict[str, str] = field(default_factory=dict)
    owners: dict[str, str] = field(default_factory=dict)

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
    owner_org: str | None = None
    verdict: str | None = None
    range_unit: str | None = None
    nominal: float | None = None
    measure: str | None = None
    summary_cue: bool = False
    targets: Targets = Targets()
    question_words: frozenset[str] = frozenset()


_LEDGER_CACHE: dict[str, tuple[float, LedgerIndex]] = {}
_LEDGER_LOCK = threading.Lock()


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
            text(
                "SELECT serial_no, cert_no, inspector_name, reviewer_name, owner_org "
                "FROM v_record_detail"
            )
        ).all()
    except SQLAlchemyError as exc:
        # Thiếu view/kết nối thì không có tín hiệu sổ cái; ghi log vì chỉ mục rỗng làm tắt
        # lớp định tuyến tất định.
        logger.warning("Không đọc được chỉ mục sổ cái: %s", exc)
        return LedgerIndex()
    serials: dict[str, str] = {}
    inspectors: dict[str, str] = {}
    reviewers: dict[str, str] = {}
    owners: dict[str, str] = {}
    cert_nos: set[str] = set()
    for serial, cert_no, inspector, reviewer, owner in rows:
        if serial and str(serial).strip():
            serials[_fold(str(serial))] = str(serial).strip()
        if cert_no and str(cert_no).strip():
            cert_nos.add(str(cert_no).strip())
        if inspector and str(inspector).strip():
            inspectors[_fold(str(inspector))] = str(inspector).strip()
        if reviewer and str(reviewer).strip():
            reviewers[_fold(str(reviewer))] = str(reviewer).strip()
        if owner and str(owner).strip():
            owners[_fold(str(owner))] = str(owner).strip()
    return LedgerIndex(serials, frozenset(cert_nos), inspectors, reviewers, owners)


def ledger_index(session: Any) -> LedgerIndex:
    """Chỉ mục sổ cái có cache ngắn hạn, khóa theo engine (tránh lẫn DB test)."""
    key = _cache_key(session)
    if key is None:
        return build_ledger_index(session)
    with _LEDGER_LOCK:
        cached = _LEDGER_CACHE.get(key)
        if cached is not None and time.monotonic() - cached[0] < _LEDGER_TTL_SECONDS:
            return cached[1]
        index = build_ledger_index(session)
        _LEDGER_CACHE[key] = (time.monotonic(), index)
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


def _has_phrase(folded: str, words: list[str]) -> bool:
    phrase = r"\s+".join(re.escape(word) for word in words)
    return re.search(rf"(?<![\w\-]){phrase}(?![\w\-])", folded) is not None


def _owner(question: str, owners: dict[str, str]) -> str | None:
    """Đơn vị sử dụng có trong sổ cái: đủ tên, hoặc phần đuôi riêng của đúng MỘT đơn vị.

    Phần đuôi cần ít nhất hai từ và một từ không phải từ chung (``_GENERIC_ORG_WORDS``),
    để "phòng đo lường" trong câu hỏi không bị hiểu thành một đơn vị cụ thể.
    """
    folded = _fold(question)
    full = [name for key, name in owners.items() if key in folded]
    if full:
        return max(full, key=len)
    matches: set[str] = set()
    for key, name in owners.items():
        words = _WORD_RE.findall(key)
        for size in range(len(words) - 1, 1, -1):
            tail = words[-size:]
            if all(word in _GENERIC_ORG_WORDS for word in tail):
                continue
            if _has_phrase(folded, tail):
                matches.add(name)
                break
    return matches.pop() if len(matches) == 1 else None


def _verdict(question: str) -> str | None:
    several_counts = len(_COUNT_RE.findall(question)) > 1
    for match in _VERDICT_RE.finditer(question):
        if several_counts and _COUNT_BEFORE_RE.search(question[: match.start()]):
            continue
        return "khong_dat" if match.group(1) else "dat"
    return None


def _nominal(question: str) -> float | None:
    match = _NOMINAL_RE.search(question)
    return vnnum.parse_number(match.group(1).strip()) if match else None


def _serial_tokens(text_value: str, index: LedgerIndex) -> list[str]:
    """Số hiệu sổ cái trong câu hỏi.

    Số hiệu toàn chữ số ("1045", "2500") dễ trùng một con số của quy định ("đến 2500
    kgf/cm²"), nên chỉ nhận khi câu hỏi có chữ "số hiệu"/"serial" hoặc số đứng ngay
    sau từ chỉ thiết bị. Số hiệu có chữ ("1A0043219", "B280-7702") luôn nhận.
    """
    has_serial_word = bool(_SERIAL_WORD_RE.search(text_value))
    in_context = {match.casefold() for match in _DEVICE_CONTEXT_RE.findall(text_value)}
    found = []
    for token in (token.casefold() for token in _SERIAL_TOKEN_RE.findall(text_value)):
        if token not in index.serials:
            continue
        if token.isdigit() and not (has_serial_word or token in in_context):
            continue
        found.append(index.serials[token])
    return found


def extract_signals(question: str, index: LedgerIndex, session: Any) -> RecordSignals:
    """Tín hiệu sổ cái trong câu hỏi, chỉ giữ định danh KHỚP ĐÚNG sổ cái."""
    text_value = question or ""
    without_dates = _DMY_RE.sub(" ", text_value)
    cert_nos = [cert for cert in _CERT_RE.findall(without_dates) if cert in index.cert_nos]
    serials = _serial_tokens(without_dates, index)
    unit_match = _RANGE_UNIT_RE.search(text_value)
    measure = "min" if _MIN_RE.search(text_value) else "max" if _MAX_RE.search(text_value) else None
    return RecordSignals(
        serials=tuple(dict.fromkeys(serials)),
        cert_nos=tuple(dict.fromkeys(cert_nos)),
        dates=_dates(text_value),
        inspector=_person(text_value, index.inspectors),
        reviewer=_person(text_value, index.reviewers),
        owner_org=_owner(text_value, index.owners),
        verdict=_verdict(text_value),
        range_unit=unit_match.group(1) if unit_match else None,
        nominal=_nominal(text_value),
        measure=measure,
        summary_cue=bool(_SUMMARY_RE.search(text_value)),
        targets=detect_targets(text_value, field_catalog(session)),
        question_words=content_tokens(text_value),
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
            "focus_words": sorted(signals.question_words) if signals.targets.steps else [],
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


def _ledger_filters(question: str, signals: RecordSignals) -> dict[str, str]:
    """Bộ lọc người / đơn vị sử dụng lấy nguyên văn từ sổ cái (không từ LLM)."""
    filters: dict[str, str] = {}
    about_records = bool(_RECORD_WORD_RE.search(question))
    if about_records and not _INSPECTOR_CATALOG_RE.search(question):
        if signals.inspector:
            filters["inspector"] = signals.inspector
        elif signals.reviewer:
            filters["reviewer"] = signals.reviewer
    listing = about_records or signals.summary_cue or bool(_LIST_CUE_RE.search(question))
    if signals.owner_org and listing:
        filters["owner_org"] = signals.owner_org
    if signals.verdict and about_records:
        filters["verdict"] = signals.verdict
    return filters


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

    # Không có định danh sổ cái: chỉ mở nhánh số liệu từ ``text`` khi câu hỏi nói rõ về
    # biên bản/hồ sơ ("áp kế"/"thiết bị" có mặt trong mọi câu hỏi quy định).
    is_data = str(payload.get("branch") or "") in ("data", "mixed")
    # Liệt kê thiết bị theo đơn vị phạm vi đo ("liệt kê các áp kế có phạm vi đo theo đơn vị
    # MPa") là câu hỏi sổ cái dù không có chữ "biên bản".
    unit_listing = bool(signals.range_unit and _ENUMERATE_RE.search(question))
    if not (is_data or _RECORD_WORD_RE.search(question) or signals.summary_cue or unit_listing):
        return payload

    filters = _ledger_filters(question, signals)
    by_period = intent == "records_by_period" and (payload.get("params") or {}).get("date_from")
    if by_period and set(filters) <= {"verdict"}:
        # records_by_period lọc được khoảng ngày + kết luận: giữ lựa chọn LLM, chỉ bổ sung
        # kết luận lấy từ câu hỏi khi LLM bỏ sót.
        params = dict(payload.get("params") or {})
        if filters.get("verdict") and not params.get("verdict"):
            return {**payload, "params": {**params, "verdict": filters["verdict"]}}
        return payload
    comparable = _comparable_field(signals)
    if signals.measure and comparable:
        scope = {"procedure_ids": list(signals.targets.procedures)} if signals.targets.steps else {}
        return _summary(
            payload,
            signals,
            question,
            measure=signals.measure,
            field=comparable,
            **scope,
            **filters,
        )
    if filters:
        return _summary(payload, signals, question, **filters)
    if signals.summary_cue or (signals.range_unit and _LIST_CUE_RE.search(question)):
        if by_period:
            return payload
        return _summary(payload, signals, question)
    return payload
