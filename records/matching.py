"""Đối sánh thiết bị theo loại + serial (spec §5.5, Sprint 7).

Khóa nhận dạng thiết bị là cặp ``(device_type_id, serial_no)``. Hai quy tắc bắt
buộc của sprint:

- **Không gộp nhầm hai serial khác nhau**: khóa gồm cả ``serial_norm`` nên hai
  số hiệu khác nhau luôn là hai thiết bị.
- **Không tách đôi cùng một serial viết khác kiểu hoa/thường**: ``serial_norm``
  bỏ khoảng trắng thừa và hạ hoa/thường trước khi so.

Thiếu serial → tạo thiết bị tạm mới gắn ``needs_identification=1`` mỗi lần, thay
vì gộp tất cả hồ sơ không số hiệu vào một thiết bị. Mỗi hồ sơ thiếu serial là
một nghi vấn nhận dạng riêng cần người xử lý.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from db.models import Device
from knowledge import vnnum


def normalize_serial(serial_no: str | None) -> str | None:
    """Chuẩn hóa serial để đối sánh: bỏ khoảng trắng thừa, hạ hoa/thường.

    Trả ``None`` khi serial rỗng/không có — tín hiệu để tạo thiết bị tạm.
    """
    if serial_no is None:
        return None
    text = vnnum.normalize_spaces(str(serial_no)).strip()
    if not text:
        return None
    return text.casefold()


def find_device(
    db: Session, *, device_type_id: int | None, serial_no: str | None
) -> Device | None:
    """Tìm thiết bị theo loại + serial đã chuẩn hóa; ``None`` nếu thiếu serial."""
    norm = normalize_serial(serial_no)
    if norm is None:
        return None
    return (
        db.query(Device)
        .filter(Device.device_type_id == device_type_id, Device.serial_norm == norm)
        .one_or_none()
    )


def find_or_create_device(
    db: Session,
    *,
    device_type_id: int | None,
    serial_no: str | None,
    model_code: str | None = None,
    manufacturer: str | None = None,
    owner_org: str | None = None,
    attrs: dict | None = None,
) -> Device:
    """Trả thiết bị khớp ``(loại, serial)`` hoặc tạo mới.

    Có serial: tìm theo ``serial_norm`` (hoa/thường không phân biệt); thấy thì
    trả luôn, chưa thấy thì tạo. Không serial: LUÔN tạo thiết bị tạm mới gắn cờ
    ``needs_identification`` (không gộp nhầm hai thiết bị khác nhau).
    """
    serial_norm = normalize_serial(serial_no)
    if serial_norm is not None:
        existing = find_device(db, device_type_id=device_type_id, serial_no=serial_no)
        if existing is not None:
            # Bổ sung thông tin nhận dạng còn thiếu nhưng không ghi đè dữ liệu có sẵn.
            if model_code and not existing.model_code:
                existing.model_code = model_code
            if manufacturer and not existing.manufacturer:
                existing.manufacturer = manufacturer
            if owner_org and not existing.owner_org:
                existing.owner_org = owner_org
            return existing

    device = Device(
        device_type_id=device_type_id,
        serial_no=vnnum.normalize_spaces(serial_no).strip() if serial_no else None,
        serial_norm=serial_norm,
        model_code=model_code,
        manufacturer=manufacturer,
        owner_org=owner_org,
        attrs=attrs or {},
        needs_identification=0 if serial_norm is not None else 1,
    )
    db.add(device)
    db.flush()
    return device
