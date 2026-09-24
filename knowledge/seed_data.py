"""Dữ liệu seed cho khung khái niệm đo lường (spec §5.1, §13).

Một nguồn sự thật duy nhất cho ``quantity``/``unit``/``device_type``: migration
003 dùng các hằng số dưới đây để seed lần đầu, còn ``scripts/seed_knowledge.py``
dùng ``seed_reference_data`` để seed/upsert lại (idempotent).

Đơn vị được seed đủ bốn nhóm bắt buộc: áp suất, nhiệt độ, độ ẩm, độ dài; thêm
khối lượng và thời gian vì corpus QTKĐ có dùng.
"""

from __future__ import annotations

# id tường minh để migration seed bằng bulk_insert và unit trỏ đúng quantity.
QUANTITIES: list[dict] = [
    {"id": 1, "code": "pressure", "name_vi": "Áp suất", "si_unit_code": "Pa"},
    {"id": 2, "code": "temperature", "name_vi": "Nhiệt độ", "si_unit_code": "K"},
    {"id": 3, "code": "humidity", "name_vi": "Độ ẩm", "si_unit_code": "%RH"},
    {"id": 4, "code": "length", "name_vi": "Độ dài", "si_unit_code": "m"},
    {"id": 5, "code": "mass", "name_vi": "Khối lượng", "si_unit_code": "kg"},
    {"id": 6, "code": "time", "name_vi": "Thời gian", "si_unit_code": "s"},
]

# factor_to_si / offset_to_si theo công thức si = factor * x + offset.
UNITS: list[dict] = [
    # ── Áp suất ──────────────────────────────────────────────────────────────
    {"id": 1, "code": "Pa", "name_vi": "pascal", "quantity_id": 1, "factor_to_si": 1.0, "offset_to_si": 0.0, "aliases": ["pa", "pascal", "n/m2"]},
    {"id": 2, "code": "kPa", "name_vi": "kilopascal", "quantity_id": 1, "factor_to_si": 1000.0, "offset_to_si": 0.0, "aliases": ["kpa", "kilopascal"]},
    {"id": 3, "code": "MPa", "name_vi": "megapascal", "quantity_id": 1, "factor_to_si": 1_000_000.0, "offset_to_si": 0.0, "aliases": ["mpa", "megapascal"]},
    {"id": 4, "code": "bar", "name_vi": "bar", "quantity_id": 1, "factor_to_si": 100_000.0, "offset_to_si": 0.0, "aliases": ["bar"]},
    {"id": 5, "code": "mbar", "name_vi": "milibar", "quantity_id": 1, "factor_to_si": 100.0, "offset_to_si": 0.0, "aliases": ["mbar", "milibar", "millibar"]},
    {"id": 6, "code": "hPa", "name_vi": "hectopascal", "quantity_id": 1, "factor_to_si": 100.0, "offset_to_si": 0.0, "aliases": ["hpa", "hectopascal"]},
    {"id": 7, "code": "psi", "name_vi": "psi", "quantity_id": 1, "factor_to_si": 6894.757293168, "offset_to_si": 0.0, "aliases": ["psi", "pound per square inch"]},
    {"id": 8, "code": "kgf/cm2", "name_vi": "kilôgam lực trên xentimét vuông", "quantity_id": 1, "factor_to_si": 98066.5, "offset_to_si": 0.0, "aliases": ["kgf/cm2", "kgf/cm²", "kg/cm2", "kg/cm²"]},
    {"id": 9, "code": "at", "name_vi": "atmosphere kỹ thuật", "quantity_id": 1, "factor_to_si": 98066.5, "offset_to_si": 0.0, "aliases": ["at", "atmosphere"]},
    {"id": 10, "code": "mmHg", "name_vi": "milimét thủy ngân", "quantity_id": 1, "factor_to_si": 133.322387415, "offset_to_si": 0.0, "aliases": ["mmhg", "torr", "milimét thủy ngân"]},
    {"id": 11, "code": "mmH2O", "name_vi": "milimét nước", "quantity_id": 1, "factor_to_si": 9.80665, "offset_to_si": 0.0, "aliases": ["mmh2o", "milimét nước"]},
    # ── Nhiệt độ ─────────────────────────────────────────────────────────────
    {"id": 12, "code": "K", "name_vi": "kelvin", "quantity_id": 2, "factor_to_si": 1.0, "offset_to_si": 0.0, "aliases": ["k", "kelvin"]},
    {"id": 13, "code": "°C", "name_vi": "độ Celsius", "quantity_id": 2, "factor_to_si": 1.0, "offset_to_si": 273.15, "aliases": ["°c", "oc", "o c", "độ c", "celsius", "c"]},
    {"id": 14, "code": "°F", "name_vi": "độ Fahrenheit", "quantity_id": 2, "factor_to_si": 0.5555555555555556, "offset_to_si": 255.3722222222222, "aliases": ["°f", "of", "fahrenheit"]},
    # ── Độ ẩm ────────────────────────────────────────────────────────────────
    {"id": 15, "code": "%RH", "name_vi": "phần trăm độ ẩm tương đối", "quantity_id": 3, "factor_to_si": 1.0, "offset_to_si": 0.0, "aliases": ["%rh", "% rh", "rh", "độ ẩm tương đối"]},
    # ── Độ dài ───────────────────────────────────────────────────────────────
    {"id": 16, "code": "m", "name_vi": "mét", "quantity_id": 4, "factor_to_si": 1.0, "offset_to_si": 0.0, "aliases": ["m", "mét", "met"]},
    {"id": 17, "code": "dm", "name_vi": "đềximét", "quantity_id": 4, "factor_to_si": 0.1, "offset_to_si": 0.0, "aliases": ["dm", "đềximét"]},
    {"id": 18, "code": "cm", "name_vi": "xentimét", "quantity_id": 4, "factor_to_si": 0.01, "offset_to_si": 0.0, "aliases": ["cm", "xentimét"]},
    {"id": 19, "code": "mm", "name_vi": "milimét", "quantity_id": 4, "factor_to_si": 0.001, "offset_to_si": 0.0, "aliases": ["mm", "milimét"]},
    {"id": 20, "code": "µm", "name_vi": "micrômét", "quantity_id": 4, "factor_to_si": 0.000001, "offset_to_si": 0.0, "aliases": ["µm", "μm", "um", "micrômét", "micron"]},
    {"id": 21, "code": "km", "name_vi": "kilômét", "quantity_id": 4, "factor_to_si": 1000.0, "offset_to_si": 0.0, "aliases": ["km", "kilômét"]},
    # ── Khối lượng ───────────────────────────────────────────────────────────
    {"id": 22, "code": "kg", "name_vi": "kilôgam", "quantity_id": 5, "factor_to_si": 1.0, "offset_to_si": 0.0, "aliases": ["kg", "kilôgam"]},
    {"id": 23, "code": "g", "name_vi": "gam", "quantity_id": 5, "factor_to_si": 0.001, "offset_to_si": 0.0, "aliases": ["g", "gam"]},
    {"id": 24, "code": "mg", "name_vi": "miligam", "quantity_id": 5, "factor_to_si": 0.000001, "offset_to_si": 0.0, "aliases": ["mg", "miligam"]},
    # ── Thời gian ────────────────────────────────────────────────────────────
    {"id": 25, "code": "s", "name_vi": "giây", "quantity_id": 6, "factor_to_si": 1.0, "offset_to_si": 0.0, "aliases": ["s", "giây", "sec"]},
    {"id": 26, "code": "min", "name_vi": "phút", "quantity_id": 6, "factor_to_si": 60.0, "offset_to_si": 0.0, "aliases": ["min", "phút"]},
    {"id": 27, "code": "h", "name_vi": "giờ", "quantity_id": 6, "factor_to_si": 3600.0, "offset_to_si": 0.0, "aliases": ["h", "giờ", "hr"]},
]

# Loại phương tiện đo. Alias ở đây thay thế `_DEVICE_ALIASES` hardcode trong
# retrieval/router.py; tên loại cũng được coi là một alias khi định tuyến.
DEVICE_TYPES: list[dict] = [
    {"id": 1, "name_vi": "Van an toàn", "aliases": ["van an toàn", "van an toan"], "quantity_id": 1},
    {"id": 2, "name_vi": "Bàn tạo áp", "aliases": ["bàn tạo áp", "ban tao ap"], "quantity_id": 1},
    {"id": 3, "name_vi": "Bình phân ly", "aliases": ["bình phân ly", "binh phan ly"], "quantity_id": 1},
    {"id": 4, "name_vi": "Áp kế píttông kiểu H3000", "aliases": ["h3000", "h3000-sp", "áp kế píttông kiểu h3000", "áp kế pít tông kiểu h3000", "áp kế píttông h3000"], "quantity_id": 1},
    {"id": 5, "name_vi": "Áp kế píttông tiêu chuẩn", "aliases": ["áp kế píttông tiêu chuẩn", "áp kế pittông tiêu chuẩn", "pittông áp kế", "píttông áp kế"], "quantity_id": 1},
    {"id": 6, "name_vi": "Thiết bị đo áp suất số", "aliases": ["thiết bị đo áp suất số", "akkđ", "akkd"], "quantity_id": 1},
    {"id": 7, "name_vi": "Thiết bị hiệu chuẩn áp suất", "aliases": ["dpi 610", "dpi610", "thiết bị hiệu chuẩn áp suất"], "quantity_id": 1},
]

# Ánh xạ QTKĐ đang có → tên loại thiết bị (khớp `DEVICE_TYPES.name_vi`). Dùng làm
# phương án dự phòng xác định cho script sinh procedure khi suy luận từ tiêu đề
# không đủ rõ; QTKĐ mới có thể thêm dòng ở đây hoặc sửa nhãn qua DB.
KNOWN_PROCEDURE_DEVICE_TYPES: dict[str, str] = {
    "1.061": "Van an toàn",
    "1.062": "Bàn tạo áp",
    "1.063": "Bình phân ly",
    "1.071": "Áp kế píttông kiểu H3000",
    "1.159": "Áp kế píttông tiêu chuẩn",
    "1.160": "Thiết bị đo áp suất số",
    "1.190": "Thiết bị hiệu chuẩn áp suất",
}


def seed_reference_data(session) -> dict[str, int]:
    """Upsert quantity/unit/device_type theo ``code``/``name_vi``; trả số dòng mỗi bảng."""
    from db.models import DeviceType, Quantity, Unit

    for row in QUANTITIES:
        obj = session.query(Quantity).filter(Quantity.code == row["code"]).one_or_none()
        if obj is None:
            obj = Quantity(code=row["code"])
            session.add(obj)
        obj.name_vi = row["name_vi"]
        obj.si_unit_code = row["si_unit_code"]

    for row in UNITS:
        obj = session.query(Unit).filter(Unit.code == row["code"]).one_or_none()
        if obj is None:
            obj = Unit(code=row["code"])
            session.add(obj)
        obj.name_vi = row["name_vi"]
        obj.quantity_id = row["quantity_id"]
        obj.factor_to_si = row["factor_to_si"]
        obj.offset_to_si = row["offset_to_si"]
        obj.aliases = list(row["aliases"])

    for row in DEVICE_TYPES:
        obj = session.query(DeviceType).filter(DeviceType.name_vi == row["name_vi"]).one_or_none()
        if obj is None:
            obj = DeviceType(name_vi=row["name_vi"])
            session.add(obj)
        obj.aliases = list(row["aliases"])
        obj.quantity_id = row["quantity_id"]

    session.flush()
    return {
        "quantity": len(QUANTITIES),
        "unit": len(UNITS),
        "device_type": len(DEVICE_TYPES),
    }
