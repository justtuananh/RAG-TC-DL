"""Dựng nhóm D (biên bản .docx) và E (phiếu đo .xlsx) (Pha 2 §2).

12 biên bản + 4 phiếu đo cho 4 QTKĐ chính (>=3 biên bản, >=1 phiếu đo mỗi QTKĐ,
nhãn/cột khớp đúng Phụ lục A của chính QTKĐ đó); cộng 2 biên bản + 4 phiếu đo
nhắm riêng K06/K07/K01/K05/đa-sheet/nhãn-gộp-ô.
"""

from __future__ import annotations

from datetime import date

from scripts.knowledge_corpus import content_b as cb
from scripts.knowledge_corpus import content_records as cr
from scripts.knowledge_corpus import ooxml as ox
from scripts.knowledge_corpus.devices_a import DEVICES
from scripts.knowledge_corpus.qtkd_doc import appendix_labels
from scripts.knowledge_corpus.specs_io import (
    FILES_DIR,
    FileRecord,
    known_behaviors_for,
)

_MAIN_NUMBERS = ["9.001", "9.002", "9.003", "9.005"]
_DEV_BY_NUMBER = {d["number"]: d for d in DEVICES}

_EXTRA_VALUES = {
    "9.001": {"Cỡ van": "DN25", "Áp suất chỉnh đặt": "50 bar"},
    "9.002": {"Cấp chính xác": "1,6"},
    "9.003": {},
    "9.005": {"Mức cân lớn nhất": "150000 kg"},
}

# (nominal, deltas Đạt, deltas Không đạt, limit)
_POINTS = {
    "9.001": ([50.0, 50.0, 50.0], [0.05, -0.1, 0.1], [0.05, -0.1, 0.3], 0.15),
    "9.002": ([100.0, 150.0, 200.0], [0.03, 0.04, -0.04], [0.03, 0.04, 0.2], 0.05),
    "9.003": ([10.0, 20.0, 30.0], [0.2, 0.3, -0.2], [0.2, 0.3, 0.6], 0.4),
    "9.005": ([10000.0, 50000.0, 100000.0], [10.0, 15.0, -10.0], [10.0, 15.0, 30.0], 20.0),
}

_VERDICT_TEXT = {"dat": "Đạt", "khong_dat": "Không đạt"}


def _values_for(number: str, *, serial: str | None, model: str, date_text: str) -> dict[str, str]:
    dev = _DEV_BY_NUMBER[number]
    labels = [label for label in appendix_labels(dev) if label != "Kết luận"]
    out: dict[str, str] = {}
    for label in labels:
        if label == "Tên phương tiện đo":
            out[label] = dev["short"]
        elif label == "Ký hiệu":
            out[label] = model
        elif label == "Số hiệu":
            if serial is not None:
                out[label] = serial
        elif label in _EXTRA_VALUES[number]:
            out[label] = _EXTRA_VALUES[number][label]
        elif label == "Nơi (hãng) sản xuất":
            out[label] = "Công ty Đo lường ABC"
        elif label == "Đơn vị sử dụng":
            out[label] = "Nhà máy XYZ"
        elif label == "Nhiệt độ":
            out[label] = "22"
        elif label == "Độ ẩm":
            out[label] = "60"
        elif label == "Chế độ kiểm định":
            out[label] = "Định kỳ"
        elif label == "Phương pháp kiểm định":
            out[label] = f"QTKĐ {number} : 2026"
        elif label == "Ngày kiểm định":
            out[label] = date_text
        elif label == "Người kiểm định":
            out[label] = "Nguyễn Văn A"
        elif label == "Người soát lại":
            out[label] = "Nguyễn Văn B"
    return out


def _date_iso(day: int, month: int, year: int) -> str:
    return date(year, month, day).isoformat()


def _make_points(number: str, *, ok: bool) -> list[dict]:
    nominal, deltas_ok, deltas_bad, limit = _POINTS[number]
    deltas = deltas_ok if ok else deltas_bad
    return cr.synth_points(nominal, deltas, limit)


def _gold(
    *, file: str, number: str, values: dict, points: list[dict], date_iso: str, verdict: str
) -> dict:
    return {
        "file": file,
        "procedure_number": number,
        "fields": cr.gold_fields(
            procedure_number=number,
            values=values,
            date_iso=date_iso,
            mode="dinh_ky",
            verdict=verdict,
            temperature=22.0,
            humidity=60.0,
        ),
        "points": points,
    }


def _bien_ban_record(
    *,
    file_id: str,
    number: str,
    style: str,
    date_text: str,
    date_iso: str,
    ok: bool,
    serial: str | None,
    model: str,
    verdict_text: str,
    verdict: str,
    purpose: str,
) -> FileRecord:
    dev = _DEV_BY_NUMBER[number]
    filename = f"Biên bản kiểm định {dev['short']} {serial or 'khong-so-hieu'} {file_id}.docx"
    values = _values_for(number, serial=serial, model=model, date_text=date_text)
    points = _make_points(number, ok=ok)
    blocks = cr.build_bien_ban(
        dev_number=number,
        dev_short=dev["short"],
        dev_title=dev["title"],
        labels=list(values),
        values=values,
        points=points,
        verdict_text=verdict_text,
        style=style,
    )
    path = FILES_DIR / filename
    ox.write_docx(path, blocks)
    return FileRecord(
        id=file_id,
        file=filename,
        group="D",
        expected_doc_type="ho_so_kiem_dinh",
        expected_ingest="ok",
        procedure_number=number,
        purpose=purpose,
        spec={
            "kind": "bien_ban",
            "procedure_number": number,
            "style": style,
            "values": values,
            "points": points,
            "verdict_text": verdict_text,
        },
        records_golden=_gold(
            file=filename,
            number=number,
            values=values,
            points=points,
            date_iso=date_iso,
            verdict=verdict,
        ),
    )


def _phieu_do_record(
    *,
    file_id: str,
    number: str,
    date_text: str,
    date_iso: str | int,
    ok: bool,
    serial: str,
    model: str,
    verdict_text: str,
    verdict: str,
    purpose: str,
    inline_labels: bool = False,
    extra_sheet: bool = False,
    points_override: list[dict] | None = None,
) -> FileRecord:
    dev = _DEV_BY_NUMBER[number]
    filename = f"Phiếu đo {dev['short']} {serial} {file_id}.xlsx"
    values = _values_for(number, serial=serial, model=model, date_text=str(date_text))
    points = points_override if points_override is not None else _make_points(number, ok=ok)
    sheets = cr.build_phieu_do(
        dev_title=dev["title"],
        values=values,
        points=points,
        verdict_text=verdict_text,
        inline_labels=inline_labels,
        extra_sheet=extra_sheet,
    )
    path = FILES_DIR / filename
    ox.write_xlsx(path, sheets)
    return FileRecord(
        id=file_id,
        file=filename,
        group="E",
        expected_doc_type="phieu_do",
        expected_ingest="ok",
        procedure_number=number,
        purpose=purpose,
        spec={
            "kind": "phieu_do",
            "procedure_number": number,
            "values": values,
            "points": points,
            "verdict_text": verdict_text,
            "inline_labels": inline_labels,
            "extra_sheet": extra_sheet,
        },
        records_golden=_gold(
            file=filename,
            number=number,
            values=values,
            points=points,
            date_iso=str(date_iso),
            verdict=verdict,
        ),
    )


def _standard_bien_ban() -> list[FileRecord]:
    """8 biên bản chuẩn (2 mỗi QTKĐ chính) qua bốn kiểu trình bày/ngày tháng."""
    records: list[FileRecord] = []
    plan = [
        (
            "9.001",
            "D01",
            "paragraph",
            "15/01/2026",
            _date_iso(15, 1, 2026),
            True,
            "SN-2026-101",
            "VA-100",
            "Đạt",
            "dat",
        ),
        (
            "9.001",
            "D02",
            "table_colon",
            "5.2.2026",
            _date_iso(5, 2, 2026),
            False,
            "SN-2026-102",
            "VA-101",
            "Không đạt",
            "khong_dat",
        ),
        (
            "9.002",
            "D04",
            "paragraph",
            "2026-04-10",
            "2026-04-10",
            True,
            "sn-2026-201",
            "AK-200",
            "Đạt",
            "dat",
        ),
        (
            "9.002",
            "D05",
            "table",
            "12/05/2026",
            _date_iso(12, 5, 2026),
            False,
            "SN-2026-201",
            "AK-200",
            "Không đạt",
            "khong_dat",
        ),
        (
            "9.003",
            "D07",
            "paragraph",
            "20/06/2026",
            _date_iso(20, 6, 2026),
            True,
            "SN-2026-301",
            "HA-300",
            "Đạt",
            "dat",
        ),
        (
            "9.003",
            "D08",
            "table",
            "1.7.2026",
            _date_iso(1, 7, 2026),
            True,
            "SN-2026-302",
            "HA-301",
            "Đạt",
            "dat",
        ),
        (
            "9.005",
            "D10",
            "paragraph",
            "03/08/2026",
            _date_iso(3, 8, 2026),
            True,
            "SN-2026-401",
            "CAN-400",
            "Đạt",
            "dat",
        ),
        (
            "9.005",
            "D11",
            "table",
            "4.9.2026",
            _date_iso(4, 9, 2026),
            False,
            "SN-2026-402",
            "CAN-401",
            "Không đạt",
            "khong_dat",
        ),
    ]
    for number, fid, style, date_text, date_iso, ok, serial, model, verdict_text, verdict in plan:
        rec = _bien_ban_record(
            file_id=fid,
            number=number,
            style=style,
            date_text=date_text,
            date_iso=date_iso,
            ok=ok,
            serial=serial,
            model=model,
            verdict_text=verdict_text,
            verdict=verdict,
            purpose=f"Biên bản chuẩn cho QTKĐ {number}, kiểu trình bày {style}.",
        )
        if fid == "D02":
            rec.purpose = "Nhãn trong ô bảng có dấu hai chấm (\"Số hiệu:\" ...) -- toàn bộ trường bảng không khớp nhãn cấu hình (K03)."
            rec.known_behaviors = known_behaviors_for("D02")
        if fid == "D04":
            rec.purpose = "Ngày kiểm định ghi dạng ISO \"2026-04-10\" (K05)."
            rec.known_behaviors = known_behaviors_for("D04")
        records.append(rec)
    return records


def _multi_line_bien_ban() -> list[FileRecord]:
    """4 biên bản kiểu "nhiều trường một dòng", cộng K04/K09/thiếu số hiệu."""
    records: list[FileRecord] = []
    # Nhiều trường trên một dòng + thiếu số hiệu + kết luận mập mờ (K04).
    d03 = _bien_ban_record(
        file_id="D03",
        number="9.001",
        style="multi",
        date_text="ngày 20 tháng 3 năm 2026",
        date_iso=_date_iso(20, 3, 2026),
        ok=True,
        serial=None,
        model="VA-102",
        verdict_text="Đạt (không đạt) yêu cầu kỹ thuật đo lường.",
        verdict=None,
        purpose="Nhiều trường một dòng, thiếu số hiệu, ngày kiểu VN, kết luận mập mờ (K04).",
    )
    d03.known_behaviors = known_behaviors_for("D03")
    records.append(d03)
    records.append(
        _bien_ban_record(
            file_id="D06",
            number="9.002",
            style="multi",
            date_text="01/06/2026",
            date_iso=_date_iso(1, 6, 2026),
            ok=True,
            serial="SN-2026-203",
            model="AK-201",
            verdict_text="Đạt",
            verdict="dat",
            purpose="Nhiều trường một dòng cho QTKĐ 9.002.",
        )
    )
    records.append(
        _bien_ban_record(
            file_id="D09",
            number="9.003",
            style="multi",
            date_text="15/07/2026",
            date_iso=_date_iso(15, 7, 2026),
            ok=False,
            serial=None,
            model="HA-302",
            verdict_text="Không đạt",
            verdict="khong_dat",
            purpose="Thiếu số hiệu cho QTKĐ 9.003.",
        )
    )
    records.append(
        _bien_ban_record(
            file_id="D12",
            number="9.005",
            style="multi",
            date_text="10/10/2026",
            date_iso=_date_iso(10, 10, 2026),
            ok=True,
            serial="SN-2026-403",
            model="CAN-402",
            verdict_text="Đạt",
            verdict="dat",
            purpose="Nhiều trường một dòng cho QTKĐ 9.005; K09 (unit_id luôn NULL) áp dụng mọi hồ sơ D/E.",
        )
    )
    return records


def _standard_phieu_do() -> list[FileRecord]:
    """4 phiếu đo chuẩn (1 mỗi QTKĐ chính)."""
    records: list[FileRecord] = []
    e_plan = [
        (
            "9.001",
            "E01",
            "15/01/2026",
            _date_iso(15, 1, 2026),
            True,
            "SN-2026-111",
            "VA-110",
            "Đạt",
            "dat",
        ),
        (
            "9.002",
            "E02",
            "12/05/2026",
            _date_iso(12, 5, 2026),
            False,
            "SN-2026-211",
            "AK-210",
            "Không đạt",
            "khong_dat",
        ),
        (
            "9.003",
            "E03",
            "20/06/2026",
            _date_iso(20, 6, 2026),
            True,
            "SN-2026-311",
            "HA-310",
            "Đạt",
            "dat",
        ),
        (
            "9.005",
            "E04",
            "03/08/2026",
            _date_iso(3, 8, 2026),
            True,
            "SN-2026-411",
            "CAN-410",
            "Đạt",
            "dat",
        ),
    ]
    for number, fid, date_text, date_iso, ok, serial, model, verdict_text, verdict in e_plan:
        records.append(
            _phieu_do_record(
                file_id=fid,
                number=number,
                date_text=date_text,
                date_iso=date_iso,
                ok=ok,
                serial=serial,
                model=model,
                verdict_text=verdict_text,
                verdict=verdict,
                purpose=f"Phiếu đo chuẩn cho QTKĐ {number}.",
            )
        )
    return records


def build_group_d_e() -> list[FileRecord]:
    records: list[FileRecord] = []
    records += _standard_bien_ban()
    records += _multi_line_bien_ban()
    records.append(_d13_k07())
    records.append(_d14_k06())
    records += _standard_phieu_do()
    records.append(_e05_multi_sheet())
    records.append(_e06_k01())
    records.append(_e07_k05())
    records.append(_e08_inline())
    return records


def _d13_k07() -> FileRecord:
    number = "9.015"
    dev = _DEV_BY_NUMBER["9.001"]
    fill = [["120,05", "120,00", "0,05"], ["150,10", "150,00", "0,10"], ["80,00", "80,20", "-0,20"]]
    values = _values_for("9.001", serial="SN-2026-901", model="VA-901", date_text="11/11/2026")
    values["Phương pháp kiểm định"] = f"QTKĐ {number} : 2026"
    blocks = [
        ox.heading("BIÊN BẢN KIỂM ĐỊNH", 1),
        ox.para(f"BIÊN BẢN KIỂM ĐỊNH {dev['title'].upper()}"),
        *cr._field_lines_paragraph(values),
        ox.para(cb.K07_TABLE_TITLE),
        ox.table(cb.k07_appendix_rows(fill=fill)),
        ox.para("Kết luận: Đạt"),
    ]
    filename = "Biên bản kiểm định Van an toan SN-2026-901 D13.docx"
    path = FILES_DIR / filename
    ox.write_docx(path, blocks)
    points = [
        {
            "ordinal": 1,
            "nominal": None,
            "measured": 120.05,
            "error": 0.05,
            "limit": None,
            "note": "Đóng: 120,00",
        },
        {
            "ordinal": 2,
            "nominal": None,
            "measured": 150.10,
            "error": 0.10,
            "limit": None,
            "note": "Đóng: 150,00",
        },
        {
            "ordinal": 3,
            "nominal": None,
            "measured": 80.00,
            "error": -0.20,
            "limit": None,
            "note": "Đóng: 80,20",
        },
    ]
    return FileRecord(
        id="D13",
        file=filename,
        group="D",
        expected_doc_type="ho_so_kiem_dinh",
        expected_ingest="ok",
        procedure_number=number,
        purpose="Bảng gộp ô Mở/Đóng/Độ chênh áp -- cột bị gán sai vai trò khi đọc (K07).",
        spec={"kind": "bien_ban_k07", "procedure_number": number, "values": values, "fill": fill},
        known_behaviors=known_behaviors_for("D13"),
        records_golden=_gold(
            file=filename,
            number=number,
            values=values,
            points=points,
            date_iso=_date_iso(11, 11, 2026),
            verdict="dat",
        ),
    )


def _d14_k06() -> FileRecord:
    number = "9.001"
    dev = _DEV_BY_NUMBER[number]
    values = _values_for(number, serial="SN-2026-902", model="VA-902", date_text="")
    del values["Ngày kiểm định"]
    points = _make_points(number, ok=True)
    blocks = [
        ox.heading("BIÊN BẢN KIỂM ĐỊNH", 1),
        ox.para(f"BIÊN BẢN KIỂM ĐỊNH {dev['title'].upper()}"),
        *cr._field_lines_paragraph(values),
        ox.para("Ngày kiểm định tháng năm 2026"),  # không có dấu hai chấm (K06)
        ox.para("Bảng A.1 - Kết quả kiểm tra đo lường"),
        cr._result_table(cr.APPENDIX_TABLE_COLUMNS, points),
        ox.para("Kết luận: Đạt"),
    ]
    filename = "Biên bản kiểm định Van an toan SN-2026-902 D14.docx"
    path = FILES_DIR / filename
    ox.write_docx(path, blocks)
    return FileRecord(
        id="D14",
        file=filename,
        group="D",
        expected_doc_type="ho_so_kiem_dinh",
        expected_ingest="ok",
        procedure_number=number,
        purpose="Dòng \"Ngày kiểm định\" trong Phụ lục A không có dấu hai chấm (K06).",
        spec={"kind": "bien_ban_k06", "procedure_number": number, "values": values},
        known_behaviors=known_behaviors_for("D14"),
        records_golden=_gold(
            file=filename, number=number, values=values, points=points, date_iso=None, verdict="dat"
        ),
    )


def _e05_multi_sheet() -> FileRecord:
    number = "9.001"
    values = _values_for(number, serial="SN-2026-511", model="VA-510", date_text="15/01/2026")
    points = _make_points(number, ok=True)
    sheets = cr.build_phieu_do(
        dev_title=_DEV_BY_NUMBER[number]["title"],
        values=values,
        points=points,
        verdict_text="Đạt",
        extra_sheet=True,
    )
    filename = "Phiếu đo Van an toan SN-2026-511 E05.xlsx"
    path = FILES_DIR / filename
    ox.write_xlsx(path, sheets)
    return FileRecord(
        id="E05",
        file=filename,
        group="E",
        expected_doc_type="phieu_do",
        expected_ingest="ok",
        procedure_number=number,
        purpose="Phiếu đo nhiều sheet -- chỉ sheet đầu được đọc.",
        spec={
            "kind": "phieu_do_multi_sheet",
            "procedure_number": number,
            "values": values,
            "points": points,
        },
        records_golden=_gold(
            file=filename,
            number=number,
            values=values,
            points=points,
            date_iso=_date_iso(15, 1, 2026),
            verdict="dat",
        ),
    )


def _e06_k01() -> FileRecord:
    number = "9.002"
    values = _values_for(number, serial="SN-2026-611", model="AK-610", date_text="15/01/2026")
    labels = list(values)
    rows: list[list[object]] = [["PHIẾU ĐO", "", "", "", "", ""]]
    for label in labels:
        rows.append([label, values[label], "", "", "", ""])
    rows.append(["Kết luận", "Đạt", "", "", "", ""])
    rows.append(["", "", "", "", "", ""])
    rows.append(list(cr.APPENDIX_TABLE_COLUMNS))
    # Ô số thực dùng dấu chấm 3 chữ số thập phân -- kích hoạt K01 khi đọc lại.
    raw_points = [(1, 100.0, 100.125, 0.125, 0.500), (2, 100.0, 99.875, -0.125, 0.500)]
    for ordv, nominal, measured, error, limit in raw_points:
        rows.append([ordv, nominal, measured, error, limit, ""])
    filename = "Phiếu đo Ap ke SN-2026-611 E06.xlsx"
    path = FILES_DIR / filename
    ox.write_xlsx(path, [ox.Sheet("PhieuDo", rows)])
    points = [
        {"ordinal": o, "nominal": n, "measured": m, "error": e, "limit": lim, "note": ""}
        for o, n, m, e, lim in raw_points
    ]
    return FileRecord(
        id="E06",
        file=filename,
        group="E",
        expected_doc_type="phieu_do",
        expected_ingest="ok",
        procedure_number=number,
        purpose="Ô số thực 3 chữ số thập phân (10,125 kiểu dấu chấm) -- K01.",
        spec={
            "kind": "phieu_do_k01",
            "procedure_number": number,
            "values": values,
            "raw_points": raw_points,
        },
        known_behaviors=known_behaviors_for("E06"),
        records_golden=_gold(
            file=filename,
            number=number,
            values=values,
            points=points,
            date_iso=_date_iso(15, 1, 2026),
            verdict="dat",
        ),
    )


def _e07_k05() -> FileRecord:
    number = "9.003"
    values = _values_for(number, serial="SN-2026-711", model="HA-710", date_text="")
    labels = [label for label in values if label != "Ngày kiểm định"]
    points = _make_points(number, ok=True)
    rows: list[list[object]] = [["PHIẾU ĐO", "", "", "", "", ""]]
    for label in labels:
        rows.append([label, values[label], "", "", "", ""])
    rows.append(["Ngày kiểm định", ox.DateCell(date(2026, 7, 20)), "", "", "", ""])
    rows.append(["Kết luận", "Đạt", "", "", "", ""])
    rows.append(["", "", "", "", "", ""])
    rows.append(list(cr.APPENDIX_TABLE_COLUMNS))
    for p in points:
        rows.append([p["ordinal"], p["nominal"], p["measured"], p["error"], p["limit"], p["note"]])
    filename = "Phiếu đo Huyet ap ke SN-2026-711 E07.xlsx"
    path = FILES_DIR / filename
    ox.write_xlsx(path, [ox.Sheet("PhieuDo", rows)])
    values["Ngày kiểm định"] = "2026-07-20"
    return FileRecord(
        id="E07",
        file=filename,
        group="E",
        expected_doc_type="phieu_do",
        expected_ingest="ok",
        procedure_number=number,
        purpose="Ô ngày kiểu Excel (số serial) -- K05.",
        spec={"kind": "phieu_do_k05", "procedure_number": number, "values": values},
        known_behaviors=known_behaviors_for("E07"),
        records_golden=_gold(
            file=filename,
            number=number,
            values=values,
            points=points,
            date_iso="2026-07-20",
            verdict="dat",
        ),
    )


def _e08_inline() -> FileRecord:
    number = "9.005"
    values = _values_for(number, serial="SN-2026-811", model="CAN-810", date_text="03/08/2026")
    points = _make_points(number, ok=True)
    sheets = cr.build_phieu_do(
        dev_title=_DEV_BY_NUMBER[number]["title"],
        values=values,
        points=points,
        verdict_text="Đạt",
        inline_labels=True,
    )
    filename = "Phiếu đo Can o to SN-2026-811 E08.xlsx"
    path = FILES_DIR / filename
    ox.write_xlsx(path, sheets)
    return FileRecord(
        id="E08",
        file=filename,
        group="E",
        expected_doc_type="phieu_do",
        expected_ingest="ok",
        procedure_number=number,
        purpose="Nhãn và giá trị gộp trong cùng một ô (\"Nhãn: giá trị\").",
        spec={
            "kind": "phieu_do_inline",
            "procedure_number": number,
            "values": values,
            "points": points,
        },
        records_golden=_gold(
            file=filename,
            number=number,
            values=values,
            points=points,
            date_iso=_date_iso(3, 8, 2026),
            verdict="dat",
        ),
    )
