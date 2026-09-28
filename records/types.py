"""Kiểu dữ liệu trung gian giữa bộ đọc hồ sơ và tầng ghi sổ cái (Sprint 7).

Bộ đọc (``docx_reader``/``xlsx_reader``) không chạm DB: chúng trả về ``RecordDraft``
thuần dữ liệu. Tầng ``store`` mới ánh xạ bản nháp sang ``calibration_record`` +
``measurement_point``. Nhờ vậy hai bộ đọc test được trên tệp mẫu mà không cần
Postgres, và nguyên tắc P1/P2 được kiểm ở một chỗ duy nhất.

Mọi trường số trên ``MeasurementDraft`` chỉ là kết quả phân tích chuỗi nguồn
(``*_text``). Không hàm nào trong thư mục ``records/`` được phép suy ``error``
từ chênh lệch giữa measured và nominal; ``error_value`` chỉ đến từ ô "Sai số"
của tài liệu.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MeasurementDraft:
    """Một dòng số liệu đo đọc từ hồ sơ, giữ nguyên văn từng ô."""

    ord: int | None = None
    step_code: str | None = None
    label: str | None = None
    nominal_text: str | None = None
    measured_text: str | None = None
    error_text: str | None = None
    limit_text: str | None = None
    unit_text: str | None = None
    # Đơn vị của sai số/giới hạn khi khác đơn vị giá trị đo (sai số tương đối "%").
    error_unit_text: str | None = None
    note: str | None = None
    # Nguyên văn cả dòng nguồn (P1).
    quote: str = ""
    # Thiếu đơn vị thì tầng store được dùng đơn vị ``working_range`` của QTKĐ (K09).
    # Bảng đã nhận diện rõ cấu trúc đặt False: đơn vị chỉ đến từ chính bảng đó.
    inherit_unit: bool = True
    # Nguyên văn MỌI ô của dòng kèm tên cột của chính bảng nguồn (P1), kể cả ô không
    # có vai trò: ``[{"column": "Lượt 1", "text": "0,33"}, ...]``.
    cells: list[dict[str, str]] = field(default_factory=list)

    # Chỉ là kết quả phân tích các ``*_text`` ở trên — không bao giờ được tính lại.
    nominal_value: float | None = None
    measured_value: float | None = None
    error_value: float | None = None
    limit_value: float | None = None

    def has_source_number(self) -> bool:
        """True nếu có ít nhất một giá trị số đọc được từ tài liệu."""
        return any(
            value is not None
            for value in (
                self.nominal_value,
                self.measured_value,
                self.error_value,
                self.limit_value,
            )
        )


@dataclass
class FieldDraft:
    """Một trường đầu mục (nhãn → giá trị) kèm nguyên văn dòng nguồn."""

    label: str
    value: str
    quote: str = ""
    # ``appendix``: nhãn Phụ lục A đã duyệt; ``record``: dòng nhãn tự do của chính
    # biên bản (``U(p) =``) mà Phụ lục A không liệt kê.
    source: str = "appendix"


@dataclass
class RecordDraft:
    """Bản nháp một hồ sơ kiểm định (biên bản Word hoặc phiếu đo Excel)."""

    extractor: str
    source_text: str
    section_path: str | None = None
    fields: list[FieldDraft] = field(default_factory=list)
    measurements: list[MeasurementDraft] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def header_map(self) -> dict[str, str]:
        """Gộp các trường đầu mục thành ``{nhãn đã chuẩn hóa: giá trị}``.

        Nhiều dòng cùng nhãn (hiếm) giữ giá trị đầu tiên; nhãn được chuẩn hóa
        khoảng trắng và hạ hoa/thường để ánh xạ ổn định.
        """
        from knowledge import vnnum

        result: dict[str, str] = {}
        for item in self.fields:
            key = vnnum.normalize_spaces(item.label).casefold()
            if key and key not in result:
                result[key] = item.value
        return result

    def get_field(self, *labels: str) -> str | None:
        """Giá trị đầu tiên khớp một trong các nhãn (đã chuẩn hóa, bỏ dấu hai chấm)."""
        from knowledge import vnnum

        mapping = self.header_map()
        for label in labels:
            key = vnnum.normalize_spaces(label).casefold().rstrip(":")
            value = mapping.get(key)
            if value:
                return value
        return None
