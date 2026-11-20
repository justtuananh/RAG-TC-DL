"""Đọc số tiếng Việt: dấu phẩy thập phân, dấu cách/dấu chấm ngăn nghìn."""

import re

import pytest

from query.numbers import NUMBER, normalize


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1 400 bar", ["1 400"]),  # cách viết trong chính tài liệu QTKĐ
        ("1 400 bar", ["1 400"]),  # NBSP do Word sinh ra
        ("1400 bar", ["1400"]),
        ("1.400 bar", ["1.400"]),
        ("1.400.000 Pa", ["1.400.000"]),
        ("2,5 MPa", ["2,5"]),
        ("1.400,5 bar", ["1.400,5"]),
        ("0,125 MPa", ["0,125"]),
        ("0.125 MPa", ["0.125"]),  # số 0 đứng đầu không bao giờ là nhóm nghìn
        ("5 bar và 3 000 kPa", ["5", "3 000"]),  # nhóm nghìn không nuốt đơn vị
        ("12345 bar", ["12345"]),
    ],
)
def test_number_pattern_keeps_whole_number(text, expected):
    assert re.findall(NUMBER, text) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1 400", "1400"),
        ("1 400", "1400"),
        ("1.400", "1400"),
        ("1.400.000", "1400000"),
        ("1.400,5", "1400.5"),
        ("2,5", "2.5"),
        ("2.5", "2.5"),
        ("0.125", "0.125"),
        ("+3,5", "+3.5"),
        ("-1 400", "-1400"),
        ("-1.400", "-1400"),
    ],
)
def test_normalize_gives_decimal_text(raw, expected):
    assert normalize(raw) == expected
