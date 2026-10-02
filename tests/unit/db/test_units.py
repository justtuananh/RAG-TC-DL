"""Quy đổi đơn vị (knowledge.units): toán hai chiều + từ chối đơn vị lạ.

Cổng Sprint 3 yêu cầu test quy đổi hai chiều cho từng đơn vị áp suất và quy tắc
"thà bỏ trống còn hơn đoán" với đơn vị lạ.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base, Quantity
from knowledge.seed_data import UNITS, seed_reference_data
from knowledge.units import (
    SiConversion,
    UnitDef,
    convert,
    convert_quantity_to_si,
    convert_to_si,
    from_si,
    load_unit_defs,
    normalize_unit_text,
    resolve_unit,
    to_si,
    unit_lookup,
)
from knowledge.vnnum import parse_quantity

PRESSURE_CODES = ["Pa", "kPa", "MPa", "bar", "mbar", "hPa", "psi", "kgf/cm2", "at", "mmHg", "mmH2O"]

# Hệ số chuẩn về Pa (nguồn: định nghĩa SI / tiêu chuẩn đo lường).
PRESSURE_TO_PA = {
    "Pa": 1.0,
    "kPa": 1e3,
    "MPa": 1e6,
    "bar": 1e5,
    "mbar": 1e2,
    "hPa": 1e2,
    "psi": 6894.757293168,
    "kgf/cm2": 98066.5,
    "at": 98066.5,
    "mmHg": 133.322387415,
    "mmH2O": 9.80665,
}


def _unit_defs() -> list[UnitDef]:
    return [
        UnitDef(
            code=row["code"],
            factor_to_si=row["factor_to_si"],
            offset_to_si=row["offset_to_si"],
            aliases=tuple(row["aliases"]),
        )
        for row in UNITS
    ]


@pytest.fixture(scope="module")
def defs() -> list[UnitDef]:
    return _unit_defs()


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = factory()
    seed_reference_data(db)
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_pressure_factor_matches_definition(defs):
    lookup = unit_lookup(defs)
    for code, expected in PRESSURE_TO_PA.items():
        unit = lookup[normalize_unit_text(code)]
        assert to_si(1.0, unit) == pytest.approx(expected)
        assert from_si(expected, unit) == pytest.approx(1.0)


@pytest.mark.parametrize("code", PRESSURE_CODES)
@pytest.mark.parametrize("value", [0.0, 1.0, -1.0, 12.5, 1400.0])
def test_pressure_roundtrip_two_way(defs, code, value):
    unit = resolve_unit(code, defs)
    assert unit is not None, code
    si = to_si(value, unit)
    assert from_si(si, unit) == pytest.approx(value)


def test_cross_unit_conversion(defs):
    bar = resolve_unit("bar", defs)
    psi = resolve_unit("psi", defs)
    assert bar is not None and psi is not None
    assert convert(1.0, bar, psi) == pytest.approx(14.5037738, rel=1e-6)


def test_temperature_offset_roundtrip(defs):
    celsius = resolve_unit("°C", defs)
    fahrenheit = resolve_unit("°F", defs)
    kelvin = resolve_unit("K", defs)
    assert celsius and fahrenheit and kelvin
    assert to_si(0.0, celsius) == pytest.approx(273.15)
    assert to_si(100.0, celsius) == pytest.approx(373.15)
    assert from_si(273.15, celsius) == pytest.approx(0.0)
    assert to_si(32.0, fahrenheit) == pytest.approx(273.15)
    assert from_si(273.15, fahrenheit) == pytest.approx(32.0, rel=1e-9)
    assert from_si(273.15, kelvin) == pytest.approx(273.15)


@pytest.mark.parametrize(
    "raw, expected_code",
    [
        ("kgf/cm²", "kgf/cm2"),
        ("% RH", "%RH"),
        ("%RH", "%RH"),
        ("độ C", "°C"),
        ("oC", "°C"),
        ("°C", "°C"),
        ("mbar.", "mbar"),
        ("mmH2O", "mmH2O"),
        ("µm", "µm"),
        ("μm", "µm"),
    ],
)
def test_normalize_and_resolve_aliases(defs, raw, expected_code):
    unit = resolve_unit(raw, defs)
    assert unit is not None, raw
    assert unit.code == expected_code


@pytest.mark.parametrize("raw", ["furlong", "hPa abs", "", None, "không rõ"])
def test_unknown_units_are_refused(defs, raw):
    assert resolve_unit(raw, defs) is None
    assert convert_to_si(1.0, raw, defs) is None


def test_convert_quantity_to_si_range(defs):
    parsed = parse_quantity("(0 ÷ 100) %RH")
    assert parsed is not None
    result = convert_quantity_to_si(parsed, defs)
    assert result.resolved is True
    assert result.unit_code == "%RH"
    assert result.value_min == pytest.approx(0.0)
    assert result.value_max == pytest.approx(100.0)


def test_convert_quantity_to_si_refuses_unknown_unit(defs):
    parsed = parse_quantity("5 furlong")
    assert parsed is not None
    result = convert_quantity_to_si(parsed, defs)
    assert result == SiConversion(None, None, None, False)
    assert result.value_min is None
    assert result.value_max is None


def test_db_units_resolve_like_seed(session):
    defs = load_unit_defs(session)
    assert len(defs) == len(UNITS)
    assert resolve_unit("kgf/cm²", defs).code == "kgf/cm2"
    assert resolve_unit("% RH", defs).code == "%RH"
    assert resolve_unit("độ C", defs).code == "°C"


def test_every_unit_points_to_a_known_quantity(session):
    codes = {q.code for q in session.query(Quantity).all()}
    assert {"pressure", "temperature", "humidity", "length"} <= codes
    for row in UNITS:
        assert row["quantity_id"] in {q.id for q in session.query(Quantity).all()}
