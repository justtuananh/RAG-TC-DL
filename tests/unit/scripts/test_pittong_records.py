"""Test 20 biên bản kiểm định áp kế pittông sinh từ tệp mẫu (Pha 0).

Kiểm bốn nhóm: (1) tính đúng của ``spec.json``; (2) nhất quán vật lý của số liệu;
(3) build ``--no-recalc`` ghi đúng ô trên OOXML thô; (4) build có tính lại
LibreOffice cho mọi ô công thức giá trị cache ``<v>``.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest
from lxml import etree

from scripts.pittong_records import build, spec_data

_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_TEMPLATE_SHA = "bf4080c50ef4b45423aadaf94ec9fe1aa5513949373882a95781b9daa87a11fb"
_EPOCH = date(1899, 12, 30)


def _spec() -> dict:
    return json.loads(build.SPEC_PATH.read_text(encoding="utf-8"))


def _sheet_paths(archive: zipfile.ZipFile) -> dict[str, str]:
    """Ánh xạ tên sheet → đường dẫn XML trong gói."""
    workbook = etree.fromstring(archive.read("xl/workbook.xml"))
    rels = etree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.get("Id"): rel.get("Target") for rel in rels.findall(_PKG + "Relationship")}
    return {
        sheet.get("name"): "xl/" + rel_map[sheet.get(_R + "id")].lstrip("/")
        for sheet in workbook.iter(_M + "sheet")
    }


def _read_sheet(path: Path, sheet: str) -> dict[str, str]:
    """Đọc một sheet thành ``{địa chỉ: giá trị}``, giải shared string."""
    with zipfile.ZipFile(path) as archive:
        try:
            shared_root = etree.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [
                "".join(t.text or "" for t in si.iter(_M + "t"))
                for si in shared_root.findall(_M + "si")
            ]
        except KeyError:
            shared = []
        root = etree.fromstring(archive.read(_sheet_paths(archive)[sheet]))
    cells: dict[str, str] = {}
    for cell in root.iter(_M + "c"):
        cell_type = cell.get("t")
        value = cell.find(_M + "v")
        if cell_type == "inlineStr":
            cells[cell.get("r")] = "".join(x.text or "" for x in cell.iter(_M + "t"))
        elif value is None:
            continue
        elif cell_type == "s":
            cells[cell.get("r")] = shared[int(value.text)]
        else:
            cells[cell.get("r")] = value.text
    return cells


def _violations(record: dict) -> list[str]:
    """Các giá trị vượt giới hạn cho phép của một bản ghi."""
    found: list[str] = []
    for row in record["bang_2"]:
        if row["sai_so"] > row["cho_phep"] + 1e-12:
            found.append(f"quả cân {row['tt']}")
    b21, b22, b23 = record["bang_2_1"], record["bang_2_2"], record["bang_2_3"]
    if b21["giam_ap_kpa"] > b21["giam_ap_cho_phep"]:
        found.append("độ giảm áp")
    if b21["vuong_goc_phut"] >= b21["vuong_goc_cho_phep"]:
        found.append("độ vuông góc")
    if b21["ty_so"] > b21["ty_so_cho_phep"]:
        found.append("tỷ số tốc độ hạ")
    if min(b22["trung_binh"], b22["quay_cw"], b22["quay_ccw"]) < b22["cho_phep"]:
        found.append("thời gian quay tự do")
    if max(b23["luot1"], b23["luot2"], b23["luot3"], b23["trung_binh"]) > b23["cho_phep"]:
        found.append("tốc độ hạ")
    return found


def test_spec_20_records_12_devices() -> None:
    spec = _spec()
    assert spec["count"] == 20
    assert len(spec["records"]) == 20
    assert len({r["device_code"] for r in spec["records"]}) == 12


def test_same_serial_consistent() -> None:
    groups: dict[str, set[tuple]] = {}
    for record in _spec()["records"]:
        signature = (
            record["ky_hieu"],
            record["hang_nuoc"],
            record["pham_vi_text"],
            record["cap_chinh_xac"],
            record["don_vi_su_dung"],
        )
        groups.setdefault(record["so_hieu"], set()).add(signature)
    assert all(len(signatures) == 1 for signatures in groups.values())


def test_dates_in_range() -> None:
    low, high = date(2022, 1, 1), date(2026, 9, 27)
    for record in _spec()["records"]:
        assert low <= date.fromisoformat(record["ngay_kiem_dinh"]) <= high


def test_khong_dat_count_and_reasons() -> None:
    records = _spec()["records"]
    failed = [r for r in records if r["ket_qua"]["ky_thuat"] != "Đạt"]
    assert len(failed) == 2
    assert {r["so_hieu"] for r in failed} == {"1045", "1A0043219"}
    for record in failed:
        assert record["ly_do_khong_dat"]
        assert record["ket_luan"].startswith("4. Kết luận: Không đạt yêu cầu kỹ thuật đo lường (")


def test_table3_points_increasing_in_range() -> None:
    for record in _spec()["records"]:
        points = [row["ap_suat_danh_nghia"] for row in record["bang_3"]]
        assert len(points) == 10
        assert points == sorted(points)
        assert all(record["range_low"] <= p <= record["range_high"] for p in points)


def test_table3_mass_matches_physics() -> None:
    for record in _spec()["records"]:
        factor = spec_data.UNIT_TO_PA[record["pham_vi_don_vi"]]
        for row in record["bang_3"]:
            expected = row["ap_suat_danh_nghia"] * factor * record["a0"] / spec_data.G * 1000.0
            total = row["kl_qua_can"] + row["so_gam_them"]
            assert abs(total - expected) / expected < 1e-3


def test_pass_fail_values_are_consistent() -> None:
    for record in _spec()["records"]:
        violations = _violations(record)
        if record["ket_qua"]["ky_thuat"] == "Đạt":
            assert violations == []
        else:
            assert violations


def test_manifest_covers_truth(tmp_path: Path) -> None:
    entries = build.build_all(tmp_path, recalc=False)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["count"] == 20
    for entry in entries:
        assert entry["file"].startswith("Biên bản kiểm định áp kế pittông SN ")
        assert "QTKĐ" not in entry["file"] and "QTKD" not in entry["file"]
        path = tmp_path / entry["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
        assert {"so_hieu", "bang_2", "bang_3", "a0", "u_p"} <= set(entry)


def test_build_no_recalc_writes_fields(tmp_path: Path) -> None:
    build.build_all(tmp_path, recalc=False)
    for record in _spec()["records"]:
        cells = _read_sheet(tmp_path / build._filename(record), "KQ KĐ")
        moment = date.fromisoformat(record["ngay_kiem_dinh"])
        assert cells["E3"] == f"Hà Nội, ngày {moment:%d} tháng {moment:%m} năm {moment:%Y}"
        assert cells["E6"] == f"Số: {record['so_bien_ban_text']}"
        assert cells["C9"] == record["ky_hieu"]
        assert cells["G9"] == record["so_hieu"]
        assert cells["D10"] == record["hang_nuoc"]
        assert cells["B12"] == f"Phạm vi đo: {record['pham_vi_text']};"
        assert cells["B13"] == f"Cấp chính xác: {record['cap_chinh_xac']}"
        assert cells["A14"] == f"Đơn vị sử dụng: {record['don_vi_su_dung']}"
        serial = float(cells["E20"])
        assert _EPOCH + timedelta(days=serial) == moment


def test_e6_certificate_number_fits_merged_cell(tmp_path: Path) -> None:
    """Ô E6 (gộp E6:F6, hẹp) đủ ngắn để không bị cắt khi in: ≤ 13 ký tự, "Số: "."""
    build.build_all(tmp_path, recalc=False)
    for record in _spec()["records"]:
        cells = _read_sheet(tmp_path / build._filename(record), "KQ KĐ")
        e6 = cells["E6"]
        assert e6.startswith("Số: ")
        assert len(e6) <= 13
        assert re.fullmatch(r"Số: \d{3}/\d{4}", e6)
        assert e6 == f"Số: {record['so_bien_ban_text']}"


def test_chon_qua_and_mass_column_match_table2(tmp_path: Path) -> None:
    build.build_all(tmp_path, recalc=False)
    for record in _spec()["records"]:
        masses = {row["kl_thuc_te"] for row in record["bang_2"]}
        assert all(row["kl"] in masses for row in record["chon_qua"])
        cells = _read_sheet(tmp_path / build._filename(record), "Tính toán")
        column = [float(cells[f"S{r}"]) for r in range(3, 21)]
        assert column == [row["kl_thuc_te"] for row in record["bang_2"]]


def test_table3_header_units_and_a0(tmp_path: Path) -> None:
    build.build_all(tmp_path, recalc=False)
    for record in _spec()["records"]:
        label = spec_data.UNIT_LABEL3[record["pham_vi_don_vi"]]
        cells = _read_sheet(tmp_path / build._filename(record), "KQ KĐ (2)")
        assert cells["B4"] == f"Áp suất danh nghĩa,\n({label})"
        assert f"({label})" in cells["D18"]
        assert f"({label})" in cells["D19"]
        assert cells["D16"] == record["a0_text"]
        assert abs(float(cells["N5"]) - record["a0"]) < 1e-18
        assert float(cells["D21"]) == record["do_chinh_xac_d"]


def test_build_no_recalc_marks_correct_positions(tmp_path: Path) -> None:
    build.build_all(tmp_path, recalc=False)
    for record in _spec()["records"]:
        cells = _read_sheet(tmp_path / build._filename(record), "KQ KĐ")
        for passed, failed, status, passed_label in (
            ("B25", "B26", record["ket_qua"]["ben_ngoai"], "Đạt"),
            ("B28", "B29", record["ket_qua"]["ky_thuat"], "Đạt"),
            ("B31", "B32", record["ket_qua"]["do_luong"], "Đạt"),
            ("B69", "B70", record["ket_qua"]["do_nhay"], "Đạt"),
        ):
            on = status == passed_label
            assert (
                cells[passed]
                == f"{spec_data.MARK_CHECKED if on else spec_data.MARK_EMPTY} {passed_label}"
            )
            assert (
                cells[failed]
                == f"{spec_data.MARK_EMPTY if on else spec_data.MARK_CHECKED} Không đạt"
            )


def test_build_deterministic(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    build.build_all(first, recalc=False)
    build.build_all(second, recalc=False)
    for record in _spec()["records"]:
        name = build._filename(record)
        for sheet in ("Chọn quả", "KQ KĐ", "KQ KĐ (2)", "Tính toán"):
            assert _read_sheet(first / name, sheet) == _read_sheet(second / name, sheet)


def test_template_unchanged() -> None:
    assert hashlib.sha256(build.TEMPLATE.read_bytes()).hexdigest() == _TEMPLATE_SHA


@pytest.mark.skipif(not Path(build.SOFFICE).exists(), reason="không có LibreOffice headless")
def test_build_recalc_fills_formula_cache(tmp_path: Path) -> None:
    entries = build.build_all(tmp_path, recalc=True, limit=1)
    record = _spec()["records"][0]
    path = tmp_path / build._filename(record)
    assert entries[0]["file"] == path.name
    with zipfile.ZipFile(path) as archive:
        missing = []
        for sheet_path in _sheet_paths(archive).values():
            root = etree.fromstring(archive.read(sheet_path))
            for cell in root.iter(_M + "c"):
                if cell.find(_M + "f") is not None and cell.find(_M + "v") is None:
                    missing.append(cell.get("r"))
    assert missing == []
    cells = _read_sheet(path, "KQ KĐ")
    mass = record["bang_2"][0]
    assert float(cells["L7"]) == mass["kl_thuc_te"]
    assert float(cells["N7"]) == mass["sai_so"]
    expected = 100.0 * mass["kl_thuc_te"] / (100.0 + mass["sai_so"])
    assert abs(float(cells["M7"]) - expected) < 1e-6
    a0 = record["a0"]
    weights = record["bang_2"]
    tinh_toan = _read_sheet(path, "Tính toán")
    for index in (0, 4, 17):
        s_value = weights[index]["kl_thuc_te"]
        expected_t = s_value * 0.001 * spec_data.G * 0.00001 / a0
        assert abs(float(tinh_toan[f"T{3 + index}"]) - expected_t) < 1e-9
        expected_u = s_value * 0.001 * 0.0001 / a0
        assert abs(float(tinh_toan[f"U{3 + index}"]) - expected_u) < 1e-9
