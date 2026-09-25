"""Ghi hồ sơ + số liệu đo vào sổ cái qua hàng đợi duyệt (spec §5.5, §9 S7).

Mỗi lần đọc hồ sơ sinh MỘT ``extraction`` ở trạng thái ``pending`` (P3). Hồ sơ và
số liệu đo chỉ lộ ra qua ``v_calibration_record``/``v_measurement_point`` sau khi
người duyệt chấp nhận. Nạp lại hồ sơ chuyển extraction cũ sang ``superseded``
chứ không xóa — lịch sử duyệt là dữ liệu nghiệp vụ.

Hai bất biến:

- **P2**: giá trị đo và ``error_value`` đọc nguyên trạng từ ``MeasurementDraft``.
  Hàm duy nhất được tính là ``expires_at`` (hạn hiệu lực), dẫn xuất từ dữ kiện
  chu kỳ ĐÃ DUYỆT và luôn lưu ``expires_from_fact_id`` trỏ về dữ kiện nguồn.
- **P1**: ``extraction.quote`` giữ nguyên văn hồ sơ; mỗi số liệu đo giữ ``quote``
  và ``*_text`` của chính dòng nguồn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from db.models import (
    CalibrationRecord,
    Document,
    Extraction,
    ExtractionStatus,
    MeasurementPoint,
    Procedure,
    Unit,
)
from knowledge import units as units_module
from knowledge import vnnum
from knowledge.record_labels import HEADER_ALIASES as _HEADER_ALIASES
from query import approved as approved_query
from records.matching import find_or_create_device
from records.types import MeasurementDraft, RecordDraft

EXTRACTOR_VERSION = "v1"
DEFAULT_CONFIDENCE = 0.9

_MODE_ALIASES = {
    "ban_dau": "ban_dau",
    "ban đầu": "ban_dau",
    "đầu": "ban_dau",
    "dinh_ky": "dinh_ky",
    "định kỳ": "dinh_ky",
    "sau_sua_chua": "sau_sua_chua",
    "sau sửa chữa": "sau_sua_chua",
}
# Phủ định xét trước để "không đạt" không bị "đạt" cắt mất.
_VERDICT_ALIASES = {
    "khong_dat": "khong_dat",
    "không đạt": "khong_dat",
    "khong dat": "khong_dat",
    "dat": "dat",
    "đạt": "dat",
}
_INTERVAL_RE = re.compile(r"(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>tháng|năm)", re.IGNORECASE)


class StoreError(ValueError):
    """Không ghi được hồ sơ (thiếu tài liệu, cấu hình sai…)."""


@dataclass
class StoreResult:
    """Tổng kết một lần ghi hồ sơ."""

    record_id: int | None = None
    extraction_id: int | None = None
    device_id: int | None = None
    measurement_points: int = 0
    superseded: int = 0
    needs_identification: bool = False
    expires_at: datetime | None = None
    expires_from_fact_id: int | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "extraction_id": self.extraction_id,
            "device_id": self.device_id,
            "measurement_points": self.measurement_points,
            "superseded": self.superseded,
            "needs_identification": self.needs_identification,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "expires_from_fact_id": self.expires_from_fact_id,
            "warnings": list(self.warnings),
        }


def _lookup(header: dict[str, str], field_name: str) -> str | None:
    for alias in _HEADER_ALIASES.get(field_name, ()):  # pragma: no branch
        value = header.get(vnnum.normalize_spaces(alias).casefold())
        if value:
            return value
    return None


def _parse_temperature(text: str | None) -> float | None:
    """Số đầu tiên trong chuỗi (nhiệt độ "(20 ± 5)" → 20)."""
    if not text:
        return None
    numbers = vnnum.numbers(text)
    return numbers[0] if numbers else None


def _parse_mode(text: str | None) -> str | None:
    if not text:
        return None
    return _MODE_ALIASES.get(vnnum.normalize_spaces(text).casefold())


def _parse_verdict(text: str | None) -> str | None:
    if not text:
        return None
    normalized = vnnum.normalize_spaces(text).casefold()
    for alias, value in _VERDICT_ALIASES.items():
        if normalized == alias:
            return value
    # K04: "Đạt (không đạt) yêu cầu" / "Đạt/Không đạt" là câu mẫu mập mờ: có cả
    # một "đạt" độc lập lẫn một "không đạt" -> không kết luận được.
    negative = "không đạt" in normalized or "khong dat" in normalized
    remainder = normalized.replace("không đạt", "").replace("khong dat", "")
    positive = "đạt" in remainder or "dat" in remainder
    if negative and positive:
        return None
    if negative:
        return "khong_dat"
    if positive:
        return "dat"
    return None


_ISO_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DATE_RE = re.compile(r"(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{2,4})")
_DATE_VI_RE = re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.IGNORECASE)


def parse_date(text: str | None) -> datetime | None:
    """Phân tích ngày kiểu Việt (``20/01/2024`` hoặc ``ngày 20 tháng 1 năm 2024``).

    K05: nhận ``YYYY-MM-DD`` (nhóm đầu 4 chữ số là năm) TRƯỚC các mẫu khác, nếu
    không "2026-04-10" sẽ bị đọc nhầm theo mẫu D/M/Y.
    """
    if not text:
        return None
    iso = _ISO_DATE_RE.search(text)
    if iso:
        year, month, day = (int(part) for part in iso.groups())
        try:
            return datetime(year, month, day)
        except ValueError:
            return None
    match = _DATE_VI_RE.search(text) or _DATE_RE.search(text)
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    if year < 100:
        year += 2000
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _add_months(moment: datetime, months: int) -> datetime:
    """Cộng ``months`` tháng, giữ ngày (kẹp về ngày cuối tháng khi cần)."""
    month_index = moment.month - 1 + months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    day = moment.day
    while day > 0:
        try:
            return moment.replace(year=year, month=month, day=day)
        except ValueError:
            day -= 1
    return moment.replace(year=year, month=month, day=1)


def interval_months(value_text: str | None) -> int | None:
    """Số tháng của một dữ kiện chu kỳ (``12 tháng`` → 12, ``01 năm`` → 12)."""
    if not value_text:
        return None
    match = _INTERVAL_RE.search(value_text)
    if match:
        number = vnnum.parse_number(match.group("num"))
        if number is None:
            return None
        months = int(round(number))
        if match.group("unit").casefold() == "năm":
            months *= 12
        return months if months > 0 else None
    # Dự phòng: chuỗi chỉ có số (đã chuẩn hóa về tháng).
    number = vnnum.parse_number(value_text)
    if number is None:
        return None
    months = int(round(number))
    return months if months > 0 else None


def derive_expiry(
    db: Session,
    *,
    procedure_id: int | None,
    calibrated_at: datetime | None,
) -> tuple[datetime | None, int | None]:
    """Tính ``expires_at`` từ dữ kiện chu kỳ ĐÃ DUYỆT gần nhất (ngoại lệ P2).

    Chỉ đọc ``v_procedure_fact`` (P3). Trả ``(expires_at, fact_id)``; không có dữ
    kiện chu kỳ đã duyệt hoặc không phân tích được → ``(None, None)``. Không bao
    giờ lấy chu kỳ từ dữ kiện ``pending``.
    """
    if procedure_id is None or calibrated_at is None:
        return None, None
    rows = approved_query.list_approved_facts(
        db,
        procedure_id=procedure_id,
        fact_kind="calibration_interval",
        limit=100,
    )
    # Dữ kiện mới nhất (id lớn nhất) là chu kỳ đang hiệu lực.
    for row in sorted(rows, key=lambda item: int(item["id"]), reverse=True):
        months = interval_months(row.get("value_text"))
        if months is None:
            continue
        return _add_months(calibrated_at, months), int(row["id"])
    return None, None


def _supersede_previous(session: Session, document: Document) -> int:
    """Chuyển extraction hồ sơ cũ của tài liệu sang ``superseded``; trả số dòng."""
    previous = (
        session.query(Extraction)
        .filter(
            Extraction.document_id == document.id,
            Extraction.extractor.like("record:%"),
            Extraction.status.in_((ExtractionStatus.PENDING, ExtractionStatus.APPROVED)),
        )
        .all()
    )
    for row in previous:
        row.status = ExtractionStatus.SUPERSEDED
    return len(previous)


def _resolve_unit_id(session: Session, unit_text: str | None) -> int | None:
    if not unit_text:
        return None
    unit_defs = units_module.load_unit_defs(session)
    unit_def = units_module.resolve_unit(unit_text, unit_defs)
    if unit_def is None:
        return None
    row = session.query(Unit).filter(Unit.code == unit_def.code).one_or_none()
    return row.id if row is not None else None


def _working_range_unit_id(session: Session, procedure: Procedure | None) -> int | None:
    """Đơn vị của dữ kiện ``working_range`` ĐÃ DUYỆT gần nhất của QTKĐ (K09).

    Dùng làm đơn vị mặc định cho điểm đo khi tiêu đề cột không ghi đơn vị. Chỉ
    đọc ``v_procedure_fact`` (P3); trả ``None`` nếu không có dữ kiện nào có đơn vị.
    """
    if procedure is None:
        return None
    rows = approved_query.list_approved_facts(
        session,
        procedure_id=procedure.id,
        fact_kind="working_range",
        limit=100,
    )
    for row in sorted(rows, key=lambda item: int(item["id"]), reverse=True):
        unit_id = row.get("unit_id")
        if unit_id is not None:
            return int(unit_id)
    return None


def _measurement_row(
    draft: MeasurementDraft, *, unit_id: int | None, record_id: int | None = None
) -> MeasurementPoint:
    """Ánh xạ bản nháp sang bản ghi; KHÔNG tính lại bất kỳ số liệu nào (P2)."""
    within_limit: int | None = None
    if draft.error_value is not None and draft.limit_value is not None:
        within_limit = 1 if abs(draft.error_value) <= abs(draft.limit_value) else 0
    return MeasurementPoint(
        record_id=record_id,
        ord=draft.ord,
        step_code=draft.step_code,
        label=draft.label,
        nominal_value=draft.nominal_value,
        measured_value=draft.measured_value,
        error_value=draft.error_value,
        unit_id=unit_id,
        limit_value=draft.limit_value,
        within_limit=within_limit,
        note=draft.note,
        quote=draft.quote or None,
        nominal_text=draft.nominal_text,
        measured_text=draft.measured_text,
        error_text=draft.error_text,
        limit_text=draft.limit_text,
    )


def store_record_draft(
    session: Session,
    *,
    document: Document,
    draft: RecordDraft,
    procedure: Procedure | None = None,
    supersede: bool = True,
) -> StoreResult:
    """Ghi một ``RecordDraft`` thành hồ sơ + số liệu đo ở trạng thái ``pending``.

    Không commit; tầng gọi quyết định. Hồ sơ mới luôn gắn một ``extraction``
    ``pending`` nên P3 giữ nguyên cho tới khi người duyệt chấp nhận.
    """
    if document is None:
        raise StoreError("Thiếu tài liệu để gắn hồ sơ.")

    result = StoreResult(warnings=list(draft.warnings))
    if supersede:
        result.superseded = _supersede_previous(session, document)

    quote = draft.source_text.strip() or draft.section_path or "(hồ sơ không có văn bản)"
    extraction = Extraction(
        document_id=document.id,
        section_path=draft.section_path,
        quote=quote,
        extractor=draft.extractor,
        extractor_version=EXTRACTOR_VERSION,
        confidence=DEFAULT_CONFIDENCE,
        status=ExtractionStatus.PENDING,
    )
    session.add(extraction)
    session.flush()
    result.extraction_id = extraction.id

    header = draft.header_map()
    serial_no = _lookup(header, "serial_no")
    device = find_or_create_device(
        session,
        device_type_id=procedure.device_type_id if procedure is not None else None,
        serial_no=serial_no,
        model_code=_lookup(header, "model_code"),
        manufacturer=_lookup(header, "manufacturer"),
        owner_org=_lookup(header, "owner_org"),
    )
    result.device_id = device.id
    result.needs_identification = bool(device.needs_identification)
    if device.needs_identification:
        result.warnings.append("Hồ sơ thiếu số hiệu — thiết bị cần nhận dạng lại.")

    calibrated_at = parse_date(_lookup(header, "calibrated_at"))
    expires_at, expires_from_fact_id = derive_expiry(
        session,
        procedure_id=procedure.id if procedure is not None else None,
        calibrated_at=calibrated_at,
    )
    result.expires_at = expires_at
    result.expires_from_fact_id = expires_from_fact_id

    record = CalibrationRecord(
        document_id=document.id,
        extraction_id=extraction.id,
        device_id=device.id,
        procedure_id=procedure.id if procedure is not None else None,
        mode=_parse_mode(_lookup(header, "mode")),
        calibrated_at=calibrated_at,
        expires_at=expires_at,
        expires_from_fact_id=expires_from_fact_id,
        verdict=_parse_verdict(_lookup(header, "verdict")),
        cert_no=_lookup(header, "cert_no"),
        inspector_name=_lookup(header, "inspector_name"),
        reviewer_name=_lookup(header, "reviewer_name"),
        lab_name=_lookup(header, "lab_name"),
        env_temp_c=_parse_temperature(_lookup(header, "env_temp_c")),
        env_humidity_pct=_parse_temperature(_lookup(header, "env_humidity_pct")),
        source_text=draft.source_text or None,
    )
    session.add(record)
    session.flush()
    result.record_id = record.id

    for draft_point in draft.measurements:
        # K09: đơn vị ưu tiên từ tiêu đề cột; không có thì lấy đơn vị working_range.
        if draft_point.unit_text:
            unit_id = _resolve_unit_id(session, draft_point.unit_text)
        else:
            unit_id = _working_range_unit_id(session, procedure)
        session.add(_measurement_row(draft_point, unit_id=unit_id, record_id=record.id))
        result.measurement_points += 1

    session.flush()
    return result
