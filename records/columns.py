"""Vai trò cột kết quả, đơn vị trong tiêu đề và số trong ô nguồn (spec §5.5).

Dùng chung cho bộ đọc Word và Excel. Mỗi cột của bảng kết quả được gán một vai
trò (``ord``, ``label``, ``nominal``, ``measured``, ``error``, ``limit``, ``env``,
``note``...) từ CHÍNH tên cột; cột không có vai trò vẫn được giữ trong ``note``.

Bất biến P2: mọi giá trị số chỉ là kết quả phân tích chuỗi của chính ô nguồn.
``cell_number`` chấp nhận dấu so sánh đứng trước (``≤ 30``, ``< 5'``) vì đó là cách
ghi giới hạn trong biên bản, nhưng không bao giờ tính một số từ ô khác.
"""

from __future__ import annotations

import re

from knowledge import vnnum
from records.types import MeasurementDraft

# Vai trò theo khớp CHÍNH XÁC slug tên cột.
_COLUMN_ROLES: dict[str, str] = {
    "lan_kiem_tra": "ord",
    "lan": "ord",
    "tt": "ord",
    "stt": "ord",
    "mo": "measured",
    "gia_tri_do": "measured",
    "ap_suat": "measured",
    "measured": "measured",
    "dong": "measured_secondary",
    "gia_tri_danh_nghia": "nominal",
    "danh_nghia": "nominal",
    "nominal": "nominal",
    "diem_do": "label",
    "diem_kiem_tra": "label",
    "sai_so": "error",
    "do_chenh_ap": "error",
    "sai_so_do": "error",
    "error": "error",
    "gioi_han": "limit",
    "sai_so_cho_phep": "limit",
    "limit": "limit",
    "ghi_chu": "note",
    "note": "note",
}

# Cột điều kiện môi trường từng dòng: là ngữ cảnh, không phải giá trị đo.
_ENV_HINTS = ("khi_quyen", "do_am", "nhiet_do_moi_truong", "moi_truong")
_LABEL_HINTS = ("diem_do", "diem_kiem_tra", "thong_so", "ten_ma_so")
_MEASURED_HINTS = ("thuc_te", "gia_tri_xac_dinh", "trung_binh", "ap_suat")

# Dấu so sánh đứng trước số giới hạn và dấu đơn vị dính sau số (phút góc, %...).
_LEADING_COMPARATOR_RE = re.compile(r"^\s*(?:<=|>=|[<>≤≥±~≈=])\s*")
_TRAILING_MARK_RE = re.compile(r"\s*['′\"″%°º]\s*$")
_UNIT_IN_PARENS_RE = re.compile(r"\(([^()]*)\)")
_UNIT_AFTER_COMMA_RE = re.compile(r",\s*([^,()]+?)\s*$")
_UNIT_EXTRA_CHARS = set("°ºµΩ%/·^-")


def slug(text: str) -> str:
    from records.template import slugify

    return slugify(text)


def cell_number(text: str | None) -> float | None:
    """Số trong MỘT ô nguồn; nhận ``≤ 30``, ``< 5'``, ``2'``; mơ hồ thì ``None``."""
    if not text:
        return None
    number = vnnum.parse_number(text)
    if number is not None:
        return number
    stripped = _TRAILING_MARK_RE.sub("", _LEADING_COMPARATOR_RE.sub("", text))
    if stripped == text.strip():
        return None
    return vnnum.parse_number(stripped)


def _looks_like_unit(candidate: str) -> bool:
    """Chuỗi ngắn, không khoảng trắng, không mở đầu bằng số, chỉ ký tự đơn vị."""
    text = candidate.strip()
    if not text or len(text) > 12 or any(char.isspace() for char in text):
        return False
    if text[0].isdigit():
        return False
    return all(char.isascii() or char in _UNIT_EXTRA_CHARS for char in text)


def unit_after_comma(text: str) -> str | None:
    """Đơn vị ở đuôi sau dấu phẩy cuối (``Độ giảm áp suất sau 5 min, kPa`` → ``kPa``)."""
    match = _UNIT_AFTER_COMMA_RE.search(vnnum.normalize_spaces(text or ""))
    if match and _looks_like_unit(match.group(1)):
        return match.group(1).strip()
    return None


def unit_from_header(column: str) -> str | None:
    """Đơn vị ở tiêu đề cột hoặc nhãn dòng: ``Giá trị đo (bar)``, ``Kết quả, s``.

    Xét đuôi sau dấu phẩy cuối trước, rồi tới nhóm ngoặc cuối cùng trông giống đơn
    vị. Không có → ``None`` để tầng gọi quyết định.
    """
    text = vnnum.normalize_spaces(column or "")
    unit = unit_after_comma(text)
    if unit:
        return unit
    for candidate in reversed(_UNIT_IN_PARENS_RE.findall(text)):
        if _looks_like_unit(candidate):
            return candidate.strip()
    return None


def _token_role(column_slug: str) -> str | None:
    """Vai trò theo từ khóa con; thứ tự xét quan trọng (giới hạn trước sai số)."""
    tokens = set(column_slug.split("_"))
    if {"lan", "tt", "stt"} & tokens or "lan_kiem_tra" in column_slug:
        return "ord"
    if "gioi_han" in column_slug or "cho_phep" in column_slug or "limit" in column_slug:
        return "limit"
    if "sai_so" in column_slug or "chenh_ap" in column_slug or "error" in column_slug:
        return "error"
    if "danh_nghia" in column_slug or "nominal" in column_slug:
        return "nominal"
    if any(hint in column_slug for hint in _ENV_HINTS):
        return "env"
    if "ghi_chu" in column_slug or "note" in column_slug:
        return "note"
    if any(hint in column_slug for hint in _LABEL_HINTS):
        return "label"
    if any(hint in column_slug for hint in _MEASURED_HINTS) or {"mo", "do", "measured"} & tokens:
        return "measured"
    return None


def role_for_column(column: str) -> str | None:
    """Suy vai trò của một cột từ tên cột (khớp chính xác rồi tới từ khóa con)."""
    column_slug = slug(column)
    if column_slug in _COLUMN_ROLES:
        return _COLUMN_ROLES[column_slug]
    return _token_role(column_slug)


def _apply_cell(
    draft: MeasurementDraft, role: str | None, column: str, text: str, extras: list[str]
) -> None:
    """Gán một ô vào bản nháp theo vai trò; ô đã có giá trị cùng vai trò thì vào ``note``."""
    if role == "ord":
        number = vnnum.parse_number(text)
        draft.ord = int(number) if number is not None else None
        if draft.label is None:
            draft.label = text or None
    elif role == "label" and text:
        draft.label = text
    elif role == "measured" and draft.measured_text is None:
        draft.measured_text = text or None
        draft.measured_value = cell_number(text)
        # K09: ưu tiên đơn vị trong tiêu đề cột giá trị.
        draft.unit_text = unit_from_header(column)
    elif role == "measured_secondary" and text:
        extras.append(f"{column}: {text}")
    elif role == "nominal" and draft.nominal_text is None:
        draft.nominal_text = text or None
        draft.nominal_value = cell_number(text)
    elif role == "error" and draft.error_text is None:
        # P2: chỉ đọc từ tài liệu; không suy ra từ measured/nominal.
        draft.error_text = text or None
        draft.error_value = cell_number(text)
        draft.error_unit_text = unit_from_header(column)
    elif role == "limit" and draft.limit_text is None:
        draft.limit_text = text or None
        draft.limit_value = cell_number(text)
    elif role == "note" and draft.note is None:
        draft.note = text or None
    elif text:
        extras.append(f"{column}={text}")


def map_measurement_row(columns: list[str], cells: list[str]) -> MeasurementDraft:
    """Ánh xạ một dòng dữ liệu sang ``MeasurementDraft``, giữ nguyên văn từng ô.

    Giá trị số chỉ được phân tích từ chính ô nguồn (P2). Cột không nhận vai trò
    nào được giữ trong ``note`` để không mất dữ liệu.
    """
    draft = MeasurementDraft(quote=" | ".join(cells))
    extras: list[str] = []
    for column, cell in zip(columns, cells, strict=False):
        _apply_cell(draft, role_for_column(column), column, cell.strip(), extras)
    if extras:
        draft.note = "; ".join(filter(None, [draft.note, *extras]))
    return draft
