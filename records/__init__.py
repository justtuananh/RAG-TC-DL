"""Nạp hồ sơ kiểm định và phiếu đo theo mẫu cố định (spec §9, Sprint 7).

Thư mục này chứa bốn mối quan tâm tách biệt:

- ``template``: sinh và kiểm cấu hình ánh xạ trường từ Phụ lục A đã duyệt;
- ``docx_reader`` / ``xlsx_reader``: đọc mẫu Word/Excel, giữ nguyên văn nguồn;
- ``matching``: đối sánh thiết bị theo loại + serial, chuẩn hóa hoa/thường;
- ``store``: ghi hồ sơ + số liệu đo qua ``extraction`` ``pending`` (P3).

Hai bất biến của thư mục:

- **P2**: không bao giờ tính lại số liệu nguồn. ``error_value`` và các giá trị đo
  chỉ được đọc từ tài liệu; ngoại lệ duy nhất là ``expires_at`` (hạn hiệu lực)
  dẫn xuất từ dữ kiện chu kỳ đã duyệt và luôn kèm ``expires_from_fact_id``.
- **P1**: mỗi số liệu đo giữ ``quote`` và ``*_text`` nguyên văn để đối chiếu.
"""

from __future__ import annotations

__all__ = [
    "docx_reader",
    "ingest",
    "matching",
    "store",
    "template",
    "types",
    "xlsx_reader",
]
