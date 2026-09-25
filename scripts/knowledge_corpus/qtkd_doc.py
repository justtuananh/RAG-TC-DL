"""Lắp khối nội dung một QTKĐ (nhóm A) từ dữ liệu thiết bị (``devices_a.py``).

Redo R1..R5: mỗi câu/dòng văn bản chỉ GHÉP các chuỗi ``value_text`` đã có sẵn
trong spec (không format lại số), nên gold (``gold_a.py``) suy từ ĐÚNG những
chuỗi này mà không cần chạy ``knowledge.rules``. Mọi hàm ở đây thuần: nhận
``dict`` thiết bị, trả danh sách khối OOXML -- không I/O.
"""

from __future__ import annotations

from scripts.knowledge_corpus import ooxml as ox

# Nhãn trường đầu mục Phụ lục A dùng chung cho mọi QTKĐ nhóm A (mẫu ĐLVN thật).
APPENDIX_BASE_LABELS = [
    "Tên phương tiện đo",
    "Ký hiệu",
    "Số hiệu",
    "Nơi (hãng) sản xuất",
    "Đơn vị sử dụng",
    "Nhiệt độ",
    "Độ ẩm",
    "Chế độ kiểm định",
    "Phương pháp kiểm định",
    "Ngày kiểm định",
    "Người kiểm định",
    "Người soát lại",
    "Kết luận",
]

APPENDIX_TABLE_TITLE = "Bảng A.1 - Kết quả kiểm tra đo lường"
APPENDIX_TABLE_COLUMNS = [
    "Lần đo",
    "Giá trị danh nghĩa",
    "Giá trị đo",
    "Sai số",
    "Giới hạn cho phép",
    "Ghi chú",
]

_MODE_LABELS = {"bd": "Ban đầu", "dk": "Định kỳ", "ssc": "Sau sửa chữa"}


def appendix_labels(dev: dict) -> list[str]:
    labels = list(APPENDIX_BASE_LABELS)
    insert_at = labels.index("Nơi (hãng) sản xuất") + 1
    for extra in dev.get("appendix_extra", []):
        labels.insert(insert_at, extra)
        insert_at += 1
    return labels


def _num(parts: list[int], style: str) -> str:
    text = ".".join(str(p) for p in parts)
    return {"space": f"{text} ", "dot": f"{text}. ", "paren": f"{text}) "}[style]


def _h(dev: dict, parts: list[int], title: str, level: int) -> dict:
    return ox.heading(_num(parts, dev["heading_style"]) + title, level)


def _front_matter(dev: dict) -> list[dict]:
    """Mô phỏng bìa QTKĐ thật (xem build/spike_a/QTKD_1.061_2021_ND_V2.md)."""
    return [
        ox.para(f"QTKĐ {dev['number']} : 2026"),
        ox.para(dev["title"].upper()),
        ox.para("QUY TRÌNH KIỂM ĐỊNH"),
        ox.para(
            "(Ban hành kèm theo Quyết định số ..... ngày ..... tháng ..... năm 2026 "
            "của Cục trưởng Cục Tiêu chuẩn - Đo lường - Chất lượng)"
        ),
        ox.para("HÀ NỘI - 2026"),
        ox.para(dev["title"]),
        ox.para("Quy trình kiểm định"),
    ]


def _section_1(dev: dict) -> list[dict]:
    """Câu văn §1: PHẢI có dấu phẩy (không phải khoảng trắng) ngay sau đơn vị.

    Lớp ký tự đơn vị của ``phamvi.py`` (``[\\w%°/²³.]*``) coi dấu "." là một
    phần đơn vị hợp lệ (không có khoảng trắng ngăn cách); nếu câu kết thúc
    "... 1 400 bar." không có gì theo sau, quy trình sẽ nuốt luôn dấu chấm câu
    vào đơn vị ("bar.") và gold sẽ không khớp. Dấu phẩy chặn đúng ranh giới.
    """
    r = dev["range"]
    sentence = (
        r["prefix"] + r["value_text"] + ", áp dụng cho kiểm định ban đầu, định kỳ và sau sửa chữa."
    )
    return [_h(dev, [1], "Phạm vi áp dụng", 1), ox.para(sentence)]


def _section_references(dev: dict) -> list[dict]:
    blocks = [
        _h(dev, [2], "Tài liệu viện dẫn", 1),
        ox.para("Các tài liệu sau được viện dẫn để áp dụng trong quy trình này:"),
    ]
    for ref in dev["references"]:
        blocks.append(ox.para(f"- {ref};"))
    return blocks


def _section_terms(dev: dict) -> list[dict]:
    blocks = [
        _h(dev, [3], "Thuật ngữ và định nghĩa", 1),
        ox.para("Các thuật ngữ, định nghĩa trong quy trình này được hiểu như sau:"),
    ]
    for term in dev["terms"]:
        blocks.append(ox.para(f"{term['vi']} ({term['en']}): {term['definition']}"))
        if term.get("chu_thich"):
            blocks.append(ox.para(f"CHÚ THÍCH: {term['chu_thich']}"))
    return blocks


def _bang1_rows(dev: dict) -> list[list[ox.CellLike]]:
    header = [
        ox.Cell("TT"),
        ox.Cell("Tên phép kiểm định"),
        ox.Cell("Theo điều (mục) của QTKĐ"),
        ox.Cell("Chế độ kiểm định", span=3),
    ]
    sub = [
        ox.Cell(""),
        ox.Cell(""),
        ox.Cell(""),
        ox.Cell("Ban đầu"),
        ox.Cell("Định kỳ"),
        ox.Cell("Sau sửa chữa"),
    ]
    rows = [header, sub]
    for i, step in enumerate(dev["bang1"], start=1):
        marks = {mode: ("+" if mode in step["modes"] else "") for mode in ("bd", "dk", "ssc")}
        rows.append(
            [
                ox.Cell(str(i)),
                ox.Cell(step["label"]),
                ox.Cell(step["ref"]),
                ox.Cell(marks["bd"]),
                ox.Cell(marks["dk"]),
                ox.Cell(marks["ssc"]),
            ]
        )
    return rows


def _section_3(dev: dict) -> list[dict]:
    return [
        _h(dev, [4], "Các phép kiểm định", 1),
        ox.para("Thực hiện các phép kiểm định được quy định trong Bảng 1."),
        ox.para("Bảng 1 - Các phép kiểm định"),
        ox.table(_bang1_rows(dev)),
    ]


def _bang2_rows(dev: dict) -> list[list[ox.CellLike]]:
    header = [
        ox.Cell("TT"),
        ox.Cell("Tên phương tiện kiểm định"),
        ox.Cell("Đặc trưng kỹ thuật đo lường", span=2),
    ]
    sub = [
        ox.Cell(""),
        ox.Cell(""),
        ox.Cell("Phạm vi đo"),
        ox.Cell("Cấp chính xác hoặc độ chính xác hoặc sai số hoặc độ không đảm bảo đo"),
    ]
    rows = [header, sub]
    for i, std in enumerate(dev["bang2"], start=1):
        rows.append(
            [ox.Cell(str(i)), ox.Cell(std["name"]), ox.Cell(std["range"]), ox.Cell(std["accuracy"])]
        )
    return rows


def _section_4(dev: dict) -> list[dict]:
    return [
        _h(dev, [5], "Phương tiện kiểm định", 1),
        ox.para("Khi tiến hành kiểm định phải sử dụng các phương tiện được quy định trong Bảng 2."),
        ox.para("Bảng 2 - Danh mục phương tiện kiểm định"),
        ox.table(_bang2_rows(dev)),
    ]


def _section_5(dev: dict) -> list[dict]:
    blocks = [
        _h(dev, [6], "Điều kiện và chuẩn bị kiểm định", 1),
        _h(dev, [6, 1], "Điều kiện kiểm định", 2),
        ox.para("Phải tiến hành kiểm định trong các điều kiện sau:"),
    ]
    for label, value in dev["env"]:
        blocks.append(ox.para(f"- {label}: {value};"))
    blocks += [
        _h(dev, [6, 2], "Chuẩn bị kiểm định", 2),
        ox.para(
            "Trước khi tiến hành kiểm định phải để phương tiện đo và chuẩn đo "
            "lường trong phòng thí nghiệm đến khi đạt điều kiện quy định tại "
            "điều 6.1, sau đó lắp đặt theo sơ đồ kết nối chuẩn."
        ),
    ]
    return blocks


def _section_6(dev: dict) -> list[dict]:
    blocks = [
        _h(dev, [7], "Tiến hành kiểm định", 1),
        ox.para(
            "Trong quá trình kiểm định, nếu một nội dung kiểm tra không đạt "
            "yêu cầu thì kết luận không đạt và không tiến hành các bước tiếp theo."
        ),
        _h(dev, [7, 1], "Kiểm tra bên ngoài", 2),
        ox.para(
            f"Kiểm tra bên ngoài {dev['short'].lower()} theo yêu cầu về tình trạng nguyên vẹn, nhãn mác."
        ),
        _h(dev, [7, 2], "Kiểm tra kỹ thuật", 2),
        ox.para(f"Kiểm tra khả năng làm việc bình thường của {dev['short'].lower()}."),
        _h(dev, [7, 3], "Kiểm tra đo lường", 2),
        ox.para(f"{dev['short']} được kiểm tra đo lường theo trình tự và yêu cầu sau:"),
    ]
    for fact in dev["section6"]:
        blocks.append(ox.para(fact["sentence"]))
    return blocks


def _section_7(dev: dict) -> list[dict]:
    return [
        _h(dev, [8], "Xử lý chung", 1),
        ox.para(
            f"Nếu sau khi kiểm định {dev['short'].lower()} đạt các yêu cầu kỹ "
            "thuật trong phần Tiến hành kiểm định thì cấp Giấy chứng nhận kiểm "
            "định và dán Tem kiểm định."
        ),
        ox.para(f"Chu kỳ kiểm định của {dev['short'].lower()} là {dev['interval_months']} tháng."),
        ox.para(
            f"Nếu {dev['short'].lower()} không đạt một trong các yêu cầu kỹ "
            "thuật thì cấp Biên bản kiểm định và xóa bỏ Tem kiểm định cũ (nếu có)."
        ),
    ]


def _appendix(dev: dict) -> list[dict]:
    blocks = [
        ox.heading("Phụ lục A", 1),
        ox.para("(Quy định)"),
        ox.para("MẪU BIÊN BẢN KIỂM ĐỊNH"),
        ox.para(f"BIÊN BẢN KIỂM ĐỊNH {dev['title'].upper()}"),
    ]
    for label in appendix_labels(dev):
        if label == "Kết luận":
            continue  # ghi một lần duy nhất, kèm giá trị, ở cuối Phụ lục A.
        if label == "Tên phương tiện đo":
            blocks.append(ox.para(f"{label}: {dev['short']}"))
        elif label == "Phương pháp kiểm định":
            blocks.append(ox.para(f"{label}: QTKĐ {dev['number']} : 2026"))
        else:
            blocks.append(ox.para(f"{label}:"))
    blocks += [
        ox.para(APPENDIX_TABLE_TITLE),
        ox.table(_appendix_table_rows()),
        ox.para("Kết luận: Đạt (không đạt) yêu cầu kỹ thuật đo lường."),
    ]
    return blocks


def _appendix_table_rows() -> list[list[ox.CellLike]]:
    header = [ox.Cell(c) for c in APPENDIX_TABLE_COLUMNS]
    blanks = [""] * len(APPENDIX_TABLE_COLUMNS)
    rows = [header]
    for i in range(1, 4):
        row = list(blanks)
        row[0] = str(i)
        rows.append([ox.Cell(c) for c in row])
    return rows


def build_qtkd_blocks(dev: dict) -> list[dict]:
    """Toàn bộ khối nội dung một QTKĐ nhóm A (đủ mục theo mẫu ĐLVN)."""
    blocks: list[dict] = []
    blocks += _front_matter(dev)
    blocks += _section_1(dev)
    blocks += _section_references(dev)
    blocks += _section_terms(dev)
    blocks += _section_3(dev)
    blocks += _section_4(dev)
    blocks += _section_5(dev)
    blocks += _section_6(dev)
    blocks += _section_7(dev)
    blocks += _appendix(dev)
    return blocks
