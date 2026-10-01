"""Câu trả lời cực trị dựng từ nguyên văn ô biên bản (``query/record_answer.py``)."""

from __future__ import annotations

from datetime import datetime

from query.record_answer import RankGroup, extreme_answer, field_sentence, point_sentence
from query.table_model import DataTable

RECORD = {
    "id": 1,
    "cert_no": "011/2024",
    "calibrated_at": datetime(2024, 7, 10),
    "device_type_name": "Áp kế píttông tiêu chuẩn",
    "model_code": "МП-60",
    "serial_no": "1045",
    "verdict": "khong_dat",
}
HEAD = "Biên bản 011/2024 của áp kế píttông tiêu chuẩn МП-60 số hiệu 1045, ngày 10/07/2024"


def _sink_rate(measured: float, *, within_limit=None) -> dict:
    """Dòng bảng A.3 (tốc độ hạ pít tông): lượt đo, trung bình, giới hạn trên."""
    text = f"{measured:.2f}".replace(".", ",")
    return {
        "label": None,
        "measured_value": measured,
        "measured_text": text,
        "limit_value": 0.4,
        "limit_text": "≤ 0,4",
        "within_limit": within_limit,
        "cells": [
            {"column": "Kết quả, mm/min Lượt 1", "text": "0,5"},
            {"column": "Kết quả, mm/min Lượt 2", "text": ""},
            {"column": "Giá trị trung bình, mm/min", "text": text},
            {"column": "Giá trị cho phép, mm/min", "text": "≤ 0,4"},
        ],
    }


def test_upper_bound_failure_says_exceeds():
    sentence = point_sentence(RECORD, _sink_rate(0.45), "Tốc độ hạ")
    assert sentence == (
        f"{HEAD}: trung bình 0,45 mm/min (lượt 1 0,5 mm/min), "
        "vượt mức cho phép ≤ 0,4 mm/min nên không đạt."
    )


def test_failure_is_not_claimed_when_the_record_itself_passed():
    sentence = point_sentence({**RECORD, "verdict": "dat"}, _sink_rate(0.45), "Tốc độ hạ")
    assert sentence.endswith(", mức cho phép ≤ 0,4 mm/min.")


def test_ascii_comparator_is_inclusive_at_the_boundary():
    point = {
        **_sink_rate(0.4),
        "limit_text": "<= 0,4",
        "cells": [
            {"column": "Giá trị trung bình, mm/min", "text": "0,40"},
            {"column": "Giá trị cho phép, mm/min", "text": "<= 0,4"},
        ],
    }
    assert point_sentence(RECORD, point, "Tốc độ hạ").endswith(
        ": trung bình 0,40 mm/min, trong mức cho phép <= 0,4 mm/min nên đạt."
    )


def test_limit_in_another_unit_is_not_compared_with_the_reading():
    point = {
        **_sink_rate(0.45),
        "cells": [
            {"column": "Giá trị trung bình, mm/min", "text": "0,45"},
            {"column": "Giá trị cho phép, mm/s", "text": "≤ 0,4"},
        ],
    }
    assert point_sentence(RECORD, point, "Tốc độ hạ").endswith(
        ": trung bình 0,45 mm/min, mức cho phép ≤ 0,4 mm/s."
    )


def _weight(*, within_limit: int) -> dict:
    """Dòng bảng A.4 (quả cân): mức cho phép áp cho SAI SỐ (%), không cho khối lượng (g)."""
    return {
        "label": "1",
        "measured_value": 84.46322,
        "limit_value": 0.0375,
        "limit_text": "0,0375",
        "within_limit": within_limit,
        "cells": [
            {"column": "TT", "text": "1"},
            {"column": "Khối lượng thực tế (g)", "text": "84,46322"},
            {"column": "Sai số tương đối khối lượng quả cân (%) Giá trị xác định", "text": "0,05"},
            {
                "column": "Sai số tương đối khối lượng quả cân (%) Giá trị cho phép",
                "text": "0,0375",
            },
        ],
    }


def test_limit_on_the_error_uses_the_reader_flag_and_shows_the_error():
    assert point_sentence(RECORD, _weight(within_limit=0), "Bảng A.4").endswith(
        ": khối lượng thực tế 84,46322 g, sai số 0,05 %, ngoài mức cho phép 0,0375 % nên không đạt."
    )
    assert point_sentence(RECORD, _weight(within_limit=1), "Bảng A.4").endswith(
        ", sai số 0,05 %, trong mức cho phép 0,0375 % nên đạt."
    )


def test_generic_measured_column_uses_the_row_label():
    label = "Độ không vuông góc của đĩa cân với trục pít tông"
    point = {
        "label": label,
        "measured_value": 2.3,
        "limit_value": 5.0,
        "limit_text": "< 5'",
        "within_limit": None,
        "cells": [
            {"column": "Thông số kiểm tra", "text": label},
            {"column": "Giá trị xác định", "text": "2,3"},
            {"column": "Giá trị cho phép", "text": "< 5'"},
        ],
    }
    assert point_sentence(RECORD, point, "Bảng A.1") == (
        f"{HEAD}: độ không vuông góc của đĩa cân với trục pít tông 2,3, trong mức cho phép < 5' nên đạt."
    )


def test_field_sentence_keeps_verbatim_value_and_related_fields():
    row = {"value_text": "0,025 × 10-3 (MPa);"}
    related = [("U(p)", {"value_text": "0,050 × 10-3 (MPa) (với k = 2)"}), ("Khác", None)]
    assert field_sentence(RECORD, row, "Độ không đảm bảo đo", related) == (
        f"{HEAD}: độ không đảm bảo đo 0,025 × 10-3 (MPa) (U(p) 0,050 × 10-3 (MPa) (với k = 2))."
    )


def test_missing_device_type_falls_back_to_device():
    row = {"value_text": "0,02"}
    sentence = field_sentence({**RECORD, "device_type_name": None}, row, "Cấp chính xác", [])
    assert sentence.startswith("Biên bản 011/2024 của thiết bị МП-60 số hiệu 1045, ")


def test_ties_are_all_listed():
    group = RankGroup(
        table=DataTable(title="t", columns=[]),
        procedure=None,
        label="Thời gian quay tự do",
        order="nhỏ nhất",
        sentences=["Biên bản A.", "Biên bản B."],
    )
    assert extreme_answer([group]) == (
        "Có 2 biên bản cùng thời gian quay tự do nhỏ nhất:\n\n- Biên bản A.\n- Biên bản B."
    )


def test_ties_inside_one_of_several_procedures_are_marked():
    table = DataTable(title="t", columns=[])
    groups = [
        RankGroup(table, "1.159", "Bảng A.2", "nhỏ nhất", ["Biên bản A.", "Biên bản B."]),
        RankGroup(table, "9.999", "Bảng A.2", "nhỏ nhất", ["Biên bản C."]),
    ]
    assert extreme_answer(groups).splitlines() == [
        "Mỗi QTKĐ so riêng, không so chéo quy trình:",
        "",
        "- **QTKĐ 1.159** (đồng hạng): Biên bản A.",
        "- **QTKĐ 1.159** (đồng hạng): Biên bản B.",
        "- **QTKĐ 9.999**: Biên bản C.",
    ]
