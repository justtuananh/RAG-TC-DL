"""Sinh 20 biên bản kiểm định áp kế pittông từ tệp mẫu.

Cách dùng::

    .venv-dev/bin/python -m scripts.pittong_records.build [--out DIR] [--no-recalc]
    .venv-dev/bin/python -m scripts.pittong_records.build --write-spec

Mỗi bản ghi được vá trực tiếp trên OOXML, sau đó tính lại công thức bằng
LibreOffice headless để mọi ô công thức có giá trị cache ``<v>`` (bộ đọc
``records/xlsx_reader.py`` không tự tính lại). Tệp ``spec.json`` là nguồn sự
thật; ``manifest.json`` ghi tên tệp, sha256 và toàn bộ giá trị sự thật.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path

from scripts.pittong_records import spec_data
from scripts.pittong_records.xlsx_patch import (
    Formula,
    InlineStr,
    Number,
    SerialDate,
    inject_caches,
    patch_workbook,
)

SOFFICE = "/usr/bin/soffice"
MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parents[1]
TEMPLATE = MODULE_DIR / "template.xlsx"
SPEC_PATH = MODULE_DIR / "spec.json"
DEFAULT_OUT = REPO_ROOT / "mau_bien_ban" / "ap_ke_pittong"
G = spec_data.G


def _mark(label: str, checked: bool) -> InlineStr:
    mark = spec_data.MARK_CHECKED if checked else spec_data.MARK_EMPTY
    return InlineStr(f"{mark} {label}")


def _table2_cells(cells: dict, record: dict) -> None:
    """Bảng 2: 18 quả cân ở khối J:O, hàng 7..24."""
    for row in record["bang_2"]:
        r = 6 + row["tt"]
        cells[f"J{r}"] = Number(row["tt"])
        cells[f"K{r}"] = InlineStr(row["ten"])
        cells[f"L{r}"] = Number(row["kl_thuc_te"])
        cells[f"N{r}"] = Number(row["sai_so"])
        cells[f"O{r}"] = Number(row["cho_phep"])


def _kq_kd_cells(record: dict) -> dict:
    """Bản vá sheet ``KQ KĐ`` (trang 1 đến 3)."""
    moment = date.fromisoformat(record["ngay_kiem_dinh"])
    cells: dict = {
        "E3": InlineStr(f"Hà Nội, ngày {moment:%d} tháng {moment:%m} năm {moment:%Y}"),
        "E6": InlineStr(f"Số: {record['so_bien_ban_text']}"),
        "C9": InlineStr(record["ky_hieu"]),
        "G9": InlineStr(record["so_hieu"]),
        "D10": InlineStr(record["hang_nuoc"]),
        "B12": InlineStr(f"Phạm vi đo: {record['pham_vi_text']};"),
        "B13": InlineStr(f"Cấp chính xác: {record['cap_chinh_xac']}"),
        "A14": InlineStr(f"Đơn vị sử dụng: {record['don_vi_su_dung']}"),
        "E16": InlineStr(record["phuong_tien"]),
        "E18": InlineStr(record["nhiet_do_mt"]),
        "E19": InlineStr(record["do_am_mt"]),
        "E20": SerialDate(moment),
        "B40": InlineStr(record["kiem_dinh_vien"]),
        "F40": InlineStr(record["nguoi_kiem_soat"]),
    }
    ket_qua = record["ket_qua"]
    cells["B25"] = _mark("Đạt", ket_qua["ben_ngoai"] == "Đạt")
    cells["B26"] = _mark("Không đạt", ket_qua["ben_ngoai"] == "Không đạt")
    cells["B28"] = _mark("Đạt", ket_qua["ky_thuat"] == "Đạt")
    cells["B29"] = _mark("Không đạt", ket_qua["ky_thuat"] == "Không đạt")
    cells["B31"] = _mark("Đạt", ket_qua["do_luong"] == "Đạt")
    cells["B32"] = _mark("Không đạt", ket_qua["do_luong"] == "Không đạt")
    cells["B69"] = _mark("Đạt", ket_qua["do_nhay"] == "Đạt")
    cells["B70"] = _mark("Không đạt", ket_qua["do_nhay"] == "Không đạt")
    _table2_cells(cells, record)
    b21, b22, b23 = record["bang_2_1"], record["bang_2_2"], record["bang_2_3"]
    cells["F48"] = Number(b21["vuong_goc_phut"])
    cells["F51"] = Number(b21["giam_ap_kpa"])
    cells["F52"] = InlineStr(f"Vt1 = {spec_data.vi(b21['vt1'], 1)}")
    cells["F53"] = InlineStr(f"Vt2 = {spec_data.vi(b21['vt2'], 1)}")
    cells["F54"] = Number(b21["ty_so"])
    cells["A60"] = Number(b22["quay_cw"])
    cells["D60"] = Number(b22["quay_ccw"])
    cells["F60"] = Number(b22["trung_binh"])
    cells["A66"] = Number(b23["luot1"])
    cells["C66"] = Number(b23["luot2"])
    cells["E66"] = Number(b23["luot3"])
    cells["F66"] = Number(b23["trung_binh"])
    return cells


def _kq_kd2_cells(record: dict) -> dict:
    """Bản vá sheet ``KQ KĐ (2)`` (trang 4)."""
    unit_label = spec_data.UNIT_LABEL3[record["pham_vi_don_vi"]]
    cells: dict = {
        "B4": InlineStr(f"Áp suất danh nghĩa,\n({unit_label})"),
        "N5": Number(record["a0"]),
        "D16": InlineStr(record["a0_text"]),
        "D18": InlineStr(f"{spec_data.vi(record['u_cmax'] * 1000, 3)} × 10-3 ({unit_label}) "),
        "D19": InlineStr(f"{spec_data.vi(record['u_p'] * 1000, 3)} × 10-3 ({unit_label}) "),
        "D20": Number(record["delta_p"]),
        "D21": Number(record["do_chinh_xac_d"]),
        "A23": InlineStr(record["ket_luan"]),
    }
    p_ref = record["bang_3"][6]["ap_suat_danh_nghia"]
    cells["F18"] = InlineStr(f"tại p = {spec_data.vi(p_ref, 1)} {unit_label}")
    for row in record["bang_3"]:
        r = 5 + row["tt"]
        cells[f"B{r}"] = Number(row["ap_suat_danh_nghia"])
        cells[f"C{r}"] = InlineStr(row["so_hieu_qua_can"])
        cells[f"D{r}"] = Number(row["kl_qua_can"])
        cells[f"E{r}"] = Number(row["so_gam_them"])
        cells[f"G{r}"] = Number(row["ap_suat_khi_quyen"])
        cells[f"H{r}"] = Number(row["do_am"])
        cells[f"I{r}"] = Number(row["nhiet_do"])
    return cells


def _tinh_toan_cells(record: dict) -> dict:
    """Bản vá sheet ``Tính toán``: cột S + hằng số A0 trong công thức T/U.

    T4/U4 là ô chủ của công thức chia sẻ (``t="shared"``, ``ref`` T4:T20 và
    U4:U20); chỉ cần sửa hai ô chủ này là mọi ô T5..T20/U5..U20 dùng A0 mới.
    """
    a0 = repr(record["a0"])
    cells: dict = {}
    for index, weight in enumerate(record["bang_2"]):
        cells[f"S{3 + index}"] = Number(weight["kl_thuc_te"])
    for column in "IJKLM":
        cells[f"{column}3"] = Number(record["a0"])
    for r in (3, 4):
        cells[f"T{r}"] = Formula(f"(S{r}*0.001*9.786673*0.00001)/{a0}")
        cells[f"U{r}"] = Formula(f"(S{r}*0.001*0.0001)/{a0}")
    return cells


def _chon_qua_cells(record: dict) -> dict:
    """Bản vá sheet ``Chọn quả``: khối lượng và áp suất từng quả cân."""
    unit_label = spec_data.UNIT_LABEL3[record["pham_vi_don_vi"]]
    cells: dict = {"G1": InlineStr(f"Áp suất ({unit_label})")}
    for index, row in enumerate(record["chon_qua"]):
        r = 2 + index
        cells[f"B{r}"] = Number(row["kl"])
        cells[f"C{r}"] = Number(row["ap_suat"])
    return cells


def patches_for(record: dict) -> dict[str, dict]:
    """Toàn bộ bản vá cho một bản ghi, theo tên sheet."""
    return {
        "Chọn quả": _chon_qua_cells(record),
        "KQ KĐ": _kq_kd_cells(record),
        "KQ KĐ (2)": _kq_kd2_cells(record),
        "Tính toán": _tinh_toan_cells(record),
    }


def _filename(record: dict) -> str:
    """Tên tệp biên bản (không chứa mã QTKĐ)."""
    return (
        f"Biên bản kiểm định áp kế pittông SN {record['so_hieu']} {record['ngay_kiem_dinh']}.xlsx"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _recalc(src: Path, out: Path, profile: str) -> None:
    """Tính lại công thức bằng LibreOffice headless, ghi kết quả ra ``out``."""
    with tempfile.TemporaryDirectory(prefix="pittong_recalc_") as tmp:
        out_dir = Path(tmp) / "out"
        out_dir.mkdir()
        subprocess.run(
            [
                SOFFICE,
                f"-env:UserInstallation=file://{profile}",
                "--headless",
                "--convert-to",
                "xlsx",
                "--outdir",
                str(out_dir),
                str(src),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
        result = out_dir / src.name
        if not result.exists():
            raise RuntimeError(f"LibreOffice không tạo được kết quả cho {src.name}")
        shutil.copyfile(result, out)


def build_all(out_dir: Path, *, recalc: bool = True, limit: int | None = None) -> list[dict]:
    """Sinh các biên bản vào ``out_dir``; trả danh sách mục manifest."""
    records = json.loads(SPEC_PATH.read_text(encoding="utf-8"))["records"]
    if limit is not None:
        records = records[:limit]
    out_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="pittong_build_") as tmp:
        profile = str(Path(tmp) / "lo_profile")
        for record in records:
            staged = Path(tmp) / "book.xlsx"
            patch_workbook(TEMPLATE, staged, patches_for(record))
            if recalc:
                computed = Path(tmp) / "computed.xlsx"
                _recalc(staged, computed, profile)
                inject_caches(staged, computed)
            target = out_dir / _filename(record)
            shutil.copyfile(staged, target)
            entries.append({"file": target.name, "sha256": _sha256(target), **record})
    (out_dir / "manifest.json").write_text(
        json.dumps({"count": len(entries), "records": entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return entries


def write_spec() -> Path:
    """Sinh ``spec.json`` tất định từ ``spec_data``."""
    records = spec_data.build_records()
    SPEC_PATH.write_text(
        json.dumps({"count": len(records), "records": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return SPEC_PATH


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sinh biên bản kiểm định áp kế pittông.")
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help="Thư mục xuất (mặc định mau_bien_ban/ap_ke_pittong).",
    )
    parser.add_argument(
        "--no-recalc", action="store_true", help="Không chạy LibreOffice tính lại công thức."
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Chỉ sinh N bản ghi đầu (tiện test)."
    )
    parser.add_argument("--write-spec", action="store_true", help="Sinh spec.json rồi thoát.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Điểm vào CLI."""
    args = _parse_args(argv)
    if args.write_spec:
        path = write_spec()
        print(f"Đã ghi {path}")
        return 0
    entries = build_all(Path(args.out), recalc=not args.no_recalc, limit=args.limit)
    for entry in entries:
        print(entry["file"])
    print(f"Tổng: {len(entries)} tệp trong {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
