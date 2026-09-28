"""Soạn số liệu 20 biên bản kiểm định áp kế pittông (QTKĐ 1.159:2021).

Toàn bộ số liệu được tính tất định từ một hạt giống băm theo mã bản ghi, nên
chạy lại luôn ra cùng kết quả. Quan hệ vật lý của áp kế pittông là
``p = m·g/A0`` (bỏ qua lực đẩy Acsimet), với ``A0`` là diện tích hiệu dụng của
pittông; mọi khối lượng trong bảng 3 đều được suy ra từ quan hệ này để bảo đảm
nhất quán vật lý trong sai số 0,1 %.
"""

from __future__ import annotations

import hashlib
import math
import random
from datetime import date

# Gia tốc trọng trường dùng trong toàn bộ mẫu (khớp ô B7 sheet "Tính toán").
G = 9.786673

# Hệ số đổi đơn vị áp suất sang Pa.
UNIT_TO_PA = {"bar": 100000.0, "kgf/cm2": 98066.5, "MPa": 1000000.0}

# Nhãn đơn vị ghi ở tiêu đề bảng 3 và dòng độ không đảm bảo đo.
UNIT_LABEL3 = {"bar": "bar", "kgf/cm2": "kG/cm2", "MPa": "MPa"}

# Ký tự Wingdings cho ô đánh dấu: trống (theo mẫu) và đã đánh dấu.
MARK_EMPTY = "\uf0a3"
MARK_CHECKED = "\uf0fe"

# Bốn kiểm định viên và hai người kiểm soát, xoay vòng theo thứ tự bản ghi.
KIEM_DINH_VIEN = ["Phạm Văn Hà", "Nguyễn Thị Lan", "Trần Quốc Bảo", "Lê Minh Châu"]
NGUOI_KIEM_SOAT = ["Luyện Thanh Tùng", "Đỗ Hải Yến"]

# Bộ quả cân: 18 quả, khối lượng danh nghĩa tỷ lệ theo 18 "đơn vị" này.
_WEIGHT_UNITS = [1, 1, 2, 2, 5, 5, 10, 10, 20, 20, 50, 50, 100, 100, 200, 200, 500, 500]

# 16 mã quả cân cố định trên sheet "Chọn quả" (cột A).
CHON_QUA_MA = [
    "Gốc",
    "1",
    "2",
    "4A",
    "4B",
    "10",
    "10N",
    "20",
    "40A",
    "40B",
    "100A",
    "100B",
    "100C",
    "100D",
    "100E",
    "100F",
]

# 12 thiết bị: ký hiệu, hãng/nước, số hiệu, phạm vi, đơn vị, cấp chính xác,
# đơn vị sử dụng, và khối lượng toàn thang mong muốn (kg) để chọn A0.
DEVICES = {
    "D01": dict(
        ky_hieu="МП-6",
        hang_nuoc="Nga",
        so_hieu="6112",
        range_text="(0,4 đến 6) bar",
        unit="bar",
        low=0.4,
        high=6.0,
        acc_class=0.02,
        don_vi_su_dung="Phòng Đo lường Nhiệt-Áp suất, Trung tâm Đo lường",
        target_kg=20.0,
    ),
    "D02": dict(
        ky_hieu="МП-60",
        hang_nuoc="Nga",
        so_hieu="1045",
        range_text="(1 đến 60) kgf/cm2",
        unit="kgf/cm2",
        low=1.0,
        high=60.0,
        acc_class=0.05,
        don_vi_su_dung="Công ty CP Cơ khí Thủy lực Hải An",
        target_kg=60.0,
    ),
    "D03": dict(
        ky_hieu="МП-600",
        hang_nuoc="Nga",
        so_hieu="2218",
        range_text="(10 đến 600) kgf/cm2",
        unit="kgf/cm2",
        low=10.0,
        high=600.0,
        acc_class=0.05,
        don_vi_su_dung="Nhà máy Nhiệt điện Sông Lam",
        target_kg=100.0,
    ),
    "D04": dict(
        ky_hieu="МП-2500",
        hang_nuoc="Nga",
        so_hieu="0391",
        range_text="(50 đến 2 500) kgf/cm2",
        unit="kgf/cm2",
        low=50.0,
        high=2500.0,
        acc_class=0.05,
        don_vi_su_dung="Nhà máy Nhiệt điện Sông Lam",
        target_kg=150.0,
    ),
    "D05": dict(
        ky_hieu="580",
        hang_nuoc="DH-Budenberg / Anh",
        so_hieu="58-3312",
        range_text="(1 đến 700) bar",
        unit="bar",
        low=1.0,
        high=700.0,
        acc_class=0.02,
        don_vi_su_dung="Công ty TNHH Khí công nghiệp Đông Phương",
        target_kg=70.0,
    ),
    "D06": dict(
        ky_hieu="CPB5800",
        hang_nuoc="WIKA / Đức",
        so_hieu="1A0043219",
        range_text="(1 đến 1 200) bar",
        unit="bar",
        low=1.0,
        high=1200.0,
        acc_class=0.02,
        don_vi_su_dung="Công ty TNHH Khí công nghiệp Đông Phương",
        target_kg=100.0,
    ),
    "D07": dict(
        ky_hieu="P3125",
        hang_nuoc="Fluke / Mỹ",
        so_hieu="4471",
        range_text="(1 đến 1 100) bar",
        unit="bar",
        low=1.0,
        high=1100.0,
        acc_class=0.02,
        don_vi_su_dung="Viện Cơ khí Năng lượng Miền Trung",
        target_kg=100.0,
    ),
    "D08": dict(
        ky_hieu="280",
        hang_nuoc="Budenberg / Anh",
        so_hieu="B280-7702",
        range_text="(0,2 đến 280) bar",
        unit="bar",
        low=0.2,
        high=280.0,
        acc_class=0.05,
        don_vi_su_dung="Trung tâm Kiểm định Kỹ thuật An toàn Khu vực 4",
        target_kg=50.0,
    ),
    "D09": dict(
        ky_hieu="YS-600",
        hang_nuoc="Xinghua / Trung Quốc",
        so_hieu="YS600-19087",
        range_text="(1 đến 60) MPa",
        unit="MPa",
        low=1.0,
        high=60.0,
        acc_class=0.05,
        don_vi_su_dung="Công ty CP Lọc hóa dầu Minh Sơn",
        target_kg=60.0,
    ),
    "D10": dict(
        ky_hieu="T2300",
        hang_nuoc="Pressurements / Anh",
        so_hieu="T23-0512",
        range_text="(-1 đến 2) bar",
        unit="bar",
        low=-1.0,
        high=2.0,
        acc_class=0.02,
        don_vi_su_dung="Viện Cơ khí Năng lượng Miền Trung",
        target_kg=5.0,
    ),
    "D11": dict(
        ky_hieu="PG7601",
        hang_nuoc="Fluke / Mỹ",
        so_hieu="1520",
        range_text="(0,005 đến 0,4) MPa",
        unit="MPa",
        low=0.005,
        high=0.4,
        acc_class=0.01,
        don_vi_su_dung="Phòng Đo lường Nhiệt-Áp suất, Trung tâm Đo lường",
        target_kg=5.0,
    ),
    "D12": dict(
        ky_hieu="МП-60",
        hang_nuoc="Nga",
        so_hieu="1046",
        range_text="(1 đến 60) kgf/cm2",
        unit="kgf/cm2",
        low=1.0,
        high=60.0,
        acc_class=0.05,
        don_vi_su_dung="Công ty CP Cơ khí Thủy lực Hải An",
        target_kg=60.0,
    ),
}

# Kế hoạch 20 biên bản: (mã thiết bị, ngày kiểm định, trạng thái).
# Trạng thái "khong_dat" kèm lý do ngắn; các bản còn lại đều Đạt.
PLAN = [
    ("D03", "2022-09-05", "dat"),
    ("D08", "2022-12-15", "dat"),
    ("D05", "2023-02-08", "dat"),
    ("D01", "2023-03-14", "dat"),
    ("D02", "2023-06-20", "dat"),
    ("D03", "2023-09-11", "dat"),
    ("D08", "2023-12-12", "dat"),
    ("D05", "2024-02-06", "dat"),
    ("D01", "2024-03-12", "dat"),
    ("D02", "2024-06-25", "khong_dat_do_kin"),
    ("D02", "2024-07-10", "dat"),
    ("D07", "2024-08-27", "dat"),
    ("D04", "2024-11-19", "dat"),
    ("D01", "2025-03-18", "dat"),
    ("D06", "2025-05-21", "dat"),
    ("D12", "2025-08-12", "dat"),
    ("D09", "2025-10-07", "dat"),
    ("D10", "2026-01-13", "dat"),
    ("D11", "2026-04-22", "dat"),
    ("D06", "2026-05-19", "khong_dat_quay_tu_do"),
]

_LY_DO = {
    "khong_dat_do_kin": "độ kín: độ giảm áp sau 5 min vượt 30 kPa",
    "khong_dat_quay_tu_do": "thời gian quay tự do dưới 180 s",
}


def _rng(seed_text: str) -> random.Random:
    """Sinh nguồn ngẫu nhiên tất định từ một chuỗi hạt giống."""
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def vi(x: float, nd: int = 0) -> str:
    """Định dạng số kiểu Việt: phẩy thập phân, khoảng trắng phân nhóm nghìn."""
    text = f"{x:,.{nd}f}".replace(",", "\u00a0").replace(".", ",")
    return text


def acc_text(acc_class: float) -> str:
    """Cấp chính xác dạng chuỗi kiểu Việt (``0.02`` → ``0,02``)."""
    return f"{acc_class:.2f}".replace(".", ",")


def _a0_for(dev: dict) -> float:
    """Chọn diện tích hiệu dụng A0 (m2) để toàn thang có khối lượng hợp lý."""
    high_pa = dev["high"] * UNIT_TO_PA[dev["unit"]]
    return dev["target_kg"] * G / high_pa


def _a0_text(a0: float) -> str:
    """Diện tích hiệu dụng dạng mẫu ``A0 = 0,99924 × 10-4 , m2``."""
    exponent = math.floor(math.log10(a0)) + 1
    mantissa = a0 / (10.0**exponent)
    return f"A0 = {vi(mantissa, 5)} × 10{exponent} , m2"


def _uncertainty(dev: dict) -> dict:
    """Độ không đảm bảo đo và độ chính xác d theo cấp chính xác."""
    max_err = dev["acc_class"] / 100.0 * dev["high"]
    u_cmax = 0.63 * max_err
    return {
        "u_cmax": round(u_cmax, 12),
        "u_p": round(2.0 * u_cmax, 12),
        "delta_p": 0.0,
        "do_chinh_xac_d": round(0.9 * dev["acc_class"] / 100.0, 12),
    }


def _weights(max_mass_g: float, allowed: float, rng: random.Random) -> list[dict]:
    """18 quả cân: khối lượng danh nghĩa, thực tế, sai số tương đối, cho phép."""
    base = max_mass_g / sum(_WEIGHT_UNITS)
    rows: list[dict] = []
    for index, unit in enumerate(_WEIGHT_UNITS, start=1):
        nominal = round(unit * base, 3)
        sai_so = min(round(allowed * rng.uniform(0.08, 0.65), 3), allowed)
        actual = round(nominal * (1.0 + sai_so / 100.0), 5)
        rows.append(
            {
                "tt": index,
                "ten": str(index),
                "kl_danh_nghia": nominal,
                "kl_thuc_te": actual,
                "sai_so": sai_so,
                "cho_phep": allowed,
            }
        )
    return rows


def _chon_qua(weights: list[dict], a0: float, dev: dict) -> list[dict]:
    """16 mã quả cân (sheet ``Chọn quả``) khớp khối lượng quả cân của thiết bị."""
    factor = UNIT_TO_PA[dev["unit"]]
    ordered = sorted(weights, key=lambda row: row["kl_thuc_te"])[2:]
    rows: list[dict] = []
    for ma, weight in zip(CHON_QUA_MA, ordered, strict=True):
        mass_g = weight["kl_thuc_te"]
        pressure = mass_g * 0.001 * G / a0 / factor
        rows.append({"ma": ma, "kl": mass_g, "ap_suat": round(pressure, 6)})
    return rows


def _table3(dev: dict, a0: float, rng: random.Random) -> list[dict]:
    """10 điểm áp suất danh nghĩa từ 10 % đến 100 % phạm vi, khớp ``p·A0/g``."""
    factor = UNIT_TO_PA[dev["unit"]]
    rows: list[dict] = []
    for index in range(1, 11):
        p = round(dev["high"] * index / 10.0, 8)
        mass_g = p * factor * a0 / G * 1000.0
        trim = round(rng.uniform(0.002, 0.05), 3)
        weight_mass = round(mass_g - trim, 5)
        combo = ",".join(str(x) for x in sorted(rng.sample(range(1, 19), rng.randint(2, 4))))
        rows.append(
            {
                "tt": index,
                "ap_suat_danh_nghia": p,
                "so_hieu_qua_can": combo,
                "kl_qua_can": weight_mass,
                "so_gam_them": trim,
                "tong_kl": round(mass_g, 5),
                "ap_suat_khi_quyen": round(1010.0 + rng.uniform(-6.0, 6.0), 2),
                "do_am": round(60.0 + rng.uniform(-5.0, 5.0), 1),
                "nhiet_do": round(20.0 + rng.uniform(-1.0, 1.0), 1),
            }
        )
    return rows


def _bang_2_1(rng: random.Random, status: str) -> dict:
    """Thông số bảng 2.1; bản độ kín có độ giảm áp vượt 30 kPa."""
    giam_ap = round(
        rng.uniform(32.0, 38.0) if status == "khong_dat_do_kin" else rng.uniform(12.0, 24.0), 1
    )
    return {
        "vuong_goc_phut": round(rng.uniform(2.0, 4.0), 1),
        "vuong_goc_cho_phep": 5.0,
        "giam_ap_kpa": giam_ap,
        "giam_ap_cho_phep": 30.0,
        "vt1": 0.3,
        "vt2": 0.3,
        "ty_so": 100.0,
        "ty_so_cho_phep": 110.0,
    }


def _bang_2_2(rng: random.Random, status: str) -> dict:
    """Thời gian quay tự do; bản quay chậm có trung bình dưới 180 s."""
    if status == "khong_dat_quay_tu_do":
        cw, ccw = round(rng.uniform(148.0, 160.0), 1), round(rng.uniform(150.0, 162.0), 1)
    else:
        cw, ccw = round(rng.uniform(198.0, 214.0), 1), round(rng.uniform(196.0, 212.0), 1)
    return {
        "quay_cw": cw,
        "quay_ccw": ccw,
        "trung_binh": round((cw + ccw) / 2.0, 2),
        "cho_phep": 180.0,
    }


def _bang_2_3(rng: random.Random) -> dict:
    """Tốc độ hạ pittông: ba lượt và trung bình, cho phép ≤ 0,4 mm/min."""
    values = [round(rng.uniform(0.30, 0.38), 2) for _ in range(3)]
    return {
        "luot1": values[0],
        "luot2": values[1],
        "luot3": values[2],
        "trung_binh": round(sum(values) / 3.0, 3),
        "cho_phep": 0.4,
    }


def _phuong_tien(dev: dict) -> str:
    """Chọn áp kế pittông tiêu chuẩn theo dải áp suất của thiết bị."""
    high_pa = dev["high"] * UNIT_TO_PA[dev["unit"]]
    return "Áp kế píttông PG7302" if high_pa >= 1.0e7 else "Áp kế píttông PG7202"


def _device_fields(code: str, dev: dict, day_text: str, number: str) -> dict:
    """Các trường định danh thiết bị của một bản ghi."""
    return {
        "id": f"{code}-{day_text}",
        "device_code": code,
        "ky_hieu": dev["ky_hieu"],
        "hang_nuoc": dev["hang_nuoc"],
        "so_hieu": dev["so_hieu"],
        "pham_vi_text": dev["range_text"],
        "pham_vi_don_vi": dev["unit"],
        "range_low": dev["low"],
        "range_high": dev["high"],
        "cap_chinh_xac": acc_text(dev["acc_class"]),
        "accuracy_class": dev["acc_class"],
        "don_vi_su_dung": dev["don_vi_su_dung"],
        "ngay_kiem_dinh": day_text,
        "so_bien_ban": number,
        "so_bien_ban_text": f"{number}/{day_text[:4]}",
    }


def _verdict_fields(dev: dict, status: str, index: int) -> dict:
    """Kết quả từng mục, kết luận, người ký và điều kiện môi trường."""
    ky_thuat = "Không đạt" if status.startswith("khong_dat") else "Đạt"
    if status.startswith("khong_dat"):
        ket_luan = f"4. Kết luận: Không đạt yêu cầu kỹ thuật đo lường ({_LY_DO[status]})"
    else:
        ket_luan = "4. Kết luận: Đạt yêu cầu kỹ thuật đo lường"
    return {
        "ket_qua": {
            "ben_ngoai": "Đạt",
            "ky_thuat": ky_thuat,
            "do_luong": "Đạt",
            "do_nhay": "Đạt",
        },
        "ket_luan": ket_luan,
        "ly_do_khong_dat": _LY_DO.get(status),
        "kiem_dinh_vien": KIEM_DINH_VIEN[index % len(KIEM_DINH_VIEN)],
        "nguoi_kiem_soat": NGUOI_KIEM_SOAT[index % len(NGUOI_KIEM_SOAT)],
        "phuong_tien": _phuong_tien(dev),
        "nhiet_do_mt": f"({20 + (index % 3)} ± 2) ºC",
        "do_am_mt": f"({58 + (index % 6)} ± 5) %RH",
    }


def _make_record(code: str, day_text: str, status: str, number: str, index: int) -> dict:
    """Dựng đầy đủ số liệu một biên bản."""
    dev = DEVICES[code]
    a0 = _a0_for(dev)
    rng = _rng(f"{code}|{day_text}")
    allowed = round(0.75 * dev["acc_class"], 4)
    max_mass_g = dev["high"] * UNIT_TO_PA[dev["unit"]] * a0 / G * 1000.0
    weights = _weights(max_mass_g, allowed, rng)
    return {
        **_device_fields(code, dev, day_text, number),
        **_verdict_fields(dev, status, index),
        "a0": a0,
        "a0_text": _a0_text(a0),
        "bang_2": weights,
        "chon_qua": _chon_qua(weights, a0, dev),
        "bang_2_1": _bang_2_1(rng, status),
        "bang_2_2": _bang_2_2(rng, status),
        "bang_2_3": _bang_2_3(rng),
        "bang_3": _table3(dev, a0, rng),
        **_uncertainty(dev),
    }


def build_records() -> list[dict]:
    """Dựng 20 bản ghi theo ma trận, đánh số biên bản tăng dần theo ngày."""
    ordered = sorted(PLAN, key=lambda item: (item[1], item[0]))
    records: list[dict] = []
    for index, (code, day_text, status) in enumerate(ordered):
        records.append(_make_record(code, day_text, status, f"{index + 1:03d}", index))
    return records


def record_date(record: dict) -> date:
    """Ngày kiểm định của bản ghi (dùng cho test)."""
    return date.fromisoformat(record["ngay_kiem_dinh"])
