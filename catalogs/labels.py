"""Nhãn tiếng Việt và hằng số chung cho bốn loại danh mục hồ sơ NAS (D1).

Tách riêng để tầng ghi (``catalogs.store``), hàng đợi duyệt (``review.queue``) và
bề mặt tra cứu (``query.catalogs``) dùng chung đúng một nguồn nhãn.
"""

from __future__ import annotations

CATALOG_KINDS: tuple[str, ...] = (
    "lab_standard",
    "inspector",
    "procedure_catalog",
    "capability",
)

CATALOG_LABELS: dict[str, str] = {
    "lab_standard": "Danh mục chuẩn mẫu",
    "inspector": "Danh sách kiểm định viên",
    "procedure_catalog": "Danh mục tiêu chuẩn, quy trình",
    "capability": "Lĩnh vực kiểm định, hiệu chuẩn",
}

# Tiền tố ``extractor`` của mọi dòng danh mục; dùng để lọc hàng đợi và supersede.
CATALOG_EXTRACTOR_PREFIX = "catalog:"


def label_for(kind: str | None) -> str:
    """Nhãn hiển thị của một loại danh mục; trả nguyên khóa nếu lạ."""
    return CATALOG_LABELS.get(kind or "", kind or "")


def extractor_for(kind: str) -> str:
    """Chuỗi ``extractor`` của một lần đọc danh mục (``catalog:lab_standard.v1``)."""
    return f"{CATALOG_EXTRACTOR_PREFIX}{kind}.v1"


def kind_from_extractor(extractor: str | None) -> str | None:
    """Suy loại danh mục từ ``extractor``; ``None`` nếu không phải dòng danh mục."""
    if not extractor or not extractor.startswith(CATALOG_EXTRACTOR_PREFIX):
        return None
    rest = extractor[len(CATALOG_EXTRACTOR_PREFIX) :]
    kind = rest.rsplit(".", 1)[0] if "." in rest else rest
    return kind if kind in CATALOG_LABELS else None
