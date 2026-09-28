"""Điểm vào đọc hồ sơ danh mục NAS: nhận loại theo TIÊU ĐỀ CỘT, không theo tên tệp.

``read_catalog(path)`` nhận bản ``.docx``/``.xlsx`` (đã chuyển từ ``.doc``/``.xls``
nếu cần) và trả ``CatalogDraft``. Không có bảng nào khớp một loại danh mục đã biết
thì ném ``CatalogError`` (không đoán).
"""

from __future__ import annotations

import re
from pathlib import Path

from catalogs import parse_catalog, parse_people, parse_standards
from catalogs.rows import slug
from catalogs.tables import Block, Row, cell_text, load_blocks, row_quote
from catalogs.types import CatalogDraft

# Loại danh mục → các từ khóa (slug) PHẢI cùng có mặt trong một dòng tiêu đề.
_SIGNATURES: dict[str, tuple[str, ...]] = {
    "lab_standard": ("ten_chuan_mau", "chu_ky"),
    "inspector": ("ho_va_ten", "so_the"),
    "procedure_catalog": ("so_hieu_tieu_chuan", "ten_tieu_chuan"),
    "capability": ("ten_dai_luong", "tham_so_do_luong"),
}
_DOMAIN_RE = re.compile(r"^[IVXLC]+\.\s+\S")
_HEADER_SEARCH_ROWS = 5


class CatalogError(ValueError):
    """Tệp không chứa bảng danh mục NAS nhận dạng được."""


def _header_kind(row: Row) -> str | None:
    joined = "_".join(slug(cell_text(cell)) for cell in row)
    return next(
        (kind for kind, keys in _SIGNATURES.items() if all(key in joined for key in keys)), None
    )


def _locate(blocks: list[Block]) -> tuple[int, int, str]:
    for block_index, block in enumerate(blocks):
        for row_index, row in enumerate((block.rows or [])[:_HEADER_SEARCH_ROWS]):
            kind = _header_kind(row)
            if kind:
                return block_index, row_index, kind
    raise CatalogError(
        "Không tìm thấy bảng danh mục NAS (chuẩn mẫu, KĐV, danh mục quy trình, lĩnh vực)."
    )


def _source_text(blocks: list[Block]) -> str:
    lines: list[str] = []
    for block in blocks:
        lines.extend(
            [block.text] if block.kind == "p" else [row_quote(row) for row in block.rows or []]
        )
    return "\n".join(line for line in lines if line.strip(" |/"))


def read_catalog(path: str | Path) -> CatalogDraft:
    blocks = load_blocks(path)
    block_index, header_index, kind = _locate(blocks)
    rows = blocks[block_index].rows or []
    header, body = rows[header_index], rows[header_index + 1 :]
    paragraphs = [block.text for block in blocks[:block_index] if block.kind == "p"]
    warnings: list[str] = []
    if kind == "lab_standard":
        items = parse_standards.parse(body, header, warnings)
    elif kind == "inspector":
        items = parse_people.parse(body, header, warnings)
    elif kind == "procedure_catalog":
        domain = next((text for text in reversed(paragraphs) if _DOMAIN_RE.match(text)), None)
        items = parse_catalog.parse_procedures(body, header, domain)
    else:
        items = parse_catalog.parse_capabilities(body, header)
    return CatalogDraft(
        kind=kind,
        title=paragraphs[0] if paragraphs else None,
        items=items,
        source_text=_source_text(blocks),
        warnings=warnings,
    )
