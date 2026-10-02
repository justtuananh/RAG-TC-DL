"""Bộ đọc Excel trên biên bản áp kế pittông thật (QTKĐ 1.159:2021).

Mẫu ``scripts/pittong_records/template.xlsx`` là biên bản thật: 4 sheet, sheet đầu
là bảng tra phụ; bảng 2 (quả cân) đặt SONG SONG với khối đầu mục; bảng nhiều tầng
tiêu đề gộp ô. Cấu hình đọc dựng từ Phụ lục A thật của QTKĐ 1.159 qua chính luật
``phuluc_a`` như đường sản phẩm, nên test này là hợp đồng giữa tri thức và bộ đọc.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from knowledge.rules import phuluc_a
from records.ingest import _peek_text, detect_procedure_number
from records.template import HeaderField, MappingConfig, ResultTable, _load_table_value, slugify
from records.xlsx_reader import read_xlsx

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "scripts" / "pittong_records" / "template.xlsx"
QTKD_1159 = ROOT / "build" / "spike_a" / "QTKD_1.159_2021_ND_FINAL.md"


def _config_from_appendix() -> MappingConfig:
    """Cấu hình như ``derive_mapping_config`` dựng từ dữ kiện Phụ lục A đã duyệt."""
    headers: list[HeaderField] = []
    tables: list[ResultTable] = []
    seen: set[str] = set()
    for index, hit in enumerate(phuluc_a.extract(QTKD_1159.read_text(encoding="utf-8"))):
        key = slugify(hit.label)
        if key in seen:
            continue
        seen.add(key)
        if hit.condition_text == "table":
            columns, _ = _load_table_value(hit.value_text, hit.label)
            tables.append(ResultTable(key=key, title=hit.label, columns=columns, fact_id=index))
        else:
            headers.append(HeaderField(key=key, label=hit.label, fact_id=index))
    return MappingConfig(1, "1.159", headers, tables)


@pytest.fixture(scope="module")
def draft():
    return read_xlsx(TEMPLATE, _config_from_appendix())


def _fields(draft) -> dict[str, str]:
    return {field.label: field.value for field in draft.fields}


def _points(draft, step_code: str):
    return [point for point in draft.measurements if point.step_code == step_code]


def test_header_fields_read_from_result_sheet_not_first_sheet(draft):
    fields = _fields(draft)
    assert fields["Ký hiệu"] == "МП-6M"
    assert fields["Số hiệu"] == "5387"
    assert fields["Nước (hãng) sản xuất"] == "Nga"
    assert fields["Tên trang bị ĐL-TN"] == "Áp kế pít tông"
    assert fields["Đơn vị sử dụng"] == "Phòng Đo lường Nhiệt-Áp suất, Trung tâm Đo lường"
    assert fields["Phương pháp kiểm định"] == "QTKĐ 1.159 : 2021"
    assert fields["Phương tiện kiểm định"] == "Áp kế píttông PG7302"
    assert fields["Ngày kiểm định"] == "22/11/2022"
    assert fields["Phạm vi đo"] == "(0,4 đến 6) bar;"
    assert fields["Cấp chính xác"] == "0,02"


def test_header_value_never_taken_from_parallel_table(draft):
    fields = _fields(draft)
    # A11/A17 là nhãn không có giá trị; ô bên phải cùng dòng thuộc bảng 2 (J:O).
    assert fields["Đặc trưng kỹ thuật đo lường"] == ""
    assert fields["Điều kiện kiểm định"] == ""


def test_label_cell_longer_than_appendix_label_takes_neighbour_value(draft):
    fields = _fields(draft)
    # "Nhiệt độ môi trường:" / "Độ ẩm môi trường" so với nhãn Phụ lục A "Nhiệt độ"/"Độ ẩm".
    assert fields["Nhiệt độ"] == "(20 ± 2) ºC"
    assert fields["Độ ẩm"] == "(65 ± 5) %RH"
    # "pít tông" (biên bản) so với "píttông" (Phụ lục A).
    assert fields["Diện tích hiệu dụng của píttông"] == "A0 = 0,99924 × 10-4 , m2"


def test_label_value_spanning_several_cells_is_joined(draft):
    assert _fields(draft)["Độ không đảm bảo đo"] == (
        "uCmax = 0,756 × 10-3 (kg/cm2) tại p = 4,2 kG/cm2"
    )


def test_conclusion_and_signatures_are_record_fields(draft):
    fields = _fields(draft)
    assert fields["Kết luận"] == "Đạt yêu cầu kỹ thuật đo lường"
    assert fields["Kiểm định viên"] == "Phạm Văn Hà"
    assert fields["Người kiểm soát"] == "Luyện Thanh Tùng"


def test_mass_table_beside_header_block_is_read_by_its_own_columns(draft):
    points = _points(draft, "A.4")
    assert len(points) == 18
    first = points[0]
    assert (first.ord, first.label) == (1, "1")
    # Số máy "999.99784999999997" đổi sang chuỗi ngắn nhất cùng giá trị double.
    assert first.measured_text == "999,99785" and first.measured_value == pytest.approx(999.99785)
    assert first.unit_text == "g"
    assert first.error_text == "0,006" and first.error_value == pytest.approx(0.006)
    assert first.limit_text == "0,015" and first.limit_value == pytest.approx(0.015)
    assert first.nominal_text.startswith("999,93785")
    assert points[-1].label == "G"


def test_pressure_balance_table_on_second_result_sheet(draft):
    points = _points(draft, "A.5")
    assert [point.ord for point in points] == list(range(1, 11))
    assert points[0].nominal_text == "0,6" and points[0].nominal_value == pytest.approx(0.6)
    assert points[0].unit_text == "kG/cm2"
    # Không có cột "giá trị đo" áp suất: không được gán nhầm áp suất khí quyển/độ ẩm.
    assert all(point.measured_text is None for point in points)
    assert "Áp suất khí quyển, hPa=1014,55" in points[0].note


def test_technical_check_table_skips_subheadings_and_reads_limits(draft):
    points = _points(draft, "A.1")
    labels = [point.label for point in points]
    assert labels[0] == "Độ không vuông góc của đĩa cân với trục pít tông"
    assert not any(label.startswith("Kiểm tra") for label in labels)
    assert len(points) == 5
    squareness = points[0]
    assert (squareness.measured_value, squareness.limit_value) == (2.0, 5.0)
    leak = points[1]
    assert (leak.measured_value, leak.limit_text, leak.limit_value) == (20.0, "≤ 30", 30.0)
    assert leak.unit_text == "kPa"
    # "Vt1 = 0,3" mơ hồ (chữ số dính ký hiệu): giữ nguyên văn, không đoán số.
    assert points[2].measured_text == "Vt1 = 0,3" and points[2].measured_value is None


def test_multi_row_header_tables_use_mean_as_measured(draft):
    (free_rotation,) = _points(draft, "A.2")
    assert free_rotation.measured_value == 208.0 and free_rotation.unit_text == "s"
    assert free_rotation.limit_value == 180.0
    assert "210" in free_rotation.note and "206" in free_rotation.note
    (descent,) = _points(draft, "A.3")
    assert descent.measured_text == "0,3" and descent.unit_text == "mm/min"


def test_no_measurement_comes_from_header_block(draft):
    assert len(draft.measurements) == 35
    assert not any("Ký hiệu" in (point.quote or "") for point in draft.measurements)


def test_table_units_never_inherit_procedure_range_unit(draft):
    assert draft.measurements
    assert all(point.inherit_unit is False for point in draft.measurements)


def test_source_text_covers_every_sheet(draft):
    for sheet in ("Chọn quả", "KQ KĐ", "KQ KĐ (2)", "Tính toán"):
        assert f"[Sheet: {sheet}]" in draft.source_text


def test_peek_text_sees_procedure_on_non_first_sheet():
    assert detect_procedure_number(_peek_text(TEMPLATE)) == "1.159"


def test_detect_procedure_prefers_explicit_qtkd_code():
    text = "Phần mềm 2.105 | 0.006 | Phương pháp kiểm định: QTKĐ 1.159 : 2021"
    assert detect_procedure_number(text) == "1.159"


def test_label_inside_sentence_is_not_a_field(draft):
    fields = _fields(draft)
    # "Quả số" (sheet Chọn quả) và "3.3 Xác định độ chính xác" không được chiếm nhãn.
    assert "số" not in fields and "độ chính xác" not in fields
    assert fields["Độ chính xác"] == "d = 0,00018"


def test_template_placeholder_dots_are_empty_value(draft):
    # Mẫu để trống "Số:……….": không được lưu chuỗi chấm làm số biên bản.
    assert _fields(draft)["Số"] == ""


def test_relative_error_keeps_its_own_unit(draft):
    # Bảng 2: khối lượng theo g nhưng sai số tương đối theo % (tiêu đề "(%)").
    first = _points(draft, "A.4")[0]
    assert (first.unit_text, first.error_unit_text) == ("g", "%")
    # Bảng không có cột sai số thì không có đơn vị sai số.
    assert all(point.error_unit_text is None for point in _points(draft, "A.1"))
