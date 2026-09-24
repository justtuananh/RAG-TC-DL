"""Bộ đọc Word/Excel trên tệp mẫu đã làm sạch (Sprint 7).

Kiểm ba việc: đọc đúng trường đầu mục + bảng kết quả; giữ nguyên văn/quote (P1);
và KHÔNG tự tính lại số liệu (P2) — đặc biệt ``error_value`` chỉ đến từ ô sai số.
"""

from __future__ import annotations

from records.docx_reader import _map_measurement_row, read_docx
from records.store import _measurement_row
from records.template import HeaderField, MappingConfig, ResultTable
from records.types import MeasurementDraft
from records.xlsx_reader import read_xlsx

HEADER_LABELS = [
    "Tên phương tiện đo",
    "Số hiệu",
    "Ký hiệu",
    "Ngày kiểm định",
    "Chế độ kiểm định",
    "Kết luận",
    "Nhiệt độ",
    "Độ ẩm",
    "Số giấy chứng nhận",
    "Người kiểm định",
    "Người soát lại",
    "Đơn vị sử dụng",
    "Nơi (hãng) sản xuất",
]

DOCX_COLUMNS = ["Lần kiểm tra", "Áp suất", "Sai số", "Ghi chú"]
XLSX_COLUMNS = [
    "Lần kiểm tra",
    "Giá trị danh nghĩa",
    "Giá trị đo",
    "Sai số",
    "Giới hạn",
    "Ghi chú",
]


def _config(columns: list[str]) -> MappingConfig:
    return MappingConfig(
        procedure_id=1,
        procedure_number="1.061",
        header_fields=[
            HeaderField(key=f"f{index}", label=label, fact_id=index)
            for index, label in enumerate(HEADER_LABELS, start=1)
        ],
        result_tables=[ResultTable(key="bang", title="Bảng kết quả", columns=columns, fact_id=99)],
    )


def test_docx_reader_extracts_header_fields(data_dir):
    draft = read_docx(data_dir / "record_bien_ban.docx", _config(DOCX_COLUMNS))
    assert draft.extractor == "record:docx.v1"
    assert draft.get_field("Số hiệu") == "SN-2024-001"
    assert draft.get_field("Ký hiệu") == "VA-100"
    assert draft.get_field("Ngày kiểm định") == "15/01/2024"
    assert draft.get_field("Kết luận") == "Đạt"
    assert draft.get_field("Chế độ kiểm định") == "Định kỳ"


def test_docx_reader_reads_result_table_with_provenance(data_dir):
    draft = read_docx(data_dir / "record_bien_ban.docx", _config(DOCX_COLUMNS))
    assert len(draft.measurements) == 3

    first = draft.measurements[0]
    assert first.ord == 1
    assert first.measured_text == "10,5"
    assert first.measured_value == 10.5
    # P2: sai số đọc nguyên trạng từ ô "Sai số".
    assert first.error_text == "0,2"
    assert first.error_value == 0.2
    # P1: nguyên văn cả dòng.
    assert first.quote == "1 | 10,5 | 0,2 | "

    third = draft.measurements[2]
    assert third.error_value == -0.1


def test_xlsx_reader_extracts_fields_and_measurements(data_dir):
    draft = read_xlsx(data_dir / "record_phieu_do.xlsx", _config(XLSX_COLUMNS))
    assert draft.extractor == "record:xlsx.v1"
    assert draft.get_field("Số hiệu") == "SN-2024-002"
    assert draft.get_field("Kết luận") == "Không đạt"
    assert draft.get_field("Nhiệt độ") == "21"
    assert draft.get_field("Độ ẩm") == "60"

    assert len(draft.measurements) == 3
    first = draft.measurements[0]
    assert first.ord == 1
    assert first.nominal_text == "10.0"
    assert first.nominal_value == 10.0
    assert first.measured_text == "10.1"
    assert first.measured_value == 10.1
    assert first.error_text == "0.1"
    assert first.error_value == 0.1
    assert first.limit_text == "0.5"
    assert first.limit_value == 0.5
    assert first.quote == "1 | 10.0 | 10.1 | 0.1 | 0.5 | "


def test_no_recalculation_when_error_column_absent():
    """P2: không có cột sai số thì error_value để trống, dù đủ measured+nominal."""
    draft = _map_measurement_row(
        ["Lần kiểm tra", "Giá trị danh nghĩa", "Giá trị đo"],
        ["1", "10,0", "10,5"],
    )
    assert draft.nominal_value == 10.0
    assert draft.measured_value == 10.5
    assert draft.error_text is None
    assert draft.error_value is None


def test_no_recalculation_when_error_cell_blank():
    draft = _map_measurement_row(
        ["Lần kiểm tra", "Giá trị đo", "Sai số"],
        ["1", "10,5", ""],
    )
    assert draft.measured_value == 10.5
    assert draft.error_value is None


def test_store_mapping_never_invents_error():
    """Tầng ghi giữ nguyên error_value của bản nháp; không tính từ measured/nominal."""
    draft = MeasurementDraft(
        measured_value=10.5, nominal_value=10.0, measured_text="10,5", nominal_text="10,0"
    )
    point = _measurement_row(draft, unit_id=None)
    assert point.error_value is None
    assert point.within_limit is None


def test_within_limit_only_when_both_sources_present():
    draft = MeasurementDraft(error_value=0.2, limit_value=0.5)
    point = _measurement_row(draft, unit_id=None)
    assert point.within_limit == 1

    draft = MeasurementDraft(error_value=0.9, limit_value=0.5)
    point = _measurement_row(draft, unit_id=None)
    assert point.within_limit == 0

    draft = MeasurementDraft(error_value=0.9)
    point = _measurement_row(draft, unit_id=None)
    assert point.within_limit is None
