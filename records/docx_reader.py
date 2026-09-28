"""Đọc biên bản kiểm định Word theo cấu hình ánh xạ trường (spec §5.5, §9 S7).

Bộ đọc dùng OOXML thô (``zipfile`` + ``lxml``) như ``ingestion/extract_docx.py``,
không cần ``python-docx``. Nó trả ``RecordDraft`` thuần dữ liệu; tầng ``store``
mới ghi sổ cái.

Bất biến:

- **P1**: mỗi trường và mỗi dòng số liệu giữ nguyên văn nguồn (``quote``/``*_text``).
- **P2**: KHÔNG tính lại số liệu. ``error_value`` chỉ đến từ ô "Sai số"/"Độ chênh
  áp" của tài liệu; thiếu ô đó thì để trống, tuyệt đối không lấy ``measured -
  nominal``.

Cấu hình ánh xạ trường do ``records.template`` dựng từ Phụ lục A đã duyệt.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from lxml import etree

from ingestion.docx_grid import grid_slots
from knowledge import vnnum
from records.columns import map_measurement_row as _map_measurement_row
from records.columns import role_for_column as _role_for_column
from records.columns import unit_from_header as _unit_from_header
from records.template import MappingConfig
from records.types import FieldDraft, MeasurementDraft, RecordDraft

__all__ = ["read_docx", "_map_measurement_row", "_role_for_column", "_unit_from_header"]

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_W = f"{{{NS['w']}}}"
_W_T = f"{_W}t"
_W_P = f"{_W}p"
_W_TBL = f"{_W}tbl"
_W_TR = f"{_W}tr"
_W_TC = f"{_W}tc"

EXTRACTOR = "record:docx.v1"
DEFAULT_SECTION_PATH = "Phụ lục A"


def _slug(text: str) -> str:
    from records.template import slugify

    return slugify(text)


def _cell_text(cell) -> str:
    return vnnum.normalize_spaces("".join(node.text or "" for node in cell.iter(_W_T))).strip()


def _paragraph_text(paragraph) -> str:
    return vnnum.normalize_spaces(
        "".join(node.text or "" for node in paragraph.iter(_W_T))
    ).strip()


def _iter_blocks(root) -> list[tuple[str, object]]:
    """Trả danh sách khối theo thứ tự tài liệu: ``("p", text)`` hoặc ``("table", rows)``."""
    body = root.find(f"{_W}body")
    if body is None:
        return []
    blocks: list[tuple[str, object]] = []
    for child in body:
        if child.tag == _W_P:
            text = _paragraph_text(child)
            if text:
                blocks.append(("p", text))
        elif child.tag == _W_TBL:
            rows: list[list[str]] = []
            for tr in child.findall(_W_TR):
                cells: list[str] = []
                for slot in grid_slots(tr):
                    # K07: cùng quy tắc với ingestion.extract_docx: ô gộp dọc tiếp
                    # nối để trống, ô gridSpan chiếm N cột (văn bản ở cột đầu).
                    text = "" if slot.continues else _cell_text(slot.cell)
                    cells.append(text)
                    cells.extend([""] * (slot.span - 1))
                rows.append(cells)
            if rows:
                blocks.append(("table", rows))
    return blocks


def _labels_pattern(labels: list[str]) -> re.Pattern[str] | None:
    if not labels:
        return None
    # Nhãn dài trước để "Tên phương tiện đo" không bị "Tên" cắt mất.
    ordered = sorted({label.strip() for label in labels if label.strip()}, key=len, reverse=True)
    return re.compile("|".join(re.escape(label) for label in ordered), re.IGNORECASE)


def _extract_labeled_fields(
    text: str, labels: list[str]
) -> list[tuple[str, str]]:
    """Tách ``(nhãn, giá trị)`` từ một dòng, xử lý nhiều trường trên một dòng.

    Giá trị của một nhãn là phần văn bản tới nhãn kế tiếp. Nhờ vậy dòng
    ``"Ký hiệu: Số hiệu:"`` cho hai trường rỗng thay vì gán nhầm "Số hiệu" làm
    giá trị của "Ký hiệu".
    """
    pattern = _labels_pattern(labels)
    if pattern is None or not text:
        return []
    matches = list(pattern.finditer(text))
    if not matches:
        return []
    results: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        label = match.group(0)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        raw_value = text[start:end]
        # Bỏ dấu hai chấm/khảng cách ngay sau nhãn và dấu hai chấm cuối giá trị.
        value = raw_value.lstrip(" :").strip()
        if index + 1 < len(matches):
            value = value.rstrip(" :").strip()
        results.append((label, value))
    return results


def _table_field_value(rows: list[list[str]], labels: list[str]) -> list[FieldDraft]:
    """Trường hợp nhãn ở một ô, giá trị ở ô kế bên (mẫu dạng bảng)."""
    from records.template import slugify

    label_keys = {slugify(label) for label in labels}
    drafts: list[FieldDraft] = []
    for row in rows:
        for index, cell in enumerate(row):
            if not cell:
                continue
            # K03: chuẩn hoá nhãn ô (bỏ ':' và khoảng trắng cuối) trước khi khớp
            # và trước khi lưu, để tầng store tra đúng alias.
            label = cell.strip().rstrip(":").strip()
            if slugify(label) in label_keys:
                value = ""
                for candidate in row[index + 1 :]:
                    if candidate:
                        value = candidate
                        break
                drafts.append(FieldDraft(label=label, value=value, quote=" | ".join(row)))
                break
    return drafts


def _row_is_header(row: list[str], columns: list[str]) -> bool:
    """Điểm khớp giữa một dòng và bộ cột cấu hình (đã slug)."""
    row_slugs = {_slug(cell) for cell in row if cell}
    column_slugs = {_slug(col) for col in columns if col}
    if not column_slugs:
        return False
    return len(row_slugs & column_slugs) >= max(1, len(column_slugs) // 2)


def _extract_measurements(
    blocks: list[tuple[str, object]], config: MappingConfig
) -> list[MeasurementDraft]:
    measurements: list[MeasurementDraft] = []
    for table in config.result_tables:
        if not table.columns:
            continue
        for kind, payload in blocks:
            if kind != "table":
                continue
            rows: list[list[str]] = payload  # type: ignore[assignment]
            header_index = next(
                (i for i, row in enumerate(rows) if _row_is_header(row, table.columns)),
                None,
            )
            if header_index is None:
                continue
            data_rows = rows[header_index + 1 :]
            # Bỏ dòng header tầng dưới (ô đầu rỗng, ô khác có chữ) ngay sau header.
            if data_rows and data_rows[0] and not data_rows[0][0].strip():
                data_rows = data_rows[1:]
            for row in data_rows:
                cells = list(row) + [""] * (len(table.columns) - len(row))
                cells = cells[: len(table.columns)]
                if not any(cell.strip() for cell in cells):
                    continue
                measurements.append(_map_measurement_row(table.columns, cells))
    return measurements


def read_docx(
    path: str | Path, config: MappingConfig, *, section_path: str | None = None
) -> RecordDraft:
    """Đọc một biên bản Word theo ``config``; trả ``RecordDraft`` giữ nguyên văn."""
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))

    blocks = _iter_blocks(root)
    labels = [item.label for item in config.header_fields]
    fields: list[FieldDraft] = []
    seen: set[str] = set()
    for kind, payload in blocks:
        if kind == "p":
            text = str(payload)
            for label, value in _extract_labeled_fields(text, labels):
                key = _slug(label)
                if key and key not in seen:
                    fields.append(FieldDraft(label=label, value=value, quote=text))
                    seen.add(key)
        else:
            for draft in _table_field_value(payload, labels):  # type: ignore[arg-type]
                key = _slug(draft.label)
                if key and key not in seen:
                    fields.append(draft)
                    seen.add(key)

    source_lines: list[str] = []
    for kind, payload in blocks:
        if kind == "p":
            source_lines.append(str(payload))
        else:
            source_lines.extend(" | ".join(row) for row in payload)  # type: ignore[arg-type]

    return RecordDraft(
        extractor=EXTRACTOR,
        source_text="\n".join(source_lines),
        section_path=section_path or DEFAULT_SECTION_PATH,
        fields=fields,
        measurements=_extract_measurements(blocks, config),
    )
