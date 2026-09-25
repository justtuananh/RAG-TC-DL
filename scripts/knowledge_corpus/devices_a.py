"""Dữ liệu 12 phương tiện đo cho nhóm A (spec Pha 2, mục 7 nghiên cứu mẫu).

QUAN TRỌNG (redo R1): mọi trường ``value_text``/``gold_*`` dưới đây là NGUỒN DUY
NHẤT của cả nội dung tài liệu (``qtkd_doc.py``) lẫn gold (``gold_a.py``) -- gold
KHÔNG được suy từ việc chạy ``knowledge.rules``. ``qtkd_doc.py`` chỉ ghép các
chuỗi này vào câu văn (tiền tố + chuỗi + hậu tố), không format lại số liệu, nên
chuỗi trích xuất mong đợi (gold) và chuỗi có trong tài liệu LUÔN khớp nhau vì
cùng một chuỗi. Số hiệu QTKĐ 9.001..9.012 và mọi số liệu giữ đúng theo
``docs/superpowers/research/2026-09-25-mau-tai-lieu-do-luong.md`` mục 7.

R4 (đa dạng hoá nhóm A): mỗi thiết bị có kiểu diễn đạt phạm vi riêng
(``range.pattern`` in {tu_den, paren, den_only}), một trong bốn "hồ sơ" điều
kiện môi trường (``ENV_PROFILES``), kiểu đánh số mục riêng
(``heading_style`` in {space, dot, paren}), 2-4 thuật ngữ (một số kèm CHÚ
THÍCH), 3-6 bước Bảng 1 (một số ô để trống thay vì "+"), và 3-5 chuẩn Bảng 2
với phạm vi đo THẬT (không lẫn với cột sai số -- sửa R3).
"""

from __future__ import annotations

# ── Bốn "hồ sơ" điều kiện môi trường luân phiên (R4: đa dạng cách diễn đạt) ────
ENV_PROFILES = [
    [
        ("Nhiệt độ môi trường", "(20 ± 5) °C"),
        ("Độ ẩm tương đối", "(65 ± 20) %"),
        ("Áp suất khí quyển", "(100 ± 4) kPa"),
    ],
    [
        ("Nhiệt độ môi trường", "(25 ± 3) oC"),
        ("Độ ẩm tương đối", "không lớn hơn 80 %RH"),
        ("Áp suất khí quyển", "≤ 106 kPa"),
    ],
    [
        ("Nhiệt độ môi trường", "không lớn hơn 30 °C"),
        ("Độ ẩm tương đối", "(60 ± 15) %RH"),
        ("Áp suất khí quyển", "(101 ± 3) kPa"),
    ],
    [
        ("Nhiệt độ môi trường", "≤ 35 oC"),
        ("Độ ẩm tương đối", "≤ 85 %"),
        ("Áp suất khí quyển", "không lớn hơn 106 kPa"),
    ],
]

# Tiền tố câu văn cho từng kiểu diễn đạt phạm vi (ghép với range["value_text"]).
_RANGE_PREFIX = {
    "tu_den": "Phạm vi đo của {short_lower} kiểm định theo quy trình này ",
    "paren": "Phạm vi đo của {short_lower} kiểm định theo quy trình này là ",
    "den_only": "Phạm vi đo của {short_lower} kiểm định theo quy trình này ",
}

_STD_BD_DK_SSC = ("bd", "dk", "ssc")
_STD_BD_SSC = ("bd", "ssc")


def _terms(*items: tuple[str, str, str, str | None]) -> list[dict]:
    return [{"vi": vi, "en": en, "definition": d, "chu_thich": ct} for vi, en, d, ct in items]


def _step(label: str, ref: str, modes: tuple[str, ...] = _STD_BD_DK_SSC) -> dict:
    return {"label": label, "ref": ref, "modes": modes}


def _std(name: str, range_text: str, accuracy: str) -> dict:
    return {"name": name, "range": range_text, "accuracy": accuracy}


DEVICES: list[dict] = [
    {
        "number": "9.001",
        "short": "Van an toàn",
        "heading_style": "space",
        "title": "Van an toàn có phạm vi làm việc đến 1 400 bar",
        "range": {"pattern": "den_only", "value_text": "đến 1 400 bar"},
        "references": [
            "QTKĐ 1.061 : 2021, Van an toàn - Quy trình kiểm định",
            "Thông tư 23/2013/TT-BKHCN, Danh mục phương tiện đo phải kiểm định",
        ],
        "terms": _terms(
            (
                "Van an toàn",
                "Safety valve",
                "là van tự động xả một phần môi chất để ngăn ngừa áp suất vượt quá giá trị đã chỉnh đặt trước.",
                None,
            ),
            (
                "Áp suất chỉnh đặt",
                "Set pressure",
                "là áp suất tại đó van an toàn bắt đầu mở trong điều kiện vận hành.",
                "Áp suất chỉnh đặt được xác định tại đường vào của van.",
            ),
            (
                "Độ chênh áp",
                "Blowdown",
                "là độ chênh lệch giữa áp suất chỉnh đặt và áp suất đóng của van.",
                None,
            ),
        ),
        "bang1": [
            _step("Kiểm tra bên ngoài", "7.1"),
            _step("Kiểm tra kỹ thuật", "7.2"),
            _step("Xác định sai số áp suất chỉnh đặt", "7.3.1"),
            _step("Xác định độ chênh áp", "7.3.2", _STD_BD_SSC),
        ],
        "bang2": [
            _std("Áp kế hiện số chuẩn", "(0 ÷ 1 500) bar", "≤ 1/4 sai số cho phép của van"),
            _std(
                "Thiết bị tạo áp suất",
                "(0 ÷ 1 500) bar",
                "ổn định, trôi không quá 5 % trong 5 phút",
            ),
            _std("Ẩm kế", "(0 ÷ 100) %RH", "± 5 %RH"),
            _std("Barômét", "(800 ÷ 1 100) mbar", "± 2 mbar"),
            _std("Thước đo", "(0 ÷ 500) mm", "± 1 mm"),
        ],
        "env": ENV_PROFILES[0],
        "interval_months": 12,
        "section6": [
            {
                "label": "Sai số áp suất chỉnh đặt",
                "sentence": "Sai số cho phép của áp suất chỉnh đặt bằng ± 3 % áp suất chỉnh đặt nhưng không nhỏ hơn ± 0,15 bar.",
                "rel_op": "±",
                "value_text": "3 %",
                "condition_text": "không nhỏ hơn ± 0,15 bar",
                "limit": {"value": 3.0, "unit": "%", "quote": "± 3 % áp suất chỉnh đặt"},
                "floor": {"value": 0.15, "unit": "bar", "quote": "không nhỏ hơn ± 0,15 bar"},
            },
        ],
        "appendix_extra": ["Cỡ van", "Áp suất chỉnh đặt"],
    },
    {
        "number": "9.002",
        "short": "Áp kế kiểu lò xo",
        "heading_style": "dot",
        "title": "Áp kế kiểu lò xo có phạm vi đo đến 250 MPa",
        "range": {"pattern": "tu_den", "value_text": "từ -0,1 MPa đến 250 MPa"},
        "references": [
            "ĐLVN 08 : 2011, Áp kế kiểu lò xo - Quy trình kiểm định",
            "Thông tư 23/2013/TT-BKHCN, Danh mục phương tiện đo phải kiểm định",
        ],
        "terms": _terms(
            (
                "Áp kế kiểu lò xo",
                "Spring pressure gauge",
                "là áp kế đo áp suất dựa trên biến dạng đàn hồi của ống lò xo (ống Bourdon).",
                None,
            ),
            (
                "Cấp chính xác",
                "Accuracy class",
                "là chỉ số thể hiện sai số cho phép lớn nhất của áp kế theo phần trăm khoảng đo.",
                None,
            ),
        ),
        "bang1": [
            _step("Kiểm tra bên ngoài", "7.1"),
            _step("Kiểm tra kỹ thuật", "7.2"),
            _step("Kiểm tra đo lường", "7.3"),
        ],
        "bang2": [
            _std("Áp kế píttông chuẩn", "(-0,1 ÷ 250) MPa", "cấp 0,05"),
            _std("Buồng điều nhiệt", "(15 ÷ 35) °C", "± 0,5 °C"),
            _std("Ẩm kế", "(0 ÷ 100) %RH", "± 5 %RH"),
            _std("Barômét", "(800 ÷ 1 100) mbar", "± 2 mbar"),
        ],
        "env": ENV_PROFILES[1],
        "interval_months": 12,
        "section6": [
            {
                "label": "Sai số cơ bản",
                "sentence": "Sai số cho phép tại mỗi điểm kiểm tra bằng ± 1,6 % giá trị khoảng đo nhưng không nhỏ hơn ± 0,05 MPa.",
                "rel_op": "±",
                "value_text": "1,6 %",
                "condition_text": "không nhỏ hơn ± 0,05 MPa",
                "limit": {"value": 1.6, "unit": "%", "quote": "± 1,6 % giá trị khoảng đo"},
                "floor": {"value": 0.05, "unit": "MPa", "quote": "không nhỏ hơn ± 0,05 MPa"},
            },
        ],
        "appendix_extra": ["Cấp chính xác"],
    },
    {
        "number": "9.003",
        "short": "Huyết áp kế",
        "heading_style": "paren",
        "title": "Huyết áp kế thủy ngân và lò xo",
        "range": {"pattern": "paren", "value_text": "(0 đến 40) kPa"},
        "references": [
            "ĐLVN 09 : 2011, Huyết áp kế - Quy trình kiểm định",
            "Thông tư 23/2013/TT-BKHCN, mục 34-35",
        ],
        "terms": _terms(
            (
                "Huyết áp kế",
                "Sphygmomanometer",
                "là phương tiện đo dùng để xác định áp suất máu động mạch của con người.",
                None,
            ),
            (
                "Huyết áp tâm thu",
                "Systolic pressure",
                "là áp suất máu động mạch cao nhất trong một chu kỳ tim đập.",
                "Huyết áp tâm thu còn gọi là huyết áp tối đa.",
            ),
        ),
        "bang1": [
            _step("Kiểm tra bên ngoài", "7.1"),
            _step("Kiểm tra kỹ thuật", "7.2"),
            _step("Kiểm tra đo lường", "7.3"),
        ],
        "bang2": [
            _std("Áp kế píttông", "(0 ÷ 40) kPa", "≤ 0,1 kPa"),
            _std("Áp kế chất lỏng", "(0 ÷ 40) kPa", "≤ 0,1 kPa"),
            _std("Nhiệt kế", "(15 ÷ 35) °C", "± 0,5 °C"),
        ],
        "env": ENV_PROFILES[2],
        "interval_months": 12,
        "section6": [
            {
                "label": "Sai số cho phép toàn thang đo",
                "sentence": "Sai số cho phép tại mọi điểm kiểm tra là ± 0,4 kPa.",
                "rel_op": "=",
                "value_text": "0,4 kPa",
                "limit": {"value": 0.4, "unit": "kPa", "quote": "là ± 0,4 kPa"},
            },
        ],
        "appendix_extra": [],
    },
    {
        "number": "9.004",
        "short": "Đồng hồ nước lạnh",
        "heading_style": "space",
        "title": "Đồng hồ nước lạnh cơ khí DN15 đến DN50",
        "range": {"pattern": "tu_den", "value_text": "từ 2,5 m3/h đến 16 m3/h"},
        "references": [
            "ĐLVN 17 : 2017, Đồng hồ đo nước - Quy trình kiểm định",
            "Thông tư 23/2013/TT-BKHCN, mục 20-21",
        ],
        "terms": _terms(
            (
                "Lưu lượng danh định",
                "Permanent flow rate Q3",
                "là giá trị lưu lượng cao nhất mà đồng hồ hoạt động ổn định trong điều kiện bình thường.",
                None,
            ),
            (
                "Lưu lượng tối thiểu",
                "Minimum flow rate Q1",
                "là giá trị lưu lượng nhỏ nhất tại đó đồng hồ vẫn chỉ thị đúng sai số cho phép.",
                "Q1 xác định vùng lưu lượng thấp cùng với Q2.",
            ),
        ),
        "bang1": [
            _step("Kiểm tra bên ngoài", "7.1"),
            _step("Kiểm tra kỹ thuật", "7.2"),
            _step("Xác định sai số tại lưu lượng thấp", "7.3.1"),
            _step("Xác định sai số tại lưu lượng cao", "7.3.2", _STD_BD_SSC),
        ],
        "bang2": [
            _std("Bể chuẩn thể tích", "(0 ÷ 200) L", "± 1/3 sai số cho phép"),
            _std("Đồng hồ bấm giây", "(0 ÷ 3 600) s", "± 0,2 s"),
            _std("Nhiệt kế", "(0 ÷ 50) °C", "± 0,5 °C"),
        ],
        "env": ENV_PROFILES[3],
        "interval_months": 60,
        "section6": [
            {
                "label": "Sai số ở vùng lưu lượng thấp",
                "sentence": "Sai số cho phép ở vùng lưu lượng thấp (từ Q1 đến Q2) bằng ± 5 % giá trị đo nhưng không nhỏ hơn 0,02 m3 cho một lần thử thể tích.",
                "rel_op": "±",
                "value_text": "5 %",
                "condition_text": "không nhỏ hơn 0,02 m3",
                "limit": {"value": 5.0, "unit": "%", "quote": "± 5 % giá trị đo"},
                "floor": {"value": 0.02, "unit": "m3", "quote": "không nhỏ hơn 0,02 m3"},
            },
            {
                "label": "Sai số ở vùng lưu lượng cao",
                "sentence": "Sai số cho phép ở vùng lưu lượng cao (từ Q2 đến Q4) là ± 2 % giá trị đo.",
                "rel_op": "=",
                "value_text": "2 %",
                "limit": {"value": 2.0, "unit": "%", "quote": "là ± 2 % giá trị đo"},
            },
        ],
        "appendix_extra": ["Cỡ đồng hồ DN"],
    },
    {
        "number": "9.005",
        "short": "Cân ô tô",
        "heading_style": "dot",
        "title": "Cân ô tô có mức cân lớn nhất đến 150 000 kg",
        "range": {"pattern": "paren", "value_text": "(0 đến 150 000) kg"},
        "references": [
            "ĐLVN 13 : 2019, Cân ô tô - Quy trình kiểm định",
            "Thông tư 23/2013/TT-BKHCN, mục 11",
        ],
        "terms": _terms(
            (
                "Mức cân lớn nhất",
                "Maximum capacity",
                "là khối lượng lớn nhất mà cân có thể cân được theo thiết kế.",
                None,
            ),
            (
                "Độ chia kiểm",
                "Verification scale interval",
                "là giá trị nhỏ nhất dùng để xác định sai số cho phép và phân cấp cân.",
                "Độ chia kiểm ký hiệu là e.",
            ),
            (
                "Cấp chính xác",
                "Accuracy class",
                "là chỉ số biểu thị mức sai số cho phép của cân theo tải trọng.",
                None,
            ),
        ),
        "bang1": [
            _step("Kiểm tra bên ngoài", "7.1"),
            _step("Kiểm tra kỹ thuật", "7.2"),
            _step("Xác định sai số ở các mức tải", "7.3.1"),
            _step("Kiểm tra độ lặp lại", "7.3.2", _STD_BD_SSC),
        ],
        "bang2": [
            _std("Quả cân chuẩn hạng M1", "(0 ÷ 150 000) kg", "cấp M1"),
            _std("Xe tải chuẩn", "(0 ÷ 150 000) kg", "± 0,05 % khối lượng"),
            _std("Nhiệt kế", "(0 ÷ 50) °C", "± 0,5 °C"),
        ],
        "env": ENV_PROFILES[0],
        "interval_months": 12,
        "section6": [
            {
                "label": "Sai số ở các mức tải",
                "sentence": "Sai số cho phép ở mỗi mức tải bằng ± 0,1 % tải trọng cân nhưng không nhỏ hơn ± 20 kg.",
                "rel_op": "±",
                "value_text": "0,1 %",
                "condition_text": "không nhỏ hơn ± 20 kg",
                "limit": {"value": 0.1, "unit": "%", "quote": "± 0,1 % tải trọng cân"},
                "floor": {"value": 20.0, "unit": "kg", "quote": "không nhỏ hơn ± 20 kg"},
            },
        ],
        "appendix_extra": ["Mức cân lớn nhất"],
    },
    {
        "number": "9.006",
        "short": "Công tơ điện",
        "heading_style": "paren",
        "title": "Công tơ điện xoay chiều 1 pha kiểu cảm ứng",
        "range": {"pattern": "tu_den", "value_text": "từ 5 A đến 60 A"},
        "references": [
            "ĐLVN 07 : 2012, Công tơ điện xoay chiều kiểu cảm ứng - Quy trình kiểm định",
            "Thông tư 23/2013/TT-BKHCN, mục 49-50",
        ],
        "terms": _terms(
            (
                "Công tơ điện cảm ứng",
                "Induction watt-hour meter",
                "là công tơ đo điện năng dựa trên nguyên lý cảm ứng điện từ giữa đĩa nhôm và cuộn dây.",
                None,
            ),
            (
                "Hằng số công tơ",
                "Meter constant",
                "là số vòng quay của đĩa nhôm ứng với một đơn vị điện năng đo được.",
                None,
            ),
        ),
        "bang1": [
            _step("Kiểm tra bên ngoài", "7.1"),
            _step("Kiểm tra kỹ thuật", "7.2"),
            _step("Xác định sai số cơ bản", "7.3.1"),
            _step("Kiểm tra hằng số công tơ", "7.3.2", _STD_BD_SSC),
        ],
        "bang2": [
            _std("Công tơ chuẩn", "(0 ÷ 100) A", "cấp 0,2"),
            _std("Nguồn dòng áp chuẩn", "(0 ÷ 250) V", "± 0,05 %"),
            _std("Đồng hồ bấm giây", "(0 ÷ 3 600) s", "± 0,2 s"),
        ],
        "env": ENV_PROFILES[1],
        "interval_months": 60,
        "section6": [
            {
                "label": "Sai số cơ bản tại dòng điện lớn",
                "sentence": "Sai số cho phép tại dòng điện từ 10 % Iđm đến Imax là ± 2,0 %.",
                "rel_op": "=",
                "value_text": "2,0 %",
                "limit": {"value": 2.0, "unit": "%", "quote": "là ± 2,0 %"},
            },
            {
                "label": "Sai số cơ bản tại dòng điện nhỏ",
                "sentence": "Sai số cho phép tại dòng điện bằng 5 % Iđm là ± 2,5 %.",
                "rel_op": "=",
                "value_text": "2,5 %",
                "limit": {"value": 2.5, "unit": "%", "quote": "là ± 2,5 %"},
            },
        ],
        "appendix_extra": ["Dòng điện danh định", "Điện áp danh định"],
    },
    {
        "number": "9.007",
        "short": "Taximet",
        "heading_style": "space",
        "title": "Taximet",
        "range": {"pattern": "paren", "value_text": "(10 đến 60) km/h"},
        "references": [
            "Taximet - chưa xác minh số hiệu/phiên bản ĐLVN chính xác (nhiều bản ĐLVN 01 lưu hành)",
            "Thông tư 23/2013/TT-BKHCN, mục 2",
        ],
        "terms": _terms(
            (
                "Taximet",
                "Taximeter",
                "là phương tiện đo tính và hiển thị tiền cước theo quãng đường và thời gian di chuyển của xe taxi.",
                None,
            ),
            (
                "Hệ số taximet",
                "Taximeter constant",
                "là số xung phát ra tương ứng với một đơn vị quãng đường xe đã đi.",
                "Hệ số taximet phụ thuộc cỡ lốp xe.",
            ),
        ),
        "bang1": [
            _step("Kiểm tra bên ngoài", "7.1"),
            _step("Kiểm tra kỹ thuật", "7.2"),
            _step("Xác định sai số quãng đường", "7.3.1"),
            _step("Xác định sai số cước phí", "7.3.2", _STD_BD_SSC),
        ],
        "bang2": [
            _std("Đường thử chuẩn", "(0 ÷ 5) km", "± 0,1 %"),
            _std("Tốc kế chuẩn", "(0 ÷ 200) km/h", "± 1 %"),
            _std("Đồng hồ bấm giây", "(0 ÷ 3 600) s", "± 0,2 s"),
        ],
        "env": ENV_PROFILES[2],
        "interval_months": 12,
        "section6": [
            {
                "label": "Sai số quãng đường thử",
                "sentence": "Sai số cho phép của quãng đường thử bằng ± 2 % quãng đường thử nhưng không nhỏ hơn ± 10 m trên một lần thử 1 km.",
                "rel_op": "±",
                "value_text": "2 %",
                "condition_text": "không nhỏ hơn ± 10 m",
                "limit": {"value": 2.0, "unit": "%", "quote": "± 2 % quãng đường thử"},
                "floor": {"value": 10.0, "unit": "m", "quote": "không nhỏ hơn ± 10 m"},
            },
        ],
        "appendix_extra": ["Biển số xe"],
    },
    {
        "number": "9.008",
        "short": "Máy đo tốc độ",
        "heading_style": "dot",
        "title": "Phương tiện đo tốc độ phương tiện giao thông kiểu laser, radar",
        "range": {"pattern": "den_only", "value_text": "đến 320 km/h"},
        "references": [
            "ĐLVN 157 : 2019, Phương tiện đo kiểm tra tốc độ phương tiện giao thông - Quy trình kiểm định",
            "Thông tư 23/2013/TT-BKHCN, mục 3",
        ],
        "terms": _terms(
            (
                "Phương tiện đo tốc độ",
                "Speed measuring device",
                "là phương tiện đo dùng sóng laser hoặc radar để xác định tốc độ di chuyển của phương tiện giao thông.",
                None,
            ),
            (
                "Hiệu ứng Doppler",
                "Doppler effect",
                "là hiện tượng thay đổi tần số sóng phản xạ dùng để tính tốc độ mục tiêu.",
                "Radar tốc độ hoạt động dựa trên hiệu ứng Doppler.",
            ),
        ),
        "bang1": [
            _step("Kiểm tra bên ngoài", "7.1"),
            _step("Kiểm tra kỹ thuật", "7.2"),
            _step("Kiểm tra sai số đo khoảng cách", "7.3.1"),
            _step("Kiểm tra sai số đo tốc độ", "7.3.2", _STD_BD_SSC),
        ],
        "bang2": [
            _std("Máy phát tốc độ chuẩn", "(0 ÷ 320) km/h", "± 0,5 km/h"),
            _std("Xe thử có định vị GPS chuẩn", "(0 ÷ 320) km/h", "± 0,3 km/h"),
            _std("Thước đo khoảng cách chuẩn", "(0 ÷ 1 000) m", "± 0,05 m"),
        ],
        "env": ENV_PROFILES[3],
        "interval_months": 12,
        "section6": [
            {
                "label": "Sai số đo tốc độ",
                "sentence": "Sai số cho phép của phép đo tốc độ bằng ± 1 % giá trị đo nhưng không nhỏ hơn ± 1 km/h.",
                "rel_op": "±",
                "value_text": "1 %",
                "condition_text": "không nhỏ hơn ± 1 km/h",
                "limit": {"value": 1.0, "unit": "%", "quote": "± 1 % giá trị đo"},
                "floor": {"value": 1.0, "unit": "km/h", "quote": "không nhỏ hơn ± 1 km/h"},
            },
            {
                "label": "Sai số đo khoảng cách",
                "sentence": "Sai số cho phép của phép đo khoảng cách không lớn hơn ± 0,15 m.",
                "rel_op": "<=",
                "value_text": "0,15 m",
                "limit": {"value": 0.15, "unit": "m", "quote": "không lớn hơn ± 0,15 m"},
            },
        ],
        "appendix_extra": ["Địa điểm thử"],
    },
    {
        "number": "9.009",
        "short": "Máy đo nồng độ cồn",
        "heading_style": "paren",
        "title": "Phương tiện đo hàm lượng cồn trong hơi thở",
        "range": {"pattern": "tu_den", "value_text": "từ 0,000 mg/L đến 3,000 mg/L"},
        "references": [
            "ĐLVN 107 : 2012, Phương tiện đo hàm lượng cồn trong hơi thở - Quy trình kiểm định",
            "Thông tư 23/2013/TT-BKHCN, mục 45",
        ],
        "terms": _terms(
            (
                "Phương tiện đo hàm lượng cồn",
                "Breath alcohol analyzer",
                "là phương tiện đo xác định nồng độ cồn ethanol trong hơi thở của người được kiểm tra.",
                None,
            ),
            (
                "Khí chuẩn ethanol",
                "Ethanol reference gas",
                "là hỗn hợp khí đã biết trước nồng độ ethanol dùng làm chuẩn khi kiểm định.",
                "Khí chuẩn ethanol phải còn hiệu lực hiệu chuẩn.",
            ),
        ),
        "bang1": [
            _step("Kiểm tra bên ngoài", "7.1"),
            _step("Kiểm tra kỹ thuật", "7.2"),
            _step("Kiểm tra khí không", "7.3.1"),
            _step("Xác định sai số tại các mức nồng độ chuẩn", "7.3.2", _STD_BD_SSC),
        ],
        "bang2": [
            _std("Khí chuẩn ethanol", "(0,000 ÷ 3,000) mg/L", "± 2 %"),
            _std("Hệ thống chuẩn khí ướt", "(30 ÷ 40) °C", "± 1 °C"),
            _std("Ẩm kế", "(0 ÷ 100) %RH", "± 5 %RH"),
        ],
        "env": ENV_PROFILES[0],
        "interval_months": 12,
        "section6": [
            {
                "label": "Sai số tại vùng nồng độ thấp",
                "sentence": "Sai số cho phép bằng ± 5 % giá trị đo nhưng không nhỏ hơn ± 0,020 mg/L ở vùng nồng độ thấp.",
                "rel_op": "±",
                "value_text": "5 %",
                "condition_text": "không nhỏ hơn ± 0,020 mg/L",
                "limit": {"value": 5.0, "unit": "%", "quote": "± 5 % giá trị đo"},
                "floor": {"value": 0.020, "unit": "mg/L", "quote": "không nhỏ hơn ± 0,020 mg/L"},
            },
        ],
        "appendix_extra": ["Số seri đầu đo"],
    },
    {
        "number": "9.010",
        "short": "Nhiệt kế y học",
        "heading_style": "space",
        "title": "Nhiệt kế y học điện tử tiếp xúc có cơ cấu cực đại",
        "range": {"pattern": "paren", "value_text": "(35,0 đến 42,0) °C"},
        "references": [
            "Nhiệt kế y học điện tử tiếp xúc - chưa xác minh số hiệu ĐLVN",
            "Thông tư 23/2013/TT-BKHCN, mục 40",
        ],
        "terms": _terms(
            (
                "Nhiệt kế y học điện tử",
                "Electronic clinical thermometer",
                "là phương tiện đo thân nhiệt cơ thể người bằng cảm biến điện tử.",
                None,
            ),
            (
                "Cơ cấu cực đại",
                "Maximum device",
                "là bộ phận giữ lại giá trị nhiệt độ cao nhất đo được trong một lần đo.",
                "Cơ cấu cực đại giúp đọc kết quả sau khi rút nhiệt kế ra khỏi cơ thể.",
            ),
        ),
        "bang1": [
            _step("Kiểm tra bên ngoài", "7.1"),
            _step("Kiểm tra kỹ thuật", "7.2"),
            _step("Xác định sai số tại các điểm nhiệt độ chuẩn", "7.3"),
        ],
        "bang2": [
            _std("Bể điều nhiệt chuẩn", "(30 ÷ 45) °C", "± 0,02 °C"),
            _std("Nhiệt kế chuẩn platinum", "(0 ÷ 100) °C", "± 0,02 °C"),
            _std("Đồng hồ bấm giây", "(0 ÷ 3 600) s", "± 0,2 s"),
        ],
        "env": ENV_PROFILES[1],
        "interval_months": 6,
        "section6": [
            {
                "label": "Sai số trong vùng thang đo chính",
                "sentence": "Sai số cho phép trong khoảng (35,5 đến 42,0) °C là ± 0,1 °C.",
                "rel_op": "=",
                "value_text": "0,1 °C",
                "limit": {"value": 0.1, "unit": "°C", "quote": "là ± 0,1 °C"},
            },
            {
                "label": "Sai số ngoài vùng thang đo chính",
                "sentence": "Sai số cho phép ngoài khoảng (35,5 đến 42,0) °C là ± 0,2 °C.",
                "rel_op": "=",
                "value_text": "0,2 °C",
                "limit": {"value": 0.2, "unit": "°C", "quote": "là ± 0,2 °C"},
            },
        ],
        "appendix_extra": [],
    },
    {
        "number": "9.011",
        "short": "Đồng hồ xăng dầu",
        "heading_style": "dot",
        "title": "Đồng hồ xăng dầu (cột đo nhiên liệu)",
        "range": {"pattern": "den_only", "value_text": "đến 120 L/min"},
        "references": [
            "Đồng hồ xăng dầu (cột đo nhiên liệu) - chưa xác minh số hiệu ĐLVN",
            "Thông tư 23/2013/TT-BKHCN, mục 23",
        ],
        "terms": _terms(
            (
                "Đồng hồ xăng dầu",
                "Fuel dispenser meter",
                "là phương tiện đo thể tích xăng dầu bán ra tại cột đo nhiên liệu.",
                None,
            ),
            (
                "Thể tích thử tiêu chuẩn",
                "Standard test volume",
                "là thể tích quy định dùng để xác định sai số của đồng hồ xăng dầu trong một lần thử.",
                None,
            ),
        ),
        "bang1": [
            _step("Kiểm tra bên ngoài", "7.1"),
            _step("Kiểm tra kỹ thuật", "7.2"),
            _step("Xác định sai số tại lưu lượng lớn nhất", "7.3.1"),
            _step("Xác định sai số tại lưu lượng nhỏ nhất", "7.3.2", _STD_BD_SSC),
        ],
        "bang2": [
            _std("Bình chuẩn dung tích hạng 2", "(0 ÷ 20) L", "± 0,02 %"),
            _std("Nhiệt kế", "(0 ÷ 50) °C", "± 0,1 °C"),
            _std("Tỷ trọng kế", "(0,7 ÷ 1,0) kg/L", "± 0,001 kg/L"),
        ],
        "env": ENV_PROFILES[2],
        "interval_months": 12,
        "section6": [
            {
                "label": "Sai số thể tích thử",
                "sentence": "Sai số cho phép bằng ± 0,3 % thể tích thử nhưng không nhỏ hơn ± 0,05 lít trên một lần đo 20 lít.",
                "rel_op": "±",
                "value_text": "0,3 %",
                "condition_text": "không nhỏ hơn ± 0,05 lít",
                "limit": {"value": 0.3, "unit": "%", "quote": "± 0,3 % thể tích thử"},
                "floor": {"value": 0.05, "unit": "lít", "quote": "không nhỏ hơn ± 0,05 lít"},
            },
        ],
        "appendix_extra": ["Số cột bơm"],
    },
    {
        "number": "9.012",
        "short": "Máy đo độ ẩm hạt",
        "heading_style": "paren",
        "title": "Phương tiện đo độ ẩm hạt nông sản",
        "range": {"pattern": "tu_den", "value_text": "từ 5 % đến 40 %"},
        "references": [
            "Phương tiện đo độ ẩm hạt nông sản - chưa xác minh số hiệu ĐLVN",
            "Thông tư 23/2013/TT-BKHCN, mục 42",
        ],
        "terms": _terms(
            (
                "Độ ẩm hạt tuyệt đối",
                "Grain moisture content",
                "là tỷ lệ phần trăm khối lượng nước chứa trong hạt so với khối lượng hạt ướt.",
                None,
            ),
            (
                "Phương pháp sấy khô chuẩn",
                "Standard oven-drying method",
                "là phương pháp xác định độ ẩm hạt bằng cách sấy mẫu đến khối lượng không đổi.",
                "Phương pháp sấy khô chuẩn dùng làm chuẩn đối chiếu.",
            ),
        ),
        "bang1": [
            _step("Kiểm tra bên ngoài", "7.1"),
            _step("Kiểm tra kỹ thuật", "7.2"),
            _step("So sánh với mẫu chuẩn tại các mức ẩm khác nhau", "7.3"),
        ],
        "bang2": [
            _std("Mẫu hạt chuẩn", "(5 ÷ 40) %", "± 0,1 %"),
            _std("Cân phân tích", "(0 ÷ 200) g", "± 0,1 mg"),
            _std("Tủ sấy chuẩn", "(50 ÷ 150) °C", "± 1 °C"),
        ],
        "env": ENV_PROFILES[3],
        "interval_months": 12,
        "section6": [
            {
                "label": "Sai số so với mẫu chuẩn",
                "sentence": "Sai số cho phép bằng ± 3 % giá trị đo nhưng không nhỏ hơn ± 0,3 điểm % ẩm tuyệt đối.",
                "rel_op": "±",
                "value_text": "3 %",
                "condition_text": "không nhỏ hơn ± 0,3 điểm %",
                "limit": {"value": 3.0, "unit": "%", "quote": "± 3 % giá trị đo"},
                "floor": {"value": 0.3, "unit": "%", "quote": "không nhỏ hơn ± 0,3 điểm %"},
            },
        ],
        "appendix_extra": ["Loại hạt thử"],
    },
]

for _dev in DEVICES:
    _dev["range"]["prefix"] = _RANGE_PREFIX[_dev["range"]["pattern"]].format(
        short_lower=_dev["short"].lower()
    )

# Bốn QTKĐ chính (thứ tự trong DEVICES) dùng cho nhóm D (biên bản) + E (phiếu đo):
# mỗi QTKĐ có >=3 biên bản + >=1 phiếu đo với bảng khớp đúng Phụ lục A của nó.
MAIN_DEVICE_NUMBERS = ["9.001", "9.002", "9.003", "9.005"]

# Giữ tương thích ngược: một số module (build_cfg.py) tham chiếu DEFAULT_ENV cho
# nhóm F (phiên bản 2 tái dùng thiết bị 9.001) -- dùng đúng hồ sơ của 9.001.
DEFAULT_ENV = ENV_PROFILES[0]
