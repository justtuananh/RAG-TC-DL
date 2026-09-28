"""Cổng tín hiệu buộc gọi LLM phân loại intent (spec §8, Sprint 9 + Pha D2).

Cổng này CHỈ quyết định có gọi LLM hay không, KHÔNG quyết định nhánh: không có tín
hiệu nào thì chắc chắn là câu hỏi văn bản và bỏ qua LLM (giữ trải nghiệm RAG văn
bản, không thêm độ trễ). Vì thế cổng không bao giờ tự mở nhánh số liệu.

Tách khỏi ``query/intents.py`` để giữ tệp gọn; chỉ đọc view đã duyệt (P3) và mọi
thất bại DB đều bị nuốt (coi như không có tín hiệu).
"""

from __future__ import annotations

import re
import time
from typing import Any

from catalogs.text import fold
from query import catalogs as catalogs_query

# Tín hiệu thô buộc phải gọi LLM phân loại. Cố ý KHÔNG khớp các từ chung như
# "kiểm định"/"thiết bị" — câu hỏi quy định (sai số, điều kiện, công thức) vẫn đi
# thẳng pipeline văn bản.
_DATA_SIGNAL_RE = re.compile(
    r"("
    r"số hiệu|so hieu|serial|\bsn[\s\-_]?\w|"
    r"hồ sơ|ho so|biên bản|bien ban|"
    r"lịch sử|lich su|gần nhất|gan nhat|lần cuối|lan cuoi|"
    r"lần gần đây nhất|lan gan day nhat|khi nào hết hạn|khi nao het han|hết hạn|het han|"
    r"đã kiểm mấy lần|da kiem may lan|kiểm mấy lần|kiem may lan|"
    r"không đạt|khong dat|"
    r"từ ngày|tu ngay|đến ngày|den ngay|trong năm|trong tháng|trong khoảng|"
    r"khoảng thời gian|khoang thoi gian|năm 20\d\d|"
    r"phạm vi đo|pham vi do|xu hướng|xu huong|diễn biến sai số|dien bien sai so|"
    r"phương tiện kiểm định|phuong tien kiem dinh|bảng 2|bang 2|"
    r"bao nhiêu hồ sơ|bao nhieu ho so|đại lượng|dai luong|"
    r"\b\d\.\d{3}\b|"
    r"\b\d{1,3}[A-ZĐ]{1,4}\d{2,}\b|"
    r"\b[A-Z]{1,4}\d{2,}(?:-\d+)*\b|"
    r"\b\d{2,4}-\d{2,4}\b|"
    r"\b0\d{2,}\b"
    r")",
    re.IGNORECASE,
)

# Tín hiệu CÓ NGUYÊN TẮC bổ sung: một token giống số hiệu thiết bị (có ít nhất một
# chữ số, cho phép chữ và gạch nối) đứng ngay sau từ chỉ thiết bị. Bắt được các
# cách hỏi mới như "áp kế 2218 kiểm mấy lần rồi", "thiết bị 1A0043219 lần mới nhất".
_DEVICE_SERIAL_CONTEXT_RE = re.compile(
    r"(?:áp\s*kế|thiết\s*bị|máy|phương\s*tiện|số\s*hiệu|sn|serial)"
    r"\s*[:#.\-]?\s*"
    r"(?=[\w\-]*\d)[\w\-]+",
    re.IGNORECASE | re.UNICODE,
)
_SERIAL_TOKEN_RE = re.compile(r"[\w\-]+", re.UNICODE)

# Tín hiệu danh mục NAS (Pha D2): câu hỏi về chuẩn mẫu, kiểm định viên, danh mục
# quy trình, lĩnh vực công nhận phải được gọi LLM phân loại. Cố ý hẹp để câu hỏi
# quy định/công thức vẫn đi thẳng nhánh văn bản.
_CATALOG_SIGNAL_RE = re.compile(
    r"("
    r"chuẩn mẫu|chuan mau|"
    r"chuẩn nào|chuan nao|những chuẩn|nhung chuan|các chuẩn|cac chuan|"
    r"\bptđ\b|\bpttn\b|"
    r"kiểm định viên|kiem dinh vien|\bkdv\b|"
    r"số thẻ|so the|"
    r"chứng nhận|chung nhan|được công nhận|duoc cong nhan|"
    r"ban hành|"
    r"danh mục quy trình|danh muc quy trinh|"
    r"danh mục tiêu chuẩn|danh muc tieu chuan|"
    r"mã quy trình|ma quy trinh|"
    r"quy trình kiểm định\s+\S.*?\s+là gì|"
    r"lĩnh vực|linh vuc|"
    r"chu kỳ hiệu chuẩn|chu ky hieu chuan|"
    r"hiệu chuẩn gần nhất|hieu chuan gan nhat|"
    r"ai\s+được|ai duoc|ai\s+có thể|ai co the|"
    r"những ai|nhung ai|"
    r"\bai\b[^?.!]{0,40}(?:kiểm định|hiệu chuẩn|chứng nhận|công nhận)"
    r")",
    re.IGNORECASE,
)

# Cache ngắn hạn số hiệu có trong sổ cái đã duyệt, khoá theo engine để tránh lẫn
# giữa các CSDL in-memory ("sqlite://") trong test.
_LEDGER_SERIAL_CACHE: dict[str, tuple[float, frozenset[str]]] = {}
_LEDGER_SERIAL_TTL_SECONDS = 30.0


def _ledger_cache_key(session: Any) -> str | None:
    try:
        engine = session.get_bind()
        return f"{engine.url}#{id(engine)}"
    except Exception:  # noqa: BLE001 - cache chỉ là tối ưu
        return None


def ledger_serials(session: Any) -> frozenset[str]:
    """Số hiệu thiết bị có trong sổ cái đã duyệt; rỗng nếu không truy được.

    Thất bại DB (chưa migrate, mất kết nối) bị nuốt và coi như không có tín hiệu.
    """
    if session is None:
        return frozenset()
    key = _ledger_cache_key(session)
    now = time.monotonic()
    if key is not None:
        cached = _LEDGER_SERIAL_CACHE.get(key)
        if cached is not None and now - cached[0] < _LEDGER_SERIAL_TTL_SECONDS:
            return cached[1]
    try:
        from sqlalchemy import text

        rows = session.execute(text("SELECT DISTINCT serial_no FROM v_record_detail")).all()
        serials = frozenset(
            str(row[0]).strip().casefold()
            for row in rows
            if row[0] is not None and str(row[0]).strip()
        )
    except Exception:  # noqa: BLE001 - thất bại DB thì bỏ qua tín hiệu sổ cái
        return frozenset()
    if key is not None:
        _LEDGER_SERIAL_CACHE[key] = (now, serials)
    return serials


def _question_serial_tokens(question: str) -> set[str]:
    return {
        token.casefold()
        for token in _SERIAL_TOKEN_RE.findall(question or "")
        if any(char.isdigit() for char in token)
    }


def looks_like_data_question(question: str, session: Any | None = None) -> bool:
    """True nếu câu hỏi có tín hiệu số liệu đáng để gọi LLM phân loại.

    Bốn mức, chỉ để mở/đóng cổng gọi LLM (không quyết định nhánh):
    1. từ khoá số liệu cũ (``_DATA_SIGNAL_RE``);
    2. token giống số hiệu đứng sau từ chỉ thiết bị (``_DEVICE_SERIAL_CONTEXT_RE``);
    3. từ khoá danh mục NAS (``_CATALOG_SIGNAL_RE``);
    4. token trùng số hiệu sổ cái hoặc số hiệu/ký hiệu chuẩn mẫu, mã quy trình
       trong view danh mục đã duyệt (nếu có ``session``).
    """
    text = question or ""
    if (
        _DATA_SIGNAL_RE.search(text)
        or _DEVICE_SERIAL_CONTEXT_RE.search(text)
        or _CATALOG_SIGNAL_RE.search(text)
    ):
        return True
    if session is not None:
        tokens = _question_serial_tokens(text)
        serials = ledger_serials(session)
        if serials and tokens & serials:
            return True
        catalog_tokens, catalog_codes, catalog_phrases = catalogs_query.catalog_signal_terms(
            session
        )
        if catalog_tokens and {fold(token) for token in tokens} & catalog_tokens:
            return True
        compact = re.sub(r"\s+", "", fold(text))
        if catalog_phrases and any(phrase in compact for phrase in catalog_phrases):
            return True
        if catalog_codes and any(code in compact for code in catalog_codes):
            return True
    return False


# ── Gỡ nhầm danh mục NAS (tất định, thất bại an toàn) ─────────────────────────
# LLM nhỏ hay nhầm CHUẨN MẪU với thiết bị cần kiểm (vì câu có "số hiệu"/"gần
# nhất") và nhầm danh mục quy trình với thông số QTKĐ. Các hiệu chỉnh dưới đây
# chỉ áp dụng khi có bằng chứng từ view danh mục đã duyệt; mọi lỗi DB bị nuốt để
# không đổi hành vi cũ và KHÔNG bao giờ tự mở nhánh số liệu từ ``text``.

_DEVICE_INTENTS: frozenset[str] = frozenset({"device_history", "latest_record", "error_trend"})
_NON_STANDARD_CATALOG_INTENTS: frozenset[str] = frozenset(
    {"procedure_catalog_lookup", "capability_lookup", "inspector_lookup"}
)
_DEVICE_TYPE_CUES_RE = re.compile(r"quy trình|tiêu chuẩn", re.IGNORECASE)
_GROUP_CUES_RE = re.compile(r"thuộc lĩnh vực|lĩnh vực|nhóm", re.IGNORECASE)
# Trích mã quy trình/tiêu chuẩn và tên thiết bị khi LLM bỏ trống tham số.
_CODE_RE = re.compile(
    r"(?:QTKĐ|QTKD|ĐLVN|DLVN|TCVN|TQSB)\s*[\d.]+(?:\s*[:\-]\s*\d{4})?", re.IGNORECASE
)
_PROC_IS_RE = re.compile(r"quy trình kiểm định\s+(.+?)\s+là gì", re.IGNORECASE)
_STD_IS_RE = re.compile(r"tiêu chuẩn\s+(.+?)\s+là gì", re.IGNORECASE)
_USAGE_REF_RE = re.compile(r"\b([IVXLC]+\.\d+)\b")
# Liệt kê chuẩn theo loại: "những áp kế píttông chuẩn nào" -> "áp kế píttông".
_STANDARD_TYPE_RE = re.compile(
    r"(?:những|các)\s+(.+?)\s+chuẩn(?:\s+mẫu)?\s+(?:nào|gì)\b", re.IGNORECASE
)
# Ranh giới Biểu 4 (danh mục quy trình) vs Biểu 1 (lĩnh vực công nhận).
_CAPABILITY_CUES_RE = re.compile(
    r"được công nhận|công nhận|chứng nhận|dải đo|cấp chính xác|"
    r"mấy kđv|bao nhiêu kđv|số kđv|bao nhiêu kiểm định viên|mấy kiểm định viên|"
    r"áp dụng quy trình nào|theo quy trình nào",
    re.IGNORECASE,
)
_PROC_IS_QUESTION_RE = re.compile(r"(?:quy trình|tiêu chuẩn)[^.?!]{0,60}là gì", re.IGNORECASE)
# Suy keyword lĩnh vực công nhận khi LLM chọn đúng intent nhưng bỏ trống tham số.
_CAPABILITY_RESCUE_RE = re.compile(
    r"(?:lĩnh vực|thiết bị|phương tiện|đại lượng)\s+(.+?)\s+"
    r"(?:được công nhận|áp dụng|theo quy trình|dải đo|cấp chính xác|mấy kđv|bao nhiêu)",
    re.IGNORECASE,
)
# Câu hỏi lần mới nhất/hạn dùng luôn thuộc latest_record, kể cả khi LLM chọn nhầm
# device_history (model nhỏ hay nhầm vì cùng có "số hiệu").
_LATEST_CUES_RE = re.compile(
    r"lần gần đây nhất|lần gần nhất|lần cuối|lần mới nhất|mới nhất|gần đây nhất|"
    r"khi nào hết hạn|hết hạn",
    re.IGNORECASE,
)


def _extract_code(question: str) -> str | None:
    match = _CODE_RE.search(question or "")
    if not match:
        return None
    return re.sub(r"\s*[:\-]\s*", ":", re.sub(r"\s+", " ", match.group(0))).strip()


def _rescue_procedure_catalog(question: str) -> dict[str, Any] | None:
    """Suy tham số danh mục quy trình khi LLM chọn đúng intent nhưng bỏ trống."""
    code = _extract_code(question)
    if code:
        return {"code": code}
    for pattern in (_PROC_IS_RE, _STD_IS_RE):
        match = pattern.search(question or "")
        if match:
            keyword = match.group(1).strip(" ,;")
            if keyword:
                return {"keyword": keyword}
    return None


def _rescue_lab_standard(
    question: str, phrases: frozenset[str] | set[str] = frozenset()
) -> dict[str, Any] | None:
    """Suy tham số chuẩn mẫu khi LLM chọn đúng intent nhưng bỏ trống."""
    match = _USAGE_REF_RE.search(question or "")
    if match:
        return {"usage_ref": match.group(1)}
    found = _match_standard_phrase(question, phrases)
    if found:
        return {"query": found}
    match = _STANDARD_TYPE_RE.search(question or "")
    if match:
        type_name = match.group(1).strip(" ,;")
        if type_name:
            return {"query": type_name}
    return None


def _rescue_capability(question: str) -> dict[str, Any] | None:
    """Suy keyword lĩnh vực công nhận khi LLM chọn đúng intent nhưng bỏ trống."""
    match = _CAPABILITY_RESCUE_RE.search(question or "")
    if not match:
        return None
    keyword = match.group(1).strip(" ,;")
    return {"keyword": keyword} if keyword else None


def _match_standard_phrase(question: str, phrases: frozenset[str] | set[str]) -> str | None:
    """Tìm cụm ký hiệu/model chuẩn mẫu (đã bỏ dấu, gộp khoảng trắng) trong câu hỏi."""
    if not phrases:
        return None
    compact = re.sub(r"\s+", "", fold(question or ""))
    matches = [phrase for phrase in phrases if phrase and phrase in compact]
    if not matches:
        return None
    return max(matches, key=len)


def _standard_values(
    params: dict[str, Any], tokens: frozenset[str], phrases: frozenset[str]
) -> list[str]:
    """Giá trị tham số trùng số hiệu/ký hiệu chuẩn mẫu đã duyệt, giữ thứ tự khoá."""
    values: list[str] = []
    for key in ("device_type", "serial", "query"):
        value = str(params.get(key) or "").strip()
        if value and (fold(value) in tokens or _match_standard_phrase(value, phrases)):
            values.append(value)
    return values


def disambiguate_catalogs(
    payload: dict[str, Any] | None, question: str, session: Any | None
) -> dict[str, Any] | None:
    """Hiệu chỉnh intent khi bằng chứng danh mục đã duyệt mâu thuẫn với lựa chọn LLM.

    Chỉ đổi giữa các intent số liệu (không bao giờ tự mở nhánh số liệu từ ``text``),
    nên câu hỏi văn bản vẫn đi thẳng pipeline RAG. Khi LLM chọn đúng intent danh mục
    nhưng bỏ trống tham số (thường gặp ở model nhỏ), tham số được suy từ câu hỏi.
    """
    if not isinstance(payload, dict) or session is None:
        return payload
    if str(payload.get("branch") or "") not in ("data", "mixed"):
        return payload
    intent = str(payload.get("intent") or "").strip().lower()
    params = dict(payload.get("params") or {})
    try:
        tokens, codes, phrases = catalogs_query.catalog_signal_terms(session)
    except Exception:  # noqa: BLE001 - thất bại DB thì giữ nguyên quyết định LLM
        return payload

    def override(new_intent: str, new_params: dict[str, Any]) -> dict[str, Any]:
        return {
            **payload,
            "branch": "data",
            "intent": new_intent,
            "params": new_params,
            "confidence": payload.get("confidence", 0.9),
        }

    # Mục sử dụng của Biểu 1 ("mục VI.1") chỉ có ở danh mục chuẩn mẫu.
    usage_ref = str(params.get("usage_ref") or "").strip()
    if usage_ref and intent != "lab_standard_lookup":
        return override("lab_standard_lookup", {"usage_ref": usage_ref})

    # "Phòng có những <loại> chuẩn nào" là câu liệt kê chuẩn mẫu, không phải danh
    # mục quy trình/lĩnh vực; tên loại lấy nguyên văn từ câu hỏi. Chỉ sửa giữa các
    # danh mục NAS: "QTKĐ X dùng những phương tiện chuẩn nào" vẫn là standards_for.
    type_match = _STANDARD_TYPE_RE.search(question or "")
    if type_match and intent in _NON_STANDARD_CATALOG_INTENTS:
        type_name = type_match.group(1).strip(" ,;")
        if type_name:
            return override("lab_standard_lookup", {"query": type_name})

    # Ranh giới Biểu 4 vs Biểu 1: câu nêu "được công nhận", "dải đo", "mấy KĐV",
    # "áp dụng quy trình nào" mà không có mã quy trình -> lĩnh vực công nhận.
    if (
        intent in ("procedure_catalog_lookup", "capability_lookup")
        and _CAPABILITY_CUES_RE.search(question or "")
        and not params.get("code")
        and not _CODE_RE.search(question or "")
    ):
        keyword = str(params.get("keyword") or params.get("group") or "").strip()
        if not keyword:
            rescued = _rescue_capability(question)
            keyword = str(rescued.get("keyword") or "") if rescued else ""
        if keyword:
            return override("capability_lookup", {"keyword": keyword})
        return payload

    if intent == "procedure_catalog_lookup" and not params:
        rescued = _rescue_procedure_catalog(question)
        if rescued:
            return override("procedure_catalog_lookup", rescued)
        return payload
    if intent == "lab_standard_lookup" and not params:
        rescued = _rescue_lab_standard(question, phrases)
        if rescued:
            return override("lab_standard_lookup", rescued)
        return payload
    if intent == "capability_lookup" and not params:
        rescued = _rescue_capability(question)
        if rescued:
            return override("capability_lookup", rescued)
        return payload

    if intent == "device_history" and _LATEST_CUES_RE.search(question or ""):
        return override("latest_record", params)

    if intent in _DEVICE_INTENTS:
        serial = str(params.get("serial") or "").strip()
        if serial and (fold(serial) in tokens or _match_standard_phrase(serial, phrases)):
            return override("lab_standard_lookup", {"query": serial})
        return payload

    if intent in ("procedure_params", "standards_for"):
        number = str(params.get("procedure_number") or "").strip()
        # "Chuẩn Fluke 7302 số 1274 có phạm vi đo..." : LLM hay coi ký hiệu chuẩn là
        # loại thiết bị của QTKĐ. Chỉ chuyển khi không nêu số QTKĐ.
        standard_values = _standard_values(params, tokens, phrases)
        if standard_values and not number:
            return override("lab_standard_lookup", {"query": " ".join(standard_values)})
        if not number and (ref_match := _USAGE_REF_RE.search(question or "")):
            return override("lab_standard_lookup", {"usage_ref": ref_match.group(1)})
        if number:
            try:
                kho = catalogs_query.kho_procedure_numbers(session)
            except Exception:  # noqa: BLE001 - thiếu DB thì giữ nguyên
                return payload
            if number.casefold() in codes and number.casefold() not in kho:
                return override("procedure_catalog_lookup", {"code": number})
            return payload
        device_type = str(params.get("device_type") or "").strip()
        if not device_type:
            return payload
        if _GROUP_CUES_RE.search(question or ""):
            return override(
                "procedure_catalog_lookup", {"group": device_type, "keyword": device_type}
            )
        try:
            kho_devices = catalogs_query.kho_device_types(session)
        except Exception:  # noqa: BLE001 - thiếu DB thì giữ nguyên
            return payload
        if _DEVICE_TYPE_CUES_RE.search(question or "") and fold(device_type) not in kho_devices:
            return override("procedure_catalog_lookup", {"keyword": device_type})
    # Hỏi một quy trình/tiêu chuẩn "là gì" -> danh mục quy trình (Biểu 4).
    if intent == "capability_lookup" and _PROC_IS_QUESTION_RE.search(question or ""):
        keyword = str(params.get("keyword") or "").strip()
        if keyword:
            return override("procedure_catalog_lookup", {"keyword": keyword})
        return payload
    return payload
