"""Bảng tra cứu dữ liệu: lọc, phân trang, sắp xếp, xuất xứ từng ô số (Sprint 8)."""

from __future__ import annotations

import pytest

from db.models import ProcedureFact, Unit
from query import records as qr


def test_list_only_returns_approved(data_db):
    db, ids = data_db
    items, total = qr.list_records(db)
    assert total == 2
    assert {item["serial_no"] for item in items} == {"SN-1"}
    # Hồ sơ pending không bao giờ lộ ra (P3).
    assert all(item["serial_no"] != "SN-PENDING" for item in items)


def test_default_sort_newest_first(data_db):
    db, _ = data_db
    items, _ = qr.list_records(db)
    assert [item["calibrated_at"][:10] for item in items] == ["2025-01-15", "2024-01-15"]


def test_sort_ascending_and_whitelist(data_db):
    db, _ = data_db
    items, _ = qr.list_records(db, sort="calibrated_at", order="asc")
    assert [item["calibrated_at"][:10] for item in items] == ["2024-01-15", "2025-01-15"]
    # Tên cột ngoài whitelist rơi về mặc định, không nối vào SQL.
    items, _ = qr.list_records(db, sort="DROP TABLE", order="asc")
    assert len(items) == 2


def test_pagination(data_db):
    db, _ = data_db
    page, total = qr.list_records(db, limit=1, offset=0)
    assert total == 2 and len(page) == 1
    page2, _ = qr.list_records(db, limit=1, offset=1)
    assert page2[0]["id"] != page[0]["id"]
    # limit bị kẹp trần danh sách.
    page3, _ = qr.list_records(db, limit=99999)
    assert len(page3) == 2


def test_filter_by_verdict(data_db):
    db, _ = data_db
    items, total = qr.list_records(db, verdict="khong_dat")
    assert total == 1
    assert items[0]["verdict_label"] == "Không đạt"


def test_filter_by_device_type_and_quantity(data_db):
    db, ids = data_db
    _, total = qr.list_records(db, device_type_id=ids["device_type_id"])
    assert total == 2
    _, total = qr.list_records(db, quantity_id=ids["quantity_id"])
    assert total == 2
    _, total = qr.list_records(db, device_type_id=999)
    assert total == 0


def test_filter_by_procedure(data_db):
    db, ids = data_db
    items, total = qr.list_records(db, procedure_id=ids["procedure_id"])
    assert total == 2
    assert items[0]["procedure_number"] == "1.061"


def test_filter_by_date_range(data_db):
    db, _ = data_db
    _, total = qr.list_records(db, date_from="2024-01-01", date_to="2024-12-31")
    assert total == 1
    _, total = qr.list_records(db, date_from="2024-01-01", date_to="2025-12-31")
    assert total == 2
    _, total = qr.list_records(db, date_from="2030-01-01")
    assert total == 0


def test_filter_by_range_with_unit_conversion(data_db):
    db, _ = data_db
    # QTKĐ phạm vi 0..1600 bar (đã chuẩn hóa 0..1.6e8 Pa).
    _, total = qr.list_records(db, range_min=0, range_max=100, range_unit="bar")
    assert total == 2
    # Khoảng vượt phạm vi QTKĐ → không kết quả.
    _, total = qr.list_records(db, range_min=0, range_max=2000, range_unit="bar")
    assert total == 0
    # Không truyền đơn vị → hiểu là SI (Pa).
    _, total = qr.list_records(db, range_min=0, range_max=150000000)
    assert total == 2


def test_filter_by_accuracy_and_search(data_db):
    db, _ = data_db
    _, total = qr.list_records(db, accuracy="0,5")
    assert total == 2
    _, total = qr.list_records(db, accuracy="không tồn tại")
    assert total == 0
    _, total = qr.list_records(db, search="sn-1")
    assert total == 2
    _, total = qr.list_records(db, search="VA-1")
    assert total == 2
    _, total = qr.list_records(db, search="1.061")
    assert total == 2


def test_unknown_unit_raises(data_db):
    db, _ = data_db
    with pytest.raises(qr.QueryError):
        qr.list_records(db, range_min=1, range_unit="khong-co-don-vi")


def test_provenance_cells_cover_numeric_fields(data_db):
    db, _ = data_db
    items, _ = qr.list_records(db, sort="calibrated_at", order="asc")
    cells = {cell["field"]: cell for cell in items[0]["provenance"]}
    for field in (
        "calibrated_at",
        "expires_at",
        "env_temp_c",
        "env_humidity_pct",
        "range_min",
        "range_max",
        "accuracy_text",
        "measurement_count",
    ):
        assert field in cells
    # Ô phạm vi/cấp chính xác trỏ về dữ kiện QTKĐ, không phải hồ sơ.
    assert cells["range_min"]["kind"] == "fact"
    assert cells["accuracy_text"]["kind"] == "fact"
    assert cells["calibrated_at"]["kind"] == "record"


def _set_range_unit(db, ids, unit_id):
    """Đổi đơn vị gốc của dữ kiện phạm vi để kiểm quy đổi hiển thị."""
    fact = db.get(ProcedureFact, ids["range_fact_id"])
    fact.unit_id = unit_id
    db.commit()


def test_range_display_keeps_si_and_adds_original_unit(data_db):
    db, _ = data_db
    record = qr.list_records(db, sort="calibrated_at", order="asc")[0][0]
    # SI giữ nguyên (bộ lọc range_min_si dùng nó).
    assert record["range_min"] == pytest.approx(0.0)
    assert record["range_max"] == pytest.approx(160000000.0)
    # Đơn vị gốc Pa trùng SI nên hiển thị bằng đúng giá trị SI.
    assert record["range_min_display"] == pytest.approx(0.0)
    assert record["range_max_display"] == pytest.approx(160000000.0)


def test_range_display_converts_to_bar(data_db):
    db, ids = data_db
    _set_range_unit(db, ids, ids["unit_bar_id"])
    record = qr.list_records(db, sort="calibrated_at", order="asc")[0][0]
    # 0..1,6e8 Pa đổi về bar = 0..1600.
    assert record["range_min_display"] == pytest.approx(0.0)
    assert record["range_max_display"] == pytest.approx(1600.0)
    # Trường SI không bị đổi theo đơn vị hiển thị.
    assert record["range_max"] == pytest.approx(160000000.0)


def test_range_display_converts_to_mpa(data_db):
    db, ids = data_db
    mpa = Unit(
        code="MPa",
        name_vi="Megapascal",
        quantity_id=ids["quantity_id"],
        factor_to_si=1000000.0,
        offset_to_si=0.0,
    )
    db.add(mpa)
    db.commit()
    _set_range_unit(db, ids, mpa.id)
    record = qr.list_records(db, sort="calibrated_at", order="asc")[0][0]
    # 1,6e8 Pa đổi về MPa = 160; bỏ nhiễu dấu phẩy động.
    assert record["range_min_display"] == pytest.approx(0.0)
    assert record["range_max_display"] == pytest.approx(160.0)


def test_range_display_falls_back_to_si_without_unit(data_db):
    db, ids = data_db
    _set_range_unit(db, ids, None)
    record = qr.list_records(db, sort="calibrated_at", order="asc")[0][0]
    # Không có đơn vị gốc → giữ giá trị SI (giống ``_from_si`` của router).
    assert record["range_min_display"] == pytest.approx(0.0)
    assert record["range_max_display"] == pytest.approx(160000000.0)


def test_get_record_detail_with_measurements(data_db):
    db, ids = data_db
    record = qr.get_record(db, ids["record_a_id"])
    assert record["serial_no"] == "SN-1"
    assert record["measurement_count"] == 1
    point = record["measurements"][0]
    assert point["step_code"] == "6.3.1"
    assert point["error_value"] == pytest.approx(0.1)
    # Sprint M: sai số có đơn vị riêng "%" tách khỏi đơn vị giá trị đo "bar".
    assert point["unit_code"] == "bar"
    assert point["error_unit_id"] == ids["unit_percent_id"]
    assert point["error_unit_code"] == "%"
    assert point["within_limit"] is True
    assert {cell["field"] for cell in point["provenance"]} == {
        "nominal",
        "measured",
        "error",
        "limit",
    }
    assert all(cell["kind"] == "measurement" for cell in point["provenance"])


def test_get_record_measurements_sorted_by_step_then_ord(data_db):
    """Điểm đo sắp theo ``step_code`` rồi ``ord`` để không xen kẽ A.4/A.5."""
    from db.models import MeasurementPoint

    db, ids = data_db
    db.add_all(
        [
            MeasurementPoint(record_id=ids["record_a_id"], ord=2, step_code="A.4", label="2"),
            MeasurementPoint(record_id=ids["record_a_id"], ord=1, step_code="A.5", label="1"),
            MeasurementPoint(record_id=ids["record_a_id"], ord=1, step_code="A.4", label="1"),
        ]
    )
    db.commit()
    points = qr.get_record(db, ids["record_a_id"])["measurements"]
    labels = [(point["step_code"], point["ord"]) for point in points]
    assert labels == [("6.3.1", 1), ("A.4", 1), ("A.4", 2), ("A.5", 1)]


def test_get_record_missing_raises(data_db):
    db, _ = data_db
    with pytest.raises(qr.NotFoundError):
        qr.get_record(db, 999999)


def test_filter_options_only_reflect_approved(data_db):
    db, _ = data_db
    options = qr.filter_options(db)
    assert [item["label"] for item in options["device_types"]] == ["Van an toàn"]
    assert [item["value"] for item in options["verdicts"]] == ["dat", "khong_dat"]
    assert options["procedures"][0]["label"] == "1.061"


def test_pending_never_in_measurement_lists(data_db):
    db, ids = data_db
    # Số liệu đo của hồ sơ pending không có điểm nào để lộ.
    points = qr.get_record(db, ids["record_b_id"])["measurements"]
    assert len(points) == 1
    _, total = qr.list_records(db, verdict="khong_dat")
    assert total == 1
