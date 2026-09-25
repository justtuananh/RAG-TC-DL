"""Nhóm D (biên bản .docx) và E (phiếu đo .xlsx) cho 4 QTKĐ chính nhóm A.

Mỗi bản ghi mô tả một hồ sơ: nhãn/giá trị đầu mục + bảng kết quả đo, dựng theo
ĐÚNG nhãn/cột Phụ lục A của QTKĐ tương ứng (``qtkd_doc.appendix_labels`` /
``APPENDIX_TABLE_COLUMNS``). Số liệu đo tính trực tiếp trong hàm (không gõ tay
rời) để ``records_golden.jsonl`` khớp tuyệt đối với nội dung tài liệu.
"""

from __future__ import annotations

from scripts.knowledge_corpus import ooxml as ox
from scripts.knowledge_corpus.qtkd_doc import APPENDIX_TABLE_COLUMNS

FIELD_LABEL_TO_GOLD_KEY = {
    "Số hiệu": "serial",
    "Ký hiệu": "model",
    "Nơi (hãng) sản xuất": "manufacturer",
    "Đơn vị sử dụng": "owner",
    "Số giấy chứng nhận": "certificate_no",
    "Người kiểm định": "inspector",
    "Người soát lại": "reviewer",
    "Phòng đo lường": "lab",
}


def synth_points(nominal: list[float], deltas: list[float], limit: float) -> list[dict]:
    """Tính ``measured = nominal + delta``; ``error = delta`` (P2: không suy ngược)."""
    points = []
    for i, (n, d) in enumerate(zip(nominal, deltas, strict=True), start=1):
        measured = round(n + d, 3)
        error = round(d, 3)
        points.append(
            {
                "ordinal": i,
                "nominal": n,
                "measured": measured,
                "error": error,
                "limit": limit,
                "note": "",
            }
        )
    return points


def verdict_from_points(points: list[dict]) -> str:
    return "dat" if all(abs(p["error"]) <= p["limit"] for p in points) else "khong_dat"


def _field_lines_paragraph(values: dict[str, str]) -> list[dict]:
    return [ox.para(f"{label}: {value}") for label, value in values.items()]


def _field_lines_multi_per_line(values: dict[str, str]) -> list[dict]:
    """Nhiều trường trên một dòng: gộp từng cặp nhãn/giá trị liền nhau."""
    items = list(values.items())
    blocks = []
    for i in range(0, len(items), 2):
        pair = items[i : i + 2]
        text = " ".join(f"{label}: {value}" for label, value in pair)
        blocks.append(ox.para(text))
    return blocks


def _field_table(values: dict[str, str], *, colon_in_cell: bool = False) -> dict:
    rows = []
    for label, value in values.items():
        cell_label = f"{label}:" if colon_in_cell else label
        rows.append([ox.Cell(cell_label), ox.Cell(value)])
    return ox.table(rows)


def _result_table(columns: list[str], points: list[dict]) -> dict:
    header = [ox.Cell(c) for c in columns]
    rows = [header]
    for p in points:
        rows.append(
            [
                ox.Cell(str(p["ordinal"])),
                ox.Cell(_fmt(p["nominal"])),
                ox.Cell(_fmt(p["measured"])),
                ox.Cell(_fmt(p["error"])),
                ox.Cell(_fmt(p["limit"])),
                ox.Cell(p["note"]),
            ]
        )
    return ox.table(rows)


def _fmt(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def build_bien_ban(
    *,
    dev_number: str,
    dev_short: str,
    dev_title: str,
    labels: list[str],
    values: dict[str, str],
    points: list[dict],
    verdict_text: str,
    style: str = "paragraph",
) -> list[dict]:
    """Dựng khối nội dung biên bản .docx theo một trong ba kiểu trình bày."""
    blocks = [
        ox.heading("BIÊN BẢN KIỂM ĐỊNH", 1),
        ox.para(f"BIÊN BẢN KIỂM ĐỊNH {dev_title.upper()}"),
    ]
    if style == "table":
        blocks.append(_field_table(values))
    elif style == "table_colon":
        blocks.append(_field_table(values, colon_in_cell=True))
    elif style == "multi":
        blocks += _field_lines_multi_per_line(values)
    else:
        blocks += _field_lines_paragraph(values)
    blocks.append(ox.para("Bảng A.1 - Kết quả kiểm tra đo lường"))
    blocks.append(_result_table(APPENDIX_TABLE_COLUMNS, points))
    blocks.append(ox.para(f"Kết luận: {verdict_text}"))
    return blocks


def build_phieu_do(
    *,
    dev_title: str,
    values: dict[str, str],
    points: list[dict],
    verdict_text: str,
    inline_labels: bool = False,
    extra_sheet: bool = False,
) -> list[ox.Sheet]:
    """Dựng phiếu đo .xlsx; ``inline_labels`` gộp nhãn+giá trị trong một ô."""
    rows: list[list[object]] = [["PHIẾU ĐO", "", "", "", "", ""]]
    rows.append([f"PHIẾU ĐO {dev_title.upper()}", "", "", "", "", ""])
    for label, value in values.items():
        if inline_labels:
            rows.append([f"{label}: {value}", "", "", "", "", ""])
        else:
            rows.append([label, value, "", "", "", ""])
    if inline_labels:
        rows.append([f"Kết luận: {verdict_text}", "", "", "", "", ""])
    else:
        rows.append(["Kết luận", verdict_text, "", "", "", ""])
    rows.append(["", "", "", "", "", ""])
    rows.append(list(APPENDIX_TABLE_COLUMNS))
    for p in points:
        rows.append([p["ordinal"], p["nominal"], p["measured"], p["error"], p["limit"], p["note"]])
    sheets = [ox.Sheet("PhieuDo", rows)]
    if extra_sheet:
        sheets.append(ox.Sheet("GhiChu", [["Ghi chú khác không phải sheet chính"]]))
    return sheets


def gold_fields(
    *,
    procedure_number: str,
    values: dict[str, str],
    date_iso: str | None,
    mode: str,
    verdict: str,
    temperature: float | None,
    humidity: float | None,
) -> dict:
    fields = {
        "serial": None,
        "model": None,
        "manufacturer": None,
        "owner": None,
        "certificate_no": None,
        "inspector": None,
        "reviewer": None,
        "lab": None,
        "date": date_iso,
        "mode": mode,
        "verdict": verdict,
        "temperature": temperature,
        "humidity": humidity,
    }
    for label, value in values.items():
        key = FIELD_LABEL_TO_GOLD_KEY.get(label)
        if key:
            fields[key] = value
    return fields
