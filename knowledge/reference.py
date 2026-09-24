"""Truy vấn chỉ-đọc trên khung khái niệm đo lường đã seed (spec §5.1).

Không ghi, không quy đổi — chỉ gom dữ liệu DB thành ánh xạ tiện dụng cho router
định tuyến và cho tầng trích xuất về sau.
"""

from __future__ import annotations

from knowledge import vnnum


def normalize_alias(text: str | None) -> str:
    """Chuẩn hóa alias để so khớp: thường hóa + gộp khoảng trắng (gồm NBSP)."""
    return vnnum.normalize_spaces(text).lower()


def device_type_aliases(device_type) -> list[str]:
    """Tên loại + alias đã chuẩn hóa, khử trùng lặp, giữ thứ tự."""
    values = [device_type.name_vi, *device_type.alias_list()]
    result: list[str] = []
    for value in values:
        normalized = normalize_alias(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def load_quantities(session) -> list:
    from db.models import Quantity

    return session.query(Quantity).order_by(Quantity.id).all()


def load_units(session) -> list:
    from db.models import Unit

    return session.query(Unit).order_by(Unit.id).all()


def load_device_types(session) -> list:
    from db.models import DeviceType

    return session.query(DeviceType).order_by(DeviceType.id).all()


def device_alias_map(session) -> dict[str, tuple[str, ...]]:
    """alias thiết bị → các số QTKĐ, dựng từ ``device_type`` + ``procedure``.

    Một alias có thể trỏ tới nhiều QTKĐ (cùng loại thiết bị, nhiều quy trình);
    khi đó router coi là mơ hồ và rơi về tìm toàn kho, đúng nguyên tắc an toàn.
    """
    from db.models import Procedure

    result: dict[str, list[str]] = {}
    for procedure in session.query(Procedure).all():
        device_type = procedure.device_type
        if device_type is None or not procedure.number:
            continue
        for alias in device_type_aliases(device_type):
            numbers = result.setdefault(alias, [])
            if procedure.number not in numbers:
                numbers.append(procedure.number)
    return {alias: tuple(numbers) for alias, numbers in result.items()}


def procedure_by_number(session, number: str):
    from db.models import Procedure

    return session.query(Procedure).filter(Procedure.number == number).one_or_none()


def procedure_device_type_map(session) -> dict[str, str]:
    """Số QTKĐ → tên loại thiết bị (để đối chiếu/kiểm tra nhanh)."""
    from db.models import Procedure

    result: dict[str, str] = {}
    for procedure in session.query(Procedure).all():
        if procedure.device_type is not None:
            result[procedure.number] = procedure.device_type.name_vi
    return result
