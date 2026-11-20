"""Quy đổi đơn vị tất định."""

import pytest

from query import unit_convert


@pytest.mark.parametrize(
    "q,expected",
    [
        ("Quy đổi 5 bar sang kPa.", "5 bar = 500 kPa"),
        ("Đổi 2,5 MPa ra bar?", "2,5 MPa = 25 bar"),
        ("1000 kPa bằng bao nhiêu bar?", "1000 kPa = 10 bar"),
        ("Hãy quy đổi 750 Pa sang kPa", "750 Pa = 0,75 kPa"),
    ],
)
def test_pure_conversion(q, expected):
    out = unit_convert.try_convert(q)
    assert out is not None and out.text.startswith(expected)


@pytest.mark.parametrize(
    "q",
    [
        "Đổi 1 400 bar sang MPa.",  # dấu cách ngăn nghìn như trong tài liệu QTKĐ
        "Đổi 1 400 bar sang MPa.",
        "Đổi 1400 bar sang MPa.",
        "Đổi 1.400 bar sang MPa.",  # dấu chấm ngăn nghìn kiểu Việt Nam
    ],
)
def test_thousands_separator_keeps_every_digit(q):
    out = unit_convert.try_convert(q)
    assert out is not None and out.text.startswith("1400 bar = 140 MPa")


def test_dimension_mismatch_is_reported():
    out = unit_convert.try_convert("Quy đổi 5 bar sang mm")
    assert out is not None and "không cùng loại" in out.text


@pytest.mark.parametrize(
    "q",
    [
        "Quy đổi 5 bar sang kPa rồi so với áp suất 3 bar",  # đại lượng thứ hai
        "Áp suất chỉnh đặt 40 bar có đạt không?",
        "Quy đổi bar sang kPa",  # không có số
        "Sai số cho phép của áp kế 0,05 là bao nhiêu bar?",
        "Quy đổi 5 bar sang kPa để kiểm định áp kế pít tông",  # nêu phép kiểm định
    ],
)
def test_not_a_pure_conversion(q):
    assert unit_convert.try_convert(q) is None


def test_flow_rate_litre_per_minute_to_litre_per_hour():
    # Bộ kiểm tra hệ thống: "Đổi 200 L/min sang L/h" từng bị từ chối "không tìm thấy".
    assert "200 L/min = 12000 L/h" in unit_convert.try_convert("Đổi 200 L/min sang L/h.").text


def test_flow_rate_is_not_convertible_to_a_pressure_unit():
    assert "không cùng loại" in unit_convert.try_convert("Đổi 200 L/min sang bar.").text
