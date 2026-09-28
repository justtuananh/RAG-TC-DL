"""Hàm đổi đơn vị SI dùng chung cho tầng tra cứu (DRY giữa records/router).

Trước đây ``query/records.py`` và ``query/router.py`` mỗi bên giữ một bản
``_from_si`` gần giống nhau; hai bản dễ trôi khỏi nhau. Một hàm chung ở
``query/units.py`` là nguồn sự thật duy nhất, chỉ đọc view ``v_unit`` (P3).
"""

from __future__ import annotations

import pytest

from query import units as qunits


def test_unit_defs_by_id_reads_view(data_db):
    session, ids = data_db
    defs = qunits.unit_defs_by_id(session)
    assert defs[ids["unit_bar_id"]]["code"] == "bar"
    assert defs[ids["unit_bar_id"]]["factor_to_si"] == pytest.approx(100000.0)
    assert defs[ids["unit_pa_id"]]["factor_to_si"] == pytest.approx(1.0)


def test_from_si_converts_and_bounds_noise():
    unit = {"code": "bar", "factor_to_si": 100000.0, "offset_to_si": 0.0}
    assert qunits.from_si(160000000.0, unit) == pytest.approx(1600.0)
    # 9 chữ số có nghĩa bỏ nhiễu dấu phẩy động.
    assert qunits.from_si(160000001.0, unit) == pytest.approx(1600.00001)
    assert qunits.from_si(None, unit) is None
    # Không có đơn vị gốc → giữ nguyên giá trị SI.
    assert qunits.from_si(5.0, None) == pytest.approx(5.0)
    # Hệ số 0 (dữ liệu lỗi) giữ nguyên giá trị thay vì chia cho 0.
    assert qunits.from_si(5.0, {"factor_to_si": 0.0, "offset_to_si": 0.0}) == pytest.approx(5.0)
