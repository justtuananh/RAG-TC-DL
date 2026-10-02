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
    assert first.nominal_text == "10,0"
    assert first.nominal_value == 10.0
    assert first.measured_text == "10,1"
    assert first.measured_value == 10.1
    assert first.error_text == "0,1"
    assert first.error_value == 0.1
    assert first.limit_text == "0,5"
    assert first.limit_value == 0.5
    assert first.quote == "1 | 10,0 | 10,1 | 0,1 | 0,5 | "


def test_xlsx_k01_numeric_cells_are_vietnamese_decimal_strings(data_dir):
    """K01: ô số (không ``t``/``t="n"``) đổi dấu chấm thập phân thành dấu phẩy,
    không nhóm nghìn, để ``vnnum`` hiểu đúng số thực."""
    draft = read_xlsx(data_dir / "record_phieu_do.xlsx", _config(XLSX_COLUMNS))
    first = draft.measurements[0]
    assert first.measured_text == "10,1"
    assert first.measured_value == 10.1
    assert first.error_value == 0.1


def _header_only_config(label: str) -> MappingConfig:
    return MappingConfig(
        procedure_id=1,
        procedure_number="1.061",
        header_fields=[HeaderField(key="f1", label=label, fact_id=1)],
        result_tables=[],
    )


def test_xlsx_k05_date_styled_cell_converts_excel_serial(tmp_path):
    """K05: ô số có định dạng ngày (xl/styles.xml) chuyển serial thành DD/MM/YYYY."""
    from datetime import date

    from scripts.knowledge_corpus import ooxml as ox

    path = tmp_path / "date.xlsx"
    ox.write_xlsx(path, [ox.Sheet("S", [["Ngày kiểm định", ox.DateCell(date(2026, 7, 20))]])])
    draft = read_xlsx(path, _header_only_config("Ngày kiểm định"))
    assert draft.get_field("Ngày kiểm định") == "20/07/2026"


def test_xlsx_k05_plain_number_is_not_converted_to_date(tmp_path):
    """K05: ô số KHÔNG có định dạng ngày giữ nguyên giá trị số."""
    from scripts.knowledge_corpus import ooxml as ox

    path = tmp_path / "plain.xlsx"
    ox.write_xlsx(path, [ox.Sheet("S", [["Số hiệu", 12345]])])
    draft = read_xlsx(path, _header_only_config("Số hiệu"))
    assert draft.get_field("Số hiệu") == "12345"


def test_docx_k03_table_field_label_with_colon(tmp_path):
    """K03: ô nhãn trong bảng có dấu hai chấm (kể cả dính khoảng trắng) vẫn nhận
    diện; nhãn lưu đã bỏ dấu ':' để ``store`` tra được alias."""
    from scripts.knowledge_corpus import ooxml as ox

    path = tmp_path / "colon.docx"
    rows = [
        [ox.Cell("Số hiệu:"), ox.Cell("SN-1")],
        [ox.Cell("Ngày kiểm định :"), ox.Cell("05/02/2026")],
    ]
    ox.write_docx(path, [ox.heading("BIÊN BẢN KIỂM ĐỊNH", 1), ox.table(rows)])
    draft = read_docx(path, _config(DOCX_COLUMNS))
    assert draft.get_field("Số hiệu") == "SN-1"
    assert draft.get_field("Ngày kiểm định") == "05/02/2026"


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


def test_parse_verdict_k04_ambiguous_template_returns_none():
    """K04: câu mẫu chứa đồng thời 'đạt' độc lập và 'không đạt' là mập mờ."""
    from records.store import _parse_verdict

    assert _parse_verdict("Đạt (không đạt) yêu cầu kỹ thuật đo lường.") is None
    assert _parse_verdict("Đạt/Không đạt") is None
    assert _parse_verdict("Đạt yêu cầu") == "dat"
    assert _parse_verdict("Không đạt yêu cầu") == "khong_dat"
    assert _parse_verdict("Đạt") == "dat"
    assert _parse_verdict("Không đạt") == "khong_dat"


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


def test_docx_k07_gridspan_columns_map_correct_roles(tmp_path):
    """K07: bảng có ô gộp ``gridSpan`` đọc đúng vai trò cột; cột phụ (Đóng) vào
    note dạng ``nhãn: giá trị``, cột ``Độ chênh áp`` vào error."""
    from scripts.knowledge_corpus import ooxml as ox

    rows = [
        [
            ox.Cell("Lần kiểm tra"),
            ox.Cell("Áp suất", span=3),
            ox.Cell("Sai số"),
            ox.Cell("Ghi chú"),
        ],
        [
            ox.Cell(""),
            ox.Cell("Mở"),
            ox.Cell("Đóng"),
            ox.Cell("Độ chênh áp"),
            ox.Cell(""),
            ox.Cell(""),
        ],
        [
            ox.Cell("1"),
            ox.Cell("120,05"),
            ox.Cell("120,00"),
            ox.Cell("0,05"),
            ox.Cell(""),
            ox.Cell(""),
        ],
    ]
    path = tmp_path / "grid.docx"
    ox.write_docx(path, [ox.heading("BIÊN BẢN KIỂM ĐỊNH", 1), ox.table(rows)])
    config = MappingConfig(
        procedure_id=1,
        procedure_number="9.015",
        header_fields=[],
        result_tables=[
            ResultTable(
                key="bang",
                title="Bảng A.1",
                columns=["Lần kiểm tra", "Áp suất Mở", "Đóng", "Độ chênh áp", "Sai số", "Ghi chú"],
                fact_id=1,
            )
        ],
    )
    draft = read_docx(path, config)
    assert len(draft.measurements) == 1
    point = draft.measurements[0]
    assert point.measured_value == 120.05
    assert point.error_value == 0.05
    assert point.note == "Đóng: 120,00"
    assert point.quote == "1 | 120,05 | 120,00 | 0,05 |  | "


def test_map_measurement_row_k09_unit_from_column_header():
    """K09: đơn vị lấy từ ngoặc ở tiêu đề cột giá trị, ví dụ ``Giá trị đo (bar)``."""
    draft = _map_measurement_row(
        ["Lần kiểm tra", "Giá trị đo (bar)", "Sai số"],
        ["1", "10,5", "0,2"],
    )
    assert draft.measured_value == 10.5
    assert draft.unit_text == "bar"

    plain = _map_measurement_row(["Lần kiểm tra", "Giá trị đo", "Sai số"], ["1", "10,5", "0,2"])
    assert plain.unit_text is None
