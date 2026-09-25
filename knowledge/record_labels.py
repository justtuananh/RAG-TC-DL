"""Nhãn đầu mục hồ sơ kiểm định dùng chung (spec §5.5).

Bảng alias nhãn (đã chuẩn hoá hoa/thường) → trường hồ sơ. Nhiều biến thể vì mỗi
mẫu biên bản đặt tên hơi khác nhau; không khớp thì bỏ qua, không đoán.

Đặt ở ``knowledge/`` để lớp luật (``knowledge.rules.phuluc_a``) nhận diện được
nhãn Phụ lục A mà không phải import ``records``; ``records.store`` import lại
chính bảng này.
"""

from __future__ import annotations

HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "serial_no": ("số hiệu", "số serial", "serial", "số máy", "số hiệu phương tiện"),
    "model_code": ("ký hiệu", "model", "ký hiệu/model"),
    "manufacturer": (
        "nơi (hãng) sản xuất",
        "nơi sản xuất",
        "hãng sản xuất",
        "nhà sản xuất",
    ),
    "owner_org": ("đơn vị sử dụng", "cơ sở sử dụng", "đơn vị quản lý"),
    "cert_no": ("số giấy chứng nhận", "số chứng nhận", "giấy chứng nhận số"),
    "inspector_name": ("người kiểm định", "kiểm định viên", "người thực hiện"),
    "reviewer_name": ("người soát lại", "người duyệt", "người soát xét"),
    "lab_name": (
        "phòng đo lường",
        "đơn vị kiểm định",
        "phòng thí nghiệm",
        "đơn vị thực hiện",
    ),
    "calibrated_at": ("ngày kiểm định", "ngày thực hiện"),
    "mode": ("chế độ kiểm định", "chế độ"),
    "verdict": ("kết luận",),
    "env_temp_c": ("nhiệt độ", "nhiệt độ môi trường"),
    "env_humidity_pct": ("độ ẩm", "độ ẩm môi trường"),
}


def all_labels() -> tuple[str, ...]:
    """Mọi nhãn hồ sơ đã biết, dài trước để nhãn ngắn không cắt mất nhãn dài."""
    labels = {label for aliases in HEADER_ALIASES.values() for label in aliases}
    return tuple(sorted(labels, key=len, reverse=True))
