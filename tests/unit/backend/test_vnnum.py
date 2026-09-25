"""Bảng biến thể số/khoảng/sai số kiểu Việt Nam cho knowledge.vnnum.

Phủ đúng các dạng gặp trong corpus QTKĐ, gồm khoảng trắng hẹp không ngắt
(U+202F) và khoảng trắng không ngắt (U+00A0) do Word/PDF sinh ra.
"""

from __future__ import annotations

import pytest

from knowledge.vnnum import (
    normalize_spaces,
    parse_number,
    parse_quantity,
    parse_range,
    parse_tolerance,
    split_value_unit,
)

NBSP = "\u00a0"
NNBSP = "\u202f"
MINUS = "\u2212"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("0,15", 0.15),
        ("0.15", 0.15),
        ("1 400", 1400.0),
        (f"1{NBSP}400", 1400.0),
        (f"1{NNBSP}400", 1400.0),
        ("1 050", 1050.0),
        ("5 000", 5000.0),
        ("-1", -1.0),
        (f"{MINUS}0,1", -0.1),
        ("+2,5", 2.5),
        ("1.061", 1061.0),  # phân nhóm hàng nghìn
        ("8,051516×10-5", 8.051516e-05),
        ("2,91×10^-9", 2.91e-09),
        ("1,5", 1.5),
        (" 1 400 ", 1400.0),
    ],
)
def test_parse_number_variants(raw, expected):
    assert parse_number(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", None, "abc", "1,2,3", "1.2.3", "bar", "1 400 bar"])
def test_parse_number_rejects_ambiguous_or_non_numeric(raw):
    assert parse_number(raw) is None


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("0.500", 0.5),  # K01: nhóm đầu bằng 0 -> số thập phân, không phải nhóm nghìn
        ("0.125", 0.125),
        ("0.050", 0.05),
        ("1.000", 1000.0),  # nhóm đầu khác 0 -> vẫn là nhóm nghìn
        ("12.500", 12500.0),
        ("1.061", 1061.0),
    ],
)
def test_parse_number_leading_zero_is_decimal(raw, expected):
    """K01: nhóm đầu bằng ``0`` không thể là nhóm nghìn."""
    assert parse_number(raw) == pytest.approx(expected)


def test_normalize_spaces_collapses_unicode_spaces():
    assert normalize_spaces(f"1{NBSP}400") == "1 400"
    assert normalize_spaces(f"1{NNBSP}400") == "1 400"
    assert normalize_spaces("  a\t b\n") == "a b"
    assert normalize_spaces(None) == ""


@pytest.mark.parametrize(
    "raw, low, high",
    [
        ("(0 ÷ 100) %RH", 0.0, 100.0),
        ("(800 ÷ 1 100) mbar", 800.0, 1100.0),
        (f"(800 ÷ 1{NBSP}100) mbar", 800.0, 1100.0),
        ("Từ 0 mm đến 350 mm", 0.0, 350.0),
        ("(20 đến 90) % RH", 20.0, 90.0),
        ("(-1 đến 5 000) bar", -1.0, 5000.0),
        ("(0 đến 24) h", 0.0, 24.0),
        ("từ 20 tới 28 oC", 20.0, 28.0),
    ],
)
def test_parse_range_variants(raw, low, high):
    parsed = parse_range(raw)
    assert parsed is not None
    assert parsed.low == pytest.approx(low)
    assert parsed.high == pytest.approx(high)


@pytest.mark.parametrize("raw", ["1400 bar", "± 3 %", "không phải khoảng", "", None])
def test_parse_range_rejects_non_range(raw):
    assert parse_range(raw) is None


@pytest.mark.parametrize(
    "raw, center, plus",
    [
        ("± 3 %", None, 3.0),
        ("± 0,15 bar", None, 0.15),
        ("(1000 ± 40) mbar", 1000.0, 40.0),
        ("(100 ± 4) kPa", 100.0, 4.0),
        ("± 0,2 oC", None, 0.2),
        ("± 4,8 s/d", None, 4.8),
        ("(8,051516×10-5 ± 2,91×10-9) m2", 8.051516e-05, 2.91e-09),
    ],
)
def test_parse_tolerance_variants(raw, center, plus):
    parsed = parse_tolerance(raw)
    assert parsed is not None
    assert parsed.plus == pytest.approx(plus)
    assert parsed.minus == pytest.approx(plus)
    if center is None:
        assert parsed.center is None
    else:
        assert parsed.center == pytest.approx(center)


@pytest.mark.parametrize("raw", ["0,15 bar", "(0 ÷ 100) %RH", "không có", "", None])
def test_parse_tolerance_rejects_non_tolerance(raw):
    assert parse_tolerance(raw) is None


@pytest.mark.parametrize(
    "raw, rel_op, unit",
    [
        ("1400 bar", "=", "bar"),
        ("(0 ÷ 100) %RH", "range", "%RH"),
        ("± 0,15 bar", "±", "bar"),
        ("(1000 ± 40) mbar", "±", "mbar"),
        ("Từ 0 mm đến 350 mm", "range", "mm"),
        ("(20 đến 90) % RH", "range", "% RH"),
    ],
)
def test_parse_quantity_rel_op_and_unit(raw, rel_op, unit):
    parsed = parse_quantity(raw)
    assert parsed is not None
    assert parsed.rel_op == rel_op
    assert parsed.unit == unit


def test_parse_quantity_scalar_sets_min_equals_max():
    parsed = parse_quantity("1 400 bar")
    assert parsed is not None
    assert parsed.value_min == pytest.approx(1400.0)
    assert parsed.value_max == pytest.approx(1400.0)


def test_parse_quantity_returns_none_without_numbers():
    assert parse_quantity("chỉ có chữ") is None
    assert parse_quantity(None) is None


@pytest.mark.parametrize(
    "raw, value, unit",
    [
        ("1 400 bar", "1400", "bar"),
        ("(0 ÷ 100) %RH", "100", "%RH"),
        ("± 0,2 oC", "0,2", "oC"),
        ("Từ 0 mm đến 350 mm", "350", "mm"),
    ],
)
def test_split_value_unit(raw, value, unit):
    assert split_value_unit(raw) == (value, unit)
