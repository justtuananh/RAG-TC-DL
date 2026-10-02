"""Bộ đọc danh mục hồ sơ NAS (Biểu 1, 3, 4, 7) trên bản chuyển đổi của tệp thật.

Fixture ở ``tests/data/nas`` là bản ``.docx``/``.xlsx`` chuyển từ bốn hồ sơ gốc
trong ``TC_DL/``. Kỳ vọng lấy nguyên văn từ tài liệu: "nt" (như trên) kế thừa ô
cùng cột dòng trên, dòng đề mục số La Mã là ngữ cảnh nhóm, không tính lại số (P2).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from catalogs.codes import parse_codes
from catalogs.readers import read_catalog

NAS = Path(__file__).resolve().parents[2] / "data" / "nas"


@pytest.fixture(scope="module")
def standards():
    return read_catalog(NAS / "bieu3_chuan_mau.xlsx")


@pytest.fixture(scope="module")
def inspectors():
    return read_catalog(NAS / "bieu7_kdv.docx")


@pytest.fixture(scope="module")
def procedures():
    return read_catalog(NAS / "bieu4_danh_muc_qt.docx")


@pytest.fixture(scope="module")
def capabilities():
    return read_catalog(NAS / "bieu1_linh_vuc.docx")


def _by_ord(draft, ord_):
    return next(item for item in draft.items if item.ord == ord_)


# ── Biểu 3: chuẩn mẫu ────────────────────────────────────────────────────────


def test_standards_kind_and_count_skip_placeholder_rows(standards):
    assert standards.kind == "lab_standard"
    # 87 dòng dữ liệu, 3 dòng giữ chỗ chỉ có số TT (9, 32, 43) bị bỏ.
    assert len(standards.items) == 84
    assert not any(item.ord in (9, 32, 43) for item in standards.items)


def test_standard_fields_and_explicit_values(standards):
    fluke = _by_ord(standards, 1)
    assert (fluke.name, fluke.model, fluke.serial) == ("Áp kế pittông", "Fluke 7302", "1274")
    assert fluke.characteristics.startswith("Phạm vi đo: (0,2 đến 5 000) bar;")
    assert (fluke.interval_text, fluke.interval_months) == ("5 năm", 60)
    assert (fluke.last_cal_year, fluke.last_cal_month, fluke.last_cal_place) == (2020, 9, "Fluke")
    assert fluke.usage_refs == [
        ("Biểu 1/CN", "IV.1"),
        ("Biểu 1/CN", "IV.2"),
        ("Biểu 1/CN", "IV.3"),
        ("Biểu 1/CN", "IV.8"),
    ]
    assert fluke.inherited == []


def test_standard_nt_inherits_previous_row_and_keeps_quote(standards):
    mp6 = _by_ord(standards, 3)
    assert (mp6.name, mp6.model, mp6.serial) == ("Áp kế píttông (Nga)", "MΠ-6", "5393")
    assert (mp6.interval_text, mp6.interval_months) == ("1 năm", 12)
    assert (mp6.last_cal_text, mp6.last_cal_year, mp6.last_cal_month) == ("6/2021 TTĐL", 2021, 6)
    assert mp6.usage_refs == [("Biểu 1/CN", "IV.2"), ("Biểu 1/CN", "IV.3"), ("Biểu 1/CN", "IV.8")]
    assert set(mp6.inherited) == {"interval", "last_calibration", "usage"}
    # P1: nguyên văn dòng nguồn vẫn ghi "nt".
    assert "nt" in mp6.quote.split(" | ")


def test_standard_missing_model_and_multi_form_usage(standards):
    separator = _by_ord(standards, 37)
    assert (separator.name, separator.model, separator.serial) == ("Bình phân ly", None, "340")
    chamber = _by_ord(standards, 65)
    assert chamber.usage_refs == [("Biểu 1/CN", "VI.5"), ("Biểu 1/CN", "VI.6"), ("Biểu 2/CN", "7")]


def test_standard_bare_interval_number_is_not_guessed(standards):
    probe = _by_ord(standards, 76)
    assert probe.interval_text == "1"
    assert probe.interval_months is None
    assert any("76" in warning for warning in standards.warnings)


# ── Biểu 7: kiểm định viên ───────────────────────────────────────────────────


def test_inspectors_parsed_from_multi_paragraph_cells(inspectors):
    assert inspectors.kind == "inspector"
    assert len(inspectors.items) == 8
    first = inspectors.items[0]
    assert (first.name, first.birth_year) == ("Nguyễn Đăng Vinh", 1970)
    assert (first.rank, first.position) == ("Đại tá", "Giám đốc")
    assert (first.education, first.specialization) == ("Thạc sỹ", "Đo lường-Điều khiển")
    assert first.fields[0] == "Phương tiện đo điện"
    assert len(first.fields) == 5
    assert (first.card_no, first.card_date) == ("003/A1", date(2019, 10, 30))
    ha = next(item for item in inspectors.items if item.name == "Phạm Văn Hà")
    assert ha.card_no == "043/A1" and ha.birth_year == 1985


# ── Biểu 4: danh mục tiêu chuẩn, quy trình ───────────────────────────────────


def test_procedure_catalog_groups_and_count(procedures):
    assert procedures.kind == "procedure_catalog"
    # 18 + 7 + 22 + 12 + 2 + 9 dòng trong 6 nhóm (nhóm VI có 3 mục "23 TQSB 5.14x").
    assert len(procedures.items) == 70
    assert {item.group_code for item in procedures.items} == {"I", "II", "III", "IV", "V", "VI"}
    assert all(item.domain == "IV. LĨNH VỰC ĐO LƯỜNG NHIỆT - ÁP SUẤT" for item in procedures.items)


def test_procedure_catalog_row_with_nt_issuer(procedures):
    row = next(item for item in procedures.items if item.procedure_number == "1.159")
    assert (row.group_code, row.group_title) == ("I", "Lĩnh vực áp suất")
    assert row.codes[0].normalized == "QTKĐ 1.159:2021"
    # "Qps kế" là lỗi đánh máy của tài liệu: giữ nguyên văn, không sửa.
    assert row.title.startswith("Qps kế Pít tông có phạm vi đo (-1 đến 5000) bar")
    assert row.issuer == "Cục TC - ĐL - CL" and "issuer" in row.inherited
    assert row.year_issued == 2022


def test_procedure_catalog_first_group_issuer_explicit(procedures):
    first = procedures.items[0]
    assert first.codes[0].normalized == "23 QTKĐ 1.039:2001"
    assert first.issuer == "Cục TC - ĐL - CL" and first.inherited == []


# ── Biểu 1: lĩnh vực kiểm định, hiệu chuẩn ───────────────────────────────────


def test_capabilities_groups_and_count(capabilities):
    assert capabilities.kind == "capability"
    assert len(capabilities.items) == 39
    assert {item.group_code for item in capabilities.items} == {"IV", "V", "VI", "VII", "VIII"}


def test_capability_row_parameters_procedures_and_recognition(capabilities):
    piston = next(item for item in capabilities.items if item.name == "Áp kế píttông")
    assert (piston.group_code, piston.group_title) == ("IV", "PHƯƠNG TIỆN ĐO ÁP SUẤT")
    assert piston.parameters == [
        "Dải đo: Từ - 0,1 MPa đến 0 MPa; CCX: Đến 0,02",
        "Dải đo: Từ 0 MPa đến 500 MPa; CCX: Đến 0,01",
    ]
    assert [code.normalized for code in piston.procedure_codes] == [
        "23 QTKĐ 1.039:2001",
        "QTKĐ 1.019:2014",
        "QTKĐ 1.159:2021",
    ]
    assert (piston.inspector_count, piston.recognition) == (3, "duy_tri")


def test_capability_recognition_columns(capabilities):
    humidity = next(item for item in capabilities.items if item.name.startswith("Nhiệt -Ẩm kế"))
    conductivity = next(
        item for item in capabilities.items if item.name == "Thiết bị đo độ dẫn điện"
    )
    assert humidity.recognition == "mo_rong"
    assert conductivity.recognition == "bo_sung_moi"


# ── Mã tiêu chuẩn, quy trình ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "normalized", "number", "year"),
    [
        ("QTKĐ 1.019 : 2014", "QTKĐ 1.019:2014", "1.019", 2014),
        ("QTKĐ 1.159.2021", "QTKĐ 1.159:2021", "1.159", 2021),
        ("23 QTKĐ 1.0015 : 2006", "23 QTKĐ 1.0015:2006", "1.0015", 2006),
        ("ĐLVN 263 : 2014", "ĐLVN 263:2014", "263", 2014),
        ("ĐLVN 213:2009", "ĐLVN 213:2009", "213", 2009),
        ("TCVN 5199 - 1990", "TCVN 5199:1990", "5199", 1990),
        ("23 TQSB 5.144 : 2006", "23 TQSB 5.144:2006", "5.144", 2006),
    ],
)
def test_parse_codes_normalizes_common_forms(text, normalized, number, year):
    (code,) = parse_codes(text)
    assert (code.normalized, code.number, code.year) == (normalized, number, year)


def test_parse_codes_keeps_unrecognized_code_raw():
    codes = parse_codes("23 TC 130 : 2002 / MIL-STD-810C  METHOD 507.1")
    assert [code.normalized for code in codes] == ["23 TC 130:2002", "MIL-STD-810C METHOD 507.1"]
    assert codes[1].family is None and codes[1].year is None
