"""Đọc biên bản/phiếu đo Excel theo cấu hình ánh xạ trường (spec §5.5, §9 S7).

Giống ``docx_reader``, bộ đọc này dùng OOXML thô (``zipfile`` + ``lxml``) thay vì
``openpyxl`` để giữ tính offline và không thêm phụ thuộc. Trình tự:

1. đọc MỌI sheet (``records.xlsx_grid``), vì sheet đầu có thể chỉ là bảng tra phụ;
2. neo các bảng kết quả theo tiêu đề bảng (``records.xlsx_tables``);
3. đọc trường đầu mục, BỎ QUA ô thuộc bảng đã neo để giá trị không bị lấy nhầm
   từ bảng đặt song song;
4. thêm kết luận, ô đánh dấu, tên người ký (``records.record_marks``).

Bảng không neo được dùng cách cũ: tìm dòng tiêu đề cột khớp cấu hình.

Bất biến P1/P2 giữ nguyên: mỗi ô số giữ nguyên văn; ``error_value`` chỉ đọc từ
cột sai số của phiếu, không bao giờ tính từ ``measured``/``nominal``.
"""

from __future__ import annotations

import re
from pathlib import Path

from knowledge import vnnum
from records.columns import map_measurement_row
from records.docx_reader import _extract_labeled_fields, _row_is_header, _slug
from records.record_marks import record_mark_fields
from records.template import MappingConfig
from records.types import FieldDraft, MeasurementDraft, RecordDraft
from records.xlsx_grid import Sheet, read_sheets
from records.xlsx_tables import TableRegion, locate_tables, step_code_for

EXTRACTOR = "record:xlsx.v1"
DEFAULT_SECTION_PATH = "Phiếu đo"

_WORD_RE = re.compile(r"\w+")
# Số thứ tự đứng trước nhãn ("1. ", "3.2 ", "a) ", "II. ").
_ENUMERATOR_RE = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[IVX]+\.|[a-zđ]\))\s+", re.IGNORECASE)
# Giá trị mẫu để trống: chỉ gồm dấu chấm, dấu chấm lửng, gạch dưới.
_PLACEHOLDER_RE = re.compile(r"^[.\u2026_\s]*$")
# Phần dư sau nhãn được coi là phần của nhãn ("Nhiệt độ môi trường:"): ngắn, không số.
_MAX_LABEL_TAIL_WORDS = 3
_MIN_LABEL_WORDS_FOR_TAIL = 2


def _clean(text: str) -> str:
    return vnnum.normalize_spaces(text or "").strip()


def _read_grid(path: str | Path) -> list[list[str]]:
    """Mọi dòng của mọi sheet nối liền (dùng để nhận diện nhanh mã QTKĐ)."""
    return [row for sheet in read_sheets(path) for row in sheet.rows]


def _label_prefix(text: str, label: str) -> str | None:
    """Phần còn lại của ``text`` nếu ``text`` mở đầu bằng ``label`` (so từng từ).

    So theo slug liền không dấu cách nên "pít tông" khớp "píttông"; ranh giới từ
    được giữ nên nhãn "Số" không khớp "Sổ tay"/"Sốc".
    """
    target = _slug(label).replace("_", "")
    if not target:
        return None
    compact = ""
    for match in _WORD_RE.finditer(text):
        compact += _slug(match.group(0)).replace("_", "")
        if compact == target:
            return text[match.end() :]
        if not target.startswith(compact):
            return None
    return None


def _is_label_cell(label: str, rest: str) -> bool:
    """Ô chỉ chứa nhãn (giá trị nằm ở ô bên phải)."""
    tail = rest.strip()
    if tail in ("", ":"):
        return True
    if len(label.split()) < _MIN_LABEL_WORDS_FOR_TAIL:
        return False
    body = tail[:-1] if tail.endswith(":") else tail
    if ":" in body or any(char.isdigit() for char in body):
        return False
    return len(body.split()) <= _MAX_LABEL_TAIL_WORDS


def _match_label(text: str, labels: list[str]) -> tuple[str, str, bool] | None:
    """``(nhãn, phần còn lại, là ô nhãn)`` cho nhãn dài nhất mở đầu ô; ``None`` nếu không."""
    for label in labels:
        rest = _label_prefix(text, label)
        if rest is None:
            continue
        if _is_label_cell(label, rest):
            return label, rest, True
        if rest.lstrip().startswith(":"):
            return label, rest, False
    return None


def _neighbour_value(sheet: Sheet, sheet_index: int, row: int, col: int, labels, regions) -> str:
    """Ghép các ô có chữ bên phải cùng dòng, dừng ở ô thuộc bảng hoặc ô nhãn kế tiếp."""
    parts: list[str] = []
    for next_col in range(col + 1, len(sheet.rows[row])):
        if any(region.covers(sheet_index, row, next_col) for region in regions):
            break
        text = _clean(sheet.cell(row, next_col))
        if not text:
            continue
        if text.endswith(":") or _match_label(text, labels) is not None:
            break
        parts.append(text)
    return _clean(" ".join(parts))


def _inline_fields(text: str, label: str, rest: str, labels: list[str]) -> list[tuple[str, str]]:
    """Nhãn và giá trị chung ô ("Số: 012/BBKĐ", "Ký hiệu: X Số hiệu: Y")."""
    pairs = _extract_labeled_fields(text, labels)
    if pairs and _slug(pairs[0][0]) == _slug(label):
        return [(label, pairs[0][1]), *pairs[1:]]
    return [(label, rest.lstrip().lstrip(":").strip())]


def _value(text: str) -> str:
    return "" if _PLACEHOLDER_RE.match(text or "") else text


def _cell_fields(sheet, sheet_index, row, col, labels, regions) -> list[tuple[str, str]]:
    """Trường mở đầu ô (sau số thứ tự nếu có); nhãn nằm giữa câu không phải trường."""
    text = _ENUMERATOR_RE.sub("", _clean(sheet.cell(row, col)))
    matched = _match_label(text, labels)
    if matched is None:
        pairs = _extract_labeled_fields(text, labels)
        leading = bool(pairs) and _label_prefix(text, pairs[0][0]) is not None
        return [(label, _value(value)) for label, value in pairs] if leading else []
    label, rest, is_label_cell = matched
    if is_label_cell:
        return [(label, _value(_neighbour_value(sheet, sheet_index, row, col, labels, regions)))]
    return [(name, _value(value)) for name, value in _inline_fields(text, label, rest, labels)]


def _header_fields(
    sheets: list[Sheet], labels: list[str], regions: list[TableRegion]
) -> list[FieldDraft]:
    ordered = sorted({label.strip() for label in labels if label.strip()}, key=len, reverse=True)
    fields: list[FieldDraft] = []
    seen: set[str] = set()
    for sheet_index, sheet in enumerate(sheets):
        for row, cells in enumerate(sheet.rows):
            quote = " | ".join(_clean(cell) for cell in cells if _clean(cell))
            for col, cell in enumerate(cells):
                if not _clean(cell) or any(
                    region.covers(sheet_index, row, col) for region in regions
                ):
                    continue
                for label, value in _cell_fields(sheet, sheet_index, row, col, ordered, regions):
                    key = _slug(label)
                    if key and key not in seen:
                        fields.append(
                            FieldDraft(label=label.rstrip(":").strip(), value=value, quote=quote)
                        )
                        seen.add(key)
    return fields


def _legacy_table(grid: list[list[str]], table) -> list[MeasurementDraft] | None:
    """Một bảng theo cách cũ trên MỘT sheet; ``None`` nếu sheet không có dòng tiêu đề khớp."""
    header_index = next(
        (i for i, row in enumerate(grid) if _row_is_header(row, table.columns)), None
    )
    if header_index is None:
        return None
    data_rows = grid[header_index + 1 :]
    # Bỏ dòng header tầng dưới (ô đầu rỗng, ô khác có chữ) ngay sau header.
    if data_rows and data_rows[0] and not data_rows[0][0].strip():
        data_rows = data_rows[1:]
    measurements: list[MeasurementDraft] = []
    for row in data_rows:
        cells = (list(row) + [""] * len(table.columns))[: len(table.columns)]
        if any(cell.strip() for cell in cells):
            measurements.append(map_measurement_row(table.columns, cells))
    return measurements


def _legacy_measurements(sheets: list[Sheet], tables) -> list[MeasurementDraft]:
    """Cách cũ cho bảng không neo được: dòng tiêu đề cột khớp cấu hình, map theo vị trí.

    Mỗi bảng lấy ở sheet ĐẦU TIÊN có dòng tiêu đề khớp và không bao giờ đọc tràn
    sang sheet sau. Lưới thưa (bỏ dòng không có ô nào) giữ đúng ngữ nghĩa cũ.
    """
    measurements: list[MeasurementDraft] = []
    for table in tables:
        for sheet in sheets:
            found = _legacy_table([row for row in sheet.rows if row], table)
            if found is not None:
                measurements.extend(found)
                break
    return measurements


def _measurements(sheets: list[Sheet], config: MappingConfig, regions: list[TableRegion]):
    anchored = {region.step_code for region in regions}
    pending = [table for table in config.result_tables if step_code_for(table) not in anchored]
    anchored_points = [point for region in regions for point in region.measurements]
    return anchored_points + _legacy_measurements(sheets, pending)


def _source_text(sheets: list[Sheet]) -> str:
    lines: list[str] = []
    for sheet in sheets:
        lines.append(f"[Sheet: {sheet.name}]")
        lines.extend(
            line
            for line in (" | ".join(cell for cell in row if cell.strip()) for row in sheet.rows)
            if line
        )
    return "\n".join(lines)


def read_xlsx(
    path: str | Path, config: MappingConfig, *, section_path: str | None = None
) -> RecordDraft:
    """Đọc một biên bản/phiếu đo Excel theo ``config``; trả ``RecordDraft`` giữ nguyên văn."""
    sheets = read_sheets(path)
    regions = locate_tables(sheets, config)
    fields = _header_fields(sheets, [item.label for item in config.header_fields], regions)
    mark_fields, warnings = record_mark_fields([sheet.rows for sheet in sheets])
    seen = {_slug(field.label) for field in fields}
    fields.extend(field for field in mark_fields if _slug(field.label) not in seen)
    return RecordDraft(
        extractor=EXTRACTOR,
        source_text=_source_text(sheets),
        section_path=section_path or DEFAULT_SECTION_PATH,
        fields=fields,
        measurements=_measurements(sheets, config, regions),
        warnings=warnings,
    )
