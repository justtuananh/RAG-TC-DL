"""Đọc 4 file danh mục 877 (.docx) thành các dòng có cấu trúc + báo cáo lỗi cho người duyệt.

Bốn loại file (nhận theo tiêu đề, rồi theo tiêu đề cột):

- ``procedure``     DANH MỤC QUY TRÌNH: ký hiệu, tên, cấp ban hành, lĩnh vực, loại quy trình.
- ``capability_kd`` NĂNG LỰC KIỂM ĐỊNH: phương tiện, tham số đo lường, các quy trình, lĩnh vực.
- ``capability_hc`` NĂNG LỰC HIỆU CHUẨN: phương tiện, quy trình, lĩnh vực.
- ``standard``      DANH MỤC CHUẨN MẪU: tên, ký hiệu, số hiệu, đặc tính đo lường, chu kỳ.

Xử lý tự động các lỗi cấu trúc của file Word (mục 10.1 tài liệu kiến trúc):
ô gộp dọc (``vMerge``) không sinh dòng trống, nhiều mã dính liền trong ô được tách theo từng đoạn,
chỉ số trên (``vertAlign``) được giữ ("10⁻⁶"). Lỗi nội dung được ghi vào báo cáo, không tự sửa.

Chạy tay (nạp bản nháp; ``--approve`` duyệt luôn, chỉ dùng cho lần nạp đầu):

    python -m ingestion.registry_import "DANH MỤC QUY TRÌNH.docx" "NĂNG LỰC KIỂM ĐỊNH NAS THEO 877.docx" ...
"""

from __future__ import annotations

import argparse
import io
import logging
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from knowledge.catalog_codes import CatalogCode, parse_code, parse_codes
from knowledge.catalog_units import QUANTITY_LABELS, CatalogRange, interval_months, parse_ranges
from retrieval.normalize import fold

logger = logging.getLogger(__name__)

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_SUPERSCRIPT = str.maketrans("0123456789-−+()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁻⁺⁽⁾ⁿ")

KINDS = ("procedure", "capability_kd", "capability_hc", "standard")
KIND_LABELS = {
    "procedure": "Danh mục quy trình",
    "capability_kd": "Năng lực kiểm định",
    "capability_hc": "Năng lực hiệu chuẩn",
    "standard": "Danh mục chuẩn mẫu",
}


class CatalogFormatError(ValueError):
    """File không phải một trong 4 loại danh mục, hoặc không đọc được bảng."""


@dataclass(frozen=True)
class Issue:
    level: str  # "error" | "warning" | "info"
    row: int | None
    message: str

    def as_dict(self) -> dict:
        return {"level": self.level, "row": self.row, "message": self.message}


@dataclass(frozen=True)
class ProcedureRow:
    row: int
    code_raw: str
    code: CatalogCode | None
    title: str
    issuer: str
    field: str
    kind: str  # "kiem_dinh" | "hieu_chuan"


@dataclass(frozen=True)
class CapabilityRow:
    row: int
    kind: str  # "kiem_dinh" | "hieu_chuan"
    name: str
    params_raw: str
    procedures_raw: str
    codes: tuple[CatalogCode, ...]
    field: str
    ranges: tuple[CatalogRange, ...]


@dataclass(frozen=True)
class StandardRow:
    row: int
    name: str
    model: str
    serial: str
    characteristics_raw: str
    interval_raw: str
    interval_months: int | None
    field: str
    ranges: tuple[CatalogRange, ...]


@dataclass
class ParsedCatalog:
    kind: str
    title: str
    procedures: list[ProcedureRow] = field(default_factory=list)
    capabilities: list[CapabilityRow] = field(default_factory=list)
    standards: list[StandardRow] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return len(self.procedures) + len(self.capabilities) + len(self.standards)


# ── Đọc bảng Word ────────────────────────────────────────────────────────────


def _run_text(run: etree._Element) -> str:
    parts: list[str] = []
    for child in run:
        if child.tag == _W + "t":
            parts.append(child.text or "")
        elif child.tag == _W + "tab":
            parts.append(" ")
        elif child.tag in (_W + "br", _W + "cr"):
            parts.append("\n")
    text = "".join(parts)
    align = run.find(f"{_W}rPr/{_W}vertAlign")
    if align is not None and align.get(_W + "val") == "superscript":
        return text.translate(_SUPERSCRIPT)
    return text


def _paragraph_text(paragraph: etree._Element) -> str:
    text = "".join(_run_text(run) for run in paragraph.iter(_W + "r"))
    return " ".join(text.split())


def _cell_text(cell: etree._Element) -> str:
    paragraphs = [_paragraph_text(p) for p in cell.findall(_W + "p")]
    return "\n".join(p for p in paragraphs if p)


def _cell_span(cell: etree._Element) -> tuple[int, bool]:
    """(số cột lưới chiếm, có phải ô tiếp nối của ô gộp dọc)."""
    props = cell.find(_W + "tcPr")
    if props is None:
        return 1, False
    span = props.find(_W + "gridSpan")
    width = int(span.get(_W + "val", "1")) if span is not None else 1
    merge = props.find(_W + "vMerge")
    continued = merge is not None and merge.get(_W + "val", "continue") != "restart"
    return width, continued


def _table_rows(table: etree._Element) -> list[list[str]]:
    """Các dòng của bảng theo ô. Ô tiếp nối của ô gộp dọc lấy chữ của ô phía trên;
    dòng chỉ gồm ô tiếp nối và ô trống bị bỏ (không sinh dòng trống hay dòng trùng)."""
    rows: list[list[str]] = []
    above: dict[int, str] = {}
    for tr in table.findall(_W + "tr"):
        values: list[str] = []
        own_text = False
        column = 0
        for cell in tr.findall(_W + "tc"):
            width, continued = _cell_span(cell)
            text = above.get(column, "") if continued else _cell_text(cell)
            if not continued:
                above[column] = text
                own_text = own_text or bool(text)
            values.append(text)
            column += width
        if own_text:
            rows.append(values)
    return rows


def _read_docx(data: bytes) -> tuple[str, list[list[list[str]]]]:
    """(tiêu đề = đoạn đầu tiên có chữ, các bảng)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            root = etree.fromstring(archive.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, etree.XMLSyntaxError) as e:
        raise CatalogFormatError(f"Không đọc được file Word: {e}") from e
    body = root.find(_W + "body")
    if body is None:
        raise CatalogFormatError("File Word không có nội dung.")
    title = ""
    tables: list[list[list[str]]] = []
    for element in body:
        if element.tag == _W + "p" and not title:
            title = _paragraph_text(element)
        elif element.tag == _W + "tbl":
            tables.append(_table_rows(element))
    return title, tables


# ── Nhận loại file và cột ────────────────────────────────────────────────────

_COLUMN_KEYS: dict[str, dict[str, str]] = {
    "procedure": {
        "ky hieu": "code",
        "ten quy trinh": "title",
        "cap ban hanh": "issuer",
        "linh vuc": "field",
        "loai quy trinh": "kind",
    },
    "capability": {
        "ten phuong tien": "name",
        "tham so": "params",
        "ky hieu": "procedures",
        "linh vuc": "field",
    },
    "standard": {
        "ten chuan": "name",
        "so hieu": "serial",
        "ky hieu": "model",
        "dac tinh": "characteristics",
        "chu ky": "interval",
        "tt": "ord",
    },
}


def detect_kind(title: str, header: list[str]) -> str:
    folded = fold(title)
    if "nang luc kiem dinh" in folded:
        return "capability_kd"
    if "nang luc hieu chuan" in folded:
        return "capability_hc"
    if "chuan mau" in folded:
        return "standard"
    if "quy trinh" in folded:
        return "procedure"
    joined = " | ".join(fold(h) for h in header)
    if "ten chuan" in joined:
        return "standard"
    if "duoc kiem dinh" in joined:
        return "capability_kd"
    if "duoc hieu chuan" in joined:
        return "capability_hc"
    if "ten quy trinh" in joined:
        return "procedure"
    raise CatalogFormatError(
        "Không nhận ra loại danh mục. Cần một trong: danh mục quy trình, năng lực kiểm định, "
        "năng lực hiệu chuẩn, danh mục chuẩn mẫu."
    )


def _columns(kind: str, header: list[str]) -> dict[str, int]:
    keys = _COLUMN_KEYS["capability" if kind.startswith("capability") else kind]
    mapping: dict[str, int] = {}
    for index, text in enumerate(header):
        folded = fold(text)
        for needle, name in keys.items():
            if name in mapping:
                continue
            if (folded == needle) if needle == "tt" else (needle in folded):
                mapping[name] = index
                break
    return mapping


def _header_index(rows: list[list[str]]) -> int:
    for index, row in enumerate(rows):
        if any(fold(cell).startswith("ten ") for cell in row):
            return index
    raise CatalogFormatError("Không tìm thấy dòng tiêu đề cột của bảng danh mục.")


def _get(row: list[str], columns: dict[str, int], name: str) -> str:
    index = columns.get(name)
    return row[index].strip() if index is not None and index < len(row) else ""


def _flat(text: str) -> str:
    return " ".join(text.split())


# ── Tách từng loại dòng ──────────────────────────────────────────────────────

_LOST_SUPERSCRIPT_RE = re.compile(r"×\s*10\s*-\s*\d|\b10-\d+\s*(?:đến|Ω)")
_BAD_CCX_RE = re.compile(r"CCX\s*:\s*0\d{2}\b")


def _kind_of(text: str, default: str) -> str:
    folded = fold(text)
    if "hieu chuan" in folded:
        return "hieu_chuan"
    if "kiem dinh" in folded:
        return "kiem_dinh"
    return default


def _short(text: str, limit: int = 120) -> str:
    flat = _flat(text)
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _common_issues(row: int, text: str, issues: list[Issue]) -> None:
    if _LOST_SUPERSCRIPT_RE.search(text):
        issues.append(Issue("warning", row, f"Có thể mất chỉ số trên (lũy thừa) trong: «{_short(text)}»"))


def _code_issues(row: int, owner: str, code: CatalogCode, issues: list[Issue]) -> None:
    if not code.prefix:
        return
    if code.year is None:
        issues.append(Issue("warning", row, f"{owner}ký hiệu «{code.raw}» thiếu năm ban hành"))
    elif re.sub(r"\s", "", code.raw) != re.sub(r"\s", "", code.key):
        issues.append(Issue("info", row, f"{owner}đã chuẩn hoá ký hiệu «{code.raw}» thành «{code.key}»"))


def _parse_procedure(row_no: int, row: list[str], columns: dict[str, int], issues: list[Issue]) -> ProcedureRow:
    code_raw = _flat(_get(row, columns, "code"))
    code = parse_code(code_raw)
    if code is None:
        issues.append(Issue("error", row_no, f"Không đọc được ký hiệu quy trình «{code_raw}»"))
    else:
        _code_issues(row_no, "", code, issues)
    return ProcedureRow(
        row=row_no,
        code_raw=code_raw,
        code=code,
        title=_flat(_get(row, columns, "title")),
        issuer=_flat(_get(row, columns, "issuer")),
        field=_flat(_get(row, columns, "field")),
        kind=_kind_of(_get(row, columns, "kind"), "kiem_dinh"),
    )


def _parse_capability(
    kind: str, row_no: int, row: list[str], columns: dict[str, int], issues: list[Issue]
) -> CapabilityRow:
    name = _flat(_get(row, columns, "name"))
    params = _get(row, columns, "params")
    procedures_raw = _get(row, columns, "procedures")
    codes = tuple(parse_codes(procedures_raw))
    field_text = _flat(_get(row, columns, "field"))
    ranges = tuple(parse_ranges(params))
    if not codes:
        issues.append(Issue("warning", row_no, f"«{name}» để trống hoặc không đọc được cột quy trình"))
    for code in codes:
        _code_issues(row_no, f"«{name}»: ", code, issues)
    if re.fullmatch(r"[\d\s.]+", field_text or "x"):
        issues.append(Issue("warning", row_no, f"«{name}»: cột lĩnh vực ghi «{field_text}», không phải tên lĩnh vực"))
    if params and not ranges:
        issues.append(Issue("info", row_no, f"«{name}»: không tách được dải đo thành số, chỉ giữ nguyên văn"))
    _common_issues(row_no, params, issues)
    return CapabilityRow(
        row=row_no,
        kind="kiem_dinh" if kind == "capability_kd" else "hieu_chuan",
        name=name,
        params_raw=params,
        procedures_raw=procedures_raw,
        codes=codes,
        field=field_text,
        ranges=ranges,
    )


def _parse_standard(row_no: int, row: list[str], columns: dict[str, int], issues: list[Issue]) -> StandardRow:
    name = _flat(_get(row, columns, "name"))
    characteristics = _get(row, columns, "characteristics")
    interval_raw = _flat(_get(row, columns, "interval"))
    months = interval_months(interval_raw)
    ranges = tuple(parse_ranges(characteristics))
    if interval_raw and months is None:
        issues.append(Issue("warning", row_no, f"«{name}»: chu kỳ «{interval_raw}» thiếu đơn vị (năm/tháng)"))
    if not interval_raw:
        issues.append(Issue("warning", row_no, f"«{name}»: để trống chu kỳ kiểm định/hiệu chuẩn"))
    bad = _BAD_CCX_RE.search(characteristics)
    if bad:
        issues.append(Issue("warning", row_no, f"«{name}»: cấp chính xác ghi «{bad.group(0)}», cần kiểm tra lại"))
    if characteristics and not ranges:
        issues.append(Issue("info", row_no, f"«{name}»: không tách được dải đo thành số, chỉ giữ nguyên văn"))
    _common_issues(row_no, characteristics, issues)
    quantities = [QUANTITY_LABELS.get(r.quantity, "") for r in ranges]
    return StandardRow(
        row=row_no,
        name=name,
        model=_flat(_get(row, columns, "model")),
        serial=_flat(_get(row, columns, "serial")),
        characteristics_raw=characteristics,
        interval_raw=interval_raw,
        interval_months=months,
        field=quantities[0] if quantities else "",
        ranges=ranges,
    )


def _row_number(row: list[str], columns: dict[str, int], fallback: int) -> int:
    value = _get(row, columns, "ord")
    return int(value) if value.isdigit() else fallback


def parse_catalog(data: bytes) -> ParsedCatalog:
    """Đọc một file danh mục; lỗi định dạng ném ``CatalogFormatError``.

    Số dòng (``row``) là số thứ tự trong file: cột TT nếu có số, không thì thứ tự dòng dữ liệu
    (Word đánh số tự động nên cột TT để trống trong XML)."""
    title, tables = _read_docx(data)
    tables = [t for t in tables if t]
    if not tables:
        raise CatalogFormatError("File không có bảng danh mục.")
    rows = max(tables, key=len)
    header_at = _header_index(rows)
    header = rows[header_at]
    kind = detect_kind(title, header)
    columns = _columns(kind, header)
    required = "code" if kind == "procedure" else "name"
    if required not in columns:
        raise CatalogFormatError(f"Không tìm thấy cột bắt buộc của {KIND_LABELS[kind].lower()}.")
    parsed = ParsedCatalog(kind=kind, title=title)
    ordinal = 0
    for row in rows[header_at + 1 :]:
        key = _get(row, columns, required)
        if not key or re.fullmatch(r"\(?\d+\)?", key):
            continue  # dòng đánh số cột "(1) (2) ..." hoặc dòng không có tên
        ordinal += 1
        row_no = _row_number(row, columns, ordinal)
        if kind == "procedure":
            parsed.procedures.append(_parse_procedure(row_no, row, columns, parsed.issues))
        elif kind == "standard":
            parsed.standards.append(_parse_standard(row_no, row, columns, parsed.issues))
        else:
            parsed.capabilities.append(_parse_capability(kind, row_no, row, columns, parsed.issues))
    if parsed.row_count == 0:
        raise CatalogFormatError("Bảng danh mục không có dòng dữ liệu nào.")
    _duplicate_issues(parsed)
    return parsed


def _duplicate_issues(parsed: ParsedCatalog) -> None:
    seen: dict[str, int] = {}
    for item in parsed.procedures:
        if item.code is None:
            continue
        if item.code.key in seen:
            parsed.issues.append(
                Issue("warning", item.row, f"Ký hiệu «{item.code.key}» trùng với dòng {seen[item.code.key]}")
            )
        else:
            seen[item.code.key] = item.row
    serials: dict[tuple[str, str], int] = {}
    for item in parsed.standards:
        key = (fold(item.model), fold(item.serial))
        if not item.serial:
            continue
        if key in serials:
            parsed.issues.append(
                Issue("warning", item.row, f"Chuẩn «{item.model}» số hiệu «{item.serial}» trùng với dòng {serials[key]}")
            )
        else:
            serials[key] = item.row


# ── CLI ──────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    from core.startup import startup
    from knowledge import registry

    parser = argparse.ArgumentParser(description="Nạp file danh mục 877 vào sổ đăng ký (bản nháp).")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--approve", action="store_true", help="Duyệt luôn bản vừa nạp (chỉ dùng cho lần nạp đầu)")
    args = parser.parse_args(argv)
    startup()
    status = 0
    for path in args.files:
        try:
            source = registry.import_file(path.name, path.read_bytes(), user=None)
        except (CatalogFormatError, registry.RegistryError) as e:
            logger.error("%s: %s", path.name, e)
            status = 1
            continue
        logger.info(
            "%s: %s, %d dòng, %d ghi chú", path.name, source["kind_label"], source["row_count"], len(source["issues"])
        )
        if args.approve:
            registry.decide(source["id"], source["revision"], approve=True, note="Nạp lần đầu bằng dòng lệnh", user=None)
            logger.info("%s: đã duyệt", path.name)
    return status


if __name__ == "__main__":
    sys.exit(main())
