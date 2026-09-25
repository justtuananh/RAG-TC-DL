"""Nhóm B: 8 QTKĐ docx biên, mỗi file nhắm một hành vi biên (K-code).

Mỗi hàm ``case_*`` trả ``(dev, blocks)`` -- ``dev`` LUÔN được cập nhật để phản
ánh ĐÚNG những gì được render (redo R1: gold nhóm B suy từ ``dev`` bằng
``gold_a.golden_rows_for_doc`` giống nhóm A; nếu một ca biên đổi khác dev mặc
định (ví dụ đổi văn bản điều kiện môi trường) thì phải cập nhật ``dev`` tương
ứng để gold không lệch khỏi tài liệu thật). Tái dùng khối từ ``qtkd_doc`` để
phần còn lại của tài liệu vẫn "hợp lý về kỹ thuật đo lường" như nhóm A.
"""

from __future__ import annotations

import copy

from scripts.knowledge_corpus import ooxml as ox
from scripts.knowledge_corpus.devices_a import DEVICES
from scripts.knowledge_corpus.qtkd_doc import (
    _appendix,
    _appendix_table_rows,
    _bang2_rows,
    _front_matter,
    _h,
    _section_1,
    _section_3,
    _section_4,
    _section_5,
    _section_6,
    _section_7,
    _section_references,
    _section_terms,
    appendix_labels,
)


def _base_dev(number: str) -> dict:
    dev = copy.deepcopy(DEVICES[0])
    dev["number"] = number
    return dev


def case_k11_qtkd_no_dau(number: str) -> tuple[dict, list[dict]]:
    """K11: mã ``QTKD`` không dấu Đ trong dòng đầu mục và Phụ lục A."""
    dev = _base_dev(number)
    blocks = [
        ox.para("QTKD QUY TRINH KIEM DINH"),
        ox.para(f"QTKD {number} : 2026"),
        ox.para(dev["title"].upper()),
        ox.para("QUY TRINH KIEM DINH"),
        ox.para("HA NOI - 2026"),
    ]
    blocks += _section_1(dev) + _section_references(dev) + _section_terms(dev) + _section_3(dev)
    blocks += _section_4(dev) + _section_5(dev) + _section_6(dev) + _section_7(dev)
    appendix = [
        ox.heading("Phụ lục A", 1),
        ox.para("(Quy định)"),
        ox.para("MẪU BIÊN BẢN KIỂM ĐỊNH"),
    ]
    for label in appendix_labels(dev):
        if label == "Kết luận":
            continue
        if label == "Phương pháp kiểm định":
            appendix.append(ox.para(f"{label}: QTKD {number} : 2026"))  # không dấu Đ (K11)
        else:
            appendix.append(ox.para(f"{label}:"))
    appendix += [
        ox.para("Bảng A.1 - Kết quả kiểm tra đo lường"),
        ox.table(_appendix_table_rows()),
        ox.para("Kết luận: Đạt (không đạt) yêu cầu kỹ thuật đo lường."),
    ]
    return dev, blocks + appendix


def case_k12_phuluc_a_heading(number: str) -> tuple[dict, list[dict]]:
    """K12: đoạn "(Quy định)" trong Phụ lục A bị gán style heading."""
    dev = _base_dev(number)
    blocks = _front_matter(dev) + _section_1(dev) + _section_references(dev) + _section_terms(dev)
    blocks += (
        _section_3(dev) + _section_4(dev) + _section_5(dev) + _section_6(dev) + _section_7(dev)
    )
    appendix = [
        ox.heading("Phụ lục A", 1),
        ox.heading("(Quy định)", 2),  # heading giữa Phụ lục A và phần thân -> cắt mục (K12)
        ox.para("MẪU BIÊN BẢN KIỂM ĐỊNH"),
    ]
    for label in appendix_labels(dev):
        if label == "Kết luận":
            continue
        appendix.append(ox.para(f"{label}:"))
    appendix += [
        ox.para("Bảng A.1 - Kết quả kiểm tra đo lường"),
        ox.table(_appendix_table_rows()),
        ox.para("Kết luận: Đạt (không đạt) yêu cầu kỹ thuật đo lường."),
    ]
    return dev, blocks + appendix


# Bảng gộp ô Phụ lục A dùng chung cho ca K07 (B3) và biên bản K07 (D13).
K07_TABLE_COLUMNS = ["Lần kiểm tra", "Áp suất", "Sai số", "Ghi chú"]
K07_TABLE_TITLE = "Bảng A.1 - Xác định sai số và độ chênh áp"


def k07_appendix_rows(
    n_rows: int = 3, fill: list[list[str]] | None = None
) -> list[list[ox.CellLike]]:
    """Tái tạo ĐÚNG cấu trúc thô gặp trong corpus thật (QTKĐ 1.061 Phụ lục A):

    hàng tiêu đề trên có 4 ô vật lý với "Áp suất" ``gridSpan=3`` (đúng XML thật),
    hàng tiêu đề dưới có 6 ô. Nhờ vậy lưới 6 cột khớp nhau và hai tầng ghép đúng
    cột: "Mở" / "Đóng" / "Độ chênh áp" (K07). Nếu bỏ gridSpan, "Sai số" và
    "Ghi chú" bị dồn về trái làm lệch vai trò cột.
    """
    header = [
        ox.Cell("Lần kiểm tra"),
        ox.Cell("Áp suất", span=3),
        ox.Cell("Sai số"),
        ox.Cell("Ghi chú"),
    ]
    sub = [
        ox.Cell(""),
        ox.Cell("Mở"),
        ox.Cell("Đóng"),
        ox.Cell("Độ chênh áp"),
        ox.Cell(""),
        ox.Cell(""),
    ]
    rows = [header, sub]
    for i in range(1, n_rows + 1):
        if fill and i <= len(fill):
            mo, dong, chenh = fill[i - 1]
        else:
            mo, dong, chenh = "", "", ""
        rows.append(
            [ox.Cell(str(i)), ox.Cell(mo), ox.Cell(dong), ox.Cell(chenh), ox.Cell(""), ox.Cell("")]
        )
    return rows


def case_k07_bang_gop_o(number: str) -> tuple[dict, list[dict]]:
    """Bảng gộp ô hai tầng (Mở/Đóng/Độ chênh áp) ở Phụ lục A -- đúng mẫu ĐLVN thật.

    Thân QTKĐ vẫn sạch (khớp luật đúng); ca biên nằm ở việc BIÊN BẢN nhóm D
    tương ứng (D13) đọc bảng này ra sai vai trò cột (K07).
    """
    dev = _base_dev(number)
    blocks = _front_matter(dev) + _section_1(dev) + _section_references(dev) + _section_terms(dev)
    blocks += (
        _section_3(dev) + _section_4(dev) + _section_5(dev) + _section_6(dev) + _section_7(dev)
    )
    appendix = [
        ox.heading("Phụ lục A", 1),
        ox.para("(Quy định)"),
        ox.para("MẪU BIÊN BẢN KIỂM ĐỊNH"),
    ]
    for label in appendix_labels(dev):
        if label == "Kết luận":
            continue
        appendix.append(ox.para(f"{label}:"))
    appendix += [
        ox.para(K07_TABLE_TITLE),
        ox.table(k07_appendix_rows()),
        ox.para("Kết luận: Đạt (không đạt) yêu cầu kỹ thuật đo lường."),
    ]
    return dev, blocks + appendix


def case_k10_chu_ky_khong_la(number: str) -> tuple[dict, list[dict]]:
    """K10: "Chu kỳ kiểm định: 6 tháng" -- không có chữ "là"."""
    dev = _base_dev(number)
    dev["interval_months"] = 6
    blocks = _front_matter(dev) + _section_1(dev) + _section_references(dev) + _section_terms(dev)
    blocks += _section_3(dev) + _section_4(dev) + _section_5(dev) + _section_6(dev)
    blocks += [
        _h(dev, [8], "Xử lý chung", 1),
        ox.para("Nếu đạt yêu cầu kỹ thuật thì cấp Giấy chứng nhận kiểm định và dán Tem kiểm định."),
        ox.para("Chu kỳ kiểm định: 6 tháng."),  # thiếu "là" (K10)
    ]
    blocks += _appendix(dev)
    return dev, blocks


def case_k02_dieu_kien_phay(number: str) -> tuple[dict, list[dict]]:
    """K02: "(20,5 ± 2) °C" -- dấu phẩy thập phân bị hiểu nhầm là dấu tách."""
    dev = _base_dev(number)
    dev["env"] = [
        ("Nhiệt độ môi trường", "(20,5 ± 2) °C"),
        ("Độ ẩm tương đối", "(65 ± 20) %"),
        ("Áp suất khí quyển", "(100 ± 4) kPa"),
    ]
    blocks = _front_matter(dev) + _section_1(dev) + _section_references(dev) + _section_terms(dev)
    blocks += (
        _section_3(dev) + _section_4(dev) + _section_5(dev) + _section_6(dev) + _section_7(dev)
    )
    blocks += _appendix(dev)
    return dev, blocks


def case_k13_heading_ban_dia_hoa(number: str) -> tuple[dict, list[dict]]:
    """K13: hai heading bản địa hoá (``TieuDeMuc1`` theo ``w:name``, ``MucCon2``
    theo ``basedOn``), không dùng style id ``headingN`` chuẩn."""
    dev = _base_dev(number)
    blocks = _front_matter(dev) + _section_1(dev) + _section_references(dev) + _section_terms(dev)
    blocks += _section_3(dev) + _section_4(dev) + _section_5(dev)
    section6 = _section_6(dev)
    section6[0] = ox.heading(section6[0]["text"], 1, style="TieuDeMuc1")  # qua w:name
    section6[2] = ox.heading(section6[2]["text"], 1, style="MucCon2")  # qua basedOn
    blocks += section6 + _section_7(dev) + _appendix(dev)
    return dev, blocks


def case_bang2_ket_thuc(number: str) -> tuple[dict, list[dict]]:
    """Bảng 2 tách làm hai bảng bằng "(kết thúc)" -- kiểm tra gộp đúng (không phải lỗi)."""
    dev = _base_dev(number)
    rows_all = _bang2_rows(dev)
    header_rows, data_rows = rows_all[:2], rows_all[2:]
    half = max(1, len(data_rows) // 2)
    blocks = _front_matter(dev) + _section_1(dev) + _section_references(dev) + _section_terms(dev)
    blocks += _section_3(dev)
    blocks += [
        _h(dev, [5], "Phương tiện kiểm định", 1),
        ox.para("Khi tiến hành kiểm định phải sử dụng các phương tiện được quy định trong Bảng 2."),
        ox.para("Bảng 2 - Danh mục phương tiện kiểm định"),
        ox.table(header_rows + data_rows[:half]),
        ox.para("Bảng 2 (kết thúc)"),
        ox.table(header_rows + data_rows[half:]),
    ]
    blocks += _section_5(dev) + _section_6(dev) + _section_7(dev) + _appendix(dev)
    return dev, blocks


def case_so_viet(number: str) -> tuple[dict, list[dict]]:
    """Số kiểu Việt hợp lệ: "0,500" (thập phân) và "1 000" (phân nhóm nghìn)."""
    dev = _base_dev(number)
    dev["range"] = {
        "pattern": "paren",
        "value_text": "(0,500 đến 1 000) mm",
        "prefix": f"Phạm vi đo của {dev['short'].lower()} kiểm định theo quy trình này là ",
    }
    blocks = _front_matter(dev) + _section_1(dev) + _section_references(dev) + _section_terms(dev)
    blocks += (
        _section_3(dev) + _section_4(dev) + _section_5(dev) + _section_6(dev) + _section_7(dev)
    )
    blocks += _appendix(dev)
    return dev, blocks


def case_k15_pham_vi_cham(number: str) -> tuple[dict, list[dict]]:
    """K15: câu phạm vi kết thúc ngay sau đơn vị bằng dấu chấm câu ("...bar.").

    Văn phong này hoàn toàn hợp lệ trong QTKĐ thật (không có mệnh đề bắt buộc
    phải theo sau đơn vị) -- khác ca ``qtkd_doc._section_1`` mặc định của nhóm
    A (luôn thêm mệnh đề + dấu phẩy để né lỗi). Ở đây cố ý giữ dạng "trần" để
    lộ ra lớp ký tự đơn vị của ``phamvi.py`` nuốt luôn dấu chấm câu.
    """
    dev = _base_dev(number)
    dev["range"] = {
        "pattern": "tu_den",
        "value_text": "từ 0 bar đến 1 400 bar",
        "prefix": "Phạm vi làm việc của van an toàn kiểm định theo quy trình này ",
    }
    section1 = [
        _h(dev, [1], "Phạm vi áp dụng", 1),
        ox.para(dev["range"]["prefix"] + dev["range"]["value_text"] + "."),
    ]
    blocks = _front_matter(dev) + section1 + _section_references(dev) + _section_terms(dev)
    blocks += (
        _section_3(dev) + _section_4(dev) + _section_5(dev) + _section_6(dev) + _section_7(dev)
    )
    blocks += _appendix(dev)
    return dev, blocks


CASES = [
    ("B01", "9.013", case_k11_qtkd_no_dau, "QTKD 9.013 2026 Van an toan ban khong dau.docx", "K11"),
    (
        "B02",
        "9.014",
        case_k12_phuluc_a_heading,
        "QTKĐ 9.014 2026 Van an toan bien phu luc.docx",
        "K12",
    ),
    (
        "B03",
        "9.015",
        case_k07_bang_gop_o,
        "QTKĐ 9.015 2026 Van an toan bang gop o.docx",
        "K07-setup",
    ),
    (
        "B04",
        "9.016",
        case_k10_chu_ky_khong_la,
        "QTKĐ 9.016 2026 Van an toan bien chu ky.docx",
        "K10",
    ),
    (
        "B05",
        "9.017",
        case_k02_dieu_kien_phay,
        "QTKĐ 9.017 2026 Van an toan bien dieu kien.docx",
        "K02",
    ),
    (
        "B06",
        "9.018",
        case_k13_heading_ban_dia_hoa,
        "QTKĐ 9.018 2026 Van an toan bien heading.docx",
        "K13",
    ),
    ("B07", "9.019", case_bang2_ket_thuc, "QTKĐ 9.019 2026 Van an toan bang2 ket thuc.docx", None),
    ("B08", "9.020", case_so_viet, "QTKĐ 9.020 2026 Van an toan so viet.docx", None),
    ("B09", "9.021", case_k15_pham_vi_cham, "QTKĐ 9.021 2026 Van an toan pham vi cham.docx", "K15"),
]
