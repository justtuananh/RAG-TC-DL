"""Sinh và kiểm cấu hình ánh xạ trường từ Phụ lục A đã duyệt (spec §7, Sprint 7).

Phụ lục A của mỗi QTKĐ chính là mẫu biên bản kiểm định tương ứng. Thay vì
hardcode một bộ đọc cho mỗi mẫu, hệ thống đọc các dữ kiện ``appendix_field`` đã
DUYỆT của QTKĐ rồi dựng cấu hình ánh xạ trường. Thêm một QTKĐ mới kéo theo khả
năng đọc hồ sơ của nó mà không phải viết thêm mã.

Hai ràng buộc:

- **P3**: chỉ đọc dữ kiện đã duyệt — dùng bề mặt ``query/approved`` (đọc
  ``v_procedure_fact``), nên cấu hình không bao giờ dựng từ dữ kiện ``pending``.
- **P1**: mỗi trường giữ ``fact_id`` và ``quote`` để truy nguyên về nguyên văn.

Dữ kiện ``appendix_field`` dùng các cột sẵn có:

- ``label``: tên trường ("Số hiệu") hoặc tiêu đề bảng ("Bảng A.1 - …");
- ``condition_text``: vai trò ``"header"`` (trường đầu mục) hoặc ``"table"``;
- ``value_text``: với header là giá trị mẫu (nếu có); với table là JSON mô tả
  tiêu đề và các cột đã gộp từ header nhiều tầng.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from db.models import FACT_KINDS, Extraction
from query import approved as approved_query

APPENDIX_FACT_KIND = "appendix_field"
ROLE_HEADER = "header"
ROLE_TABLE = "table"

# Đảm bảo loại dữ kiện này được khai báo ở nguồn sự thật (db/models.py).
assert APPENDIX_FACT_KIND in FACT_KINDS


class TemplateError(ValueError):
    """Cấu hình ánh xạ trường không hợp lệ hoặc không dựng được."""


@dataclass(frozen=True)
class HeaderField:
    """Một trường đầu mục của biên bản (nhãn → khóa ổn định)."""

    key: str
    label: str
    fact_id: int
    value_text: str | None = None
    quote: str | None = None

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "fact_id": self.fact_id,
            "value_text": self.value_text,
            "quote": self.quote,
        }


@dataclass(frozen=True)
class ResultTable:
    """Một bảng kết quả đo của biên bản."""

    key: str
    title: str
    columns: list[str]
    fact_id: int
    header_rows: list[list[str]] = field(default_factory=list)
    quote: str | None = None

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "columns": list(self.columns),
            "header_rows": [list(row) for row in self.header_rows],
            "fact_id": self.fact_id,
            "quote": self.quote,
        }


@dataclass(frozen=True)
class MappingConfig:
    """Cấu hình đọc hồ sơ cho một QTKĐ, dựng từ Phụ lục A đã duyệt."""

    procedure_id: int | None
    procedure_number: str | None
    header_fields: list[HeaderField]
    result_tables: list[ResultTable]

    def as_dict(self) -> dict:
        return {
            "procedure_id": self.procedure_id,
            "procedure_number": self.procedure_number,
            "header_fields": [item.as_dict() for item in self.header_fields],
            "result_tables": [item.as_dict() for item in self.result_tables],
        }


_DIACRITICS = re.compile(r"[\u0300-\u036f]")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Chuẩn hóa nhãn tiếng Việt thành khóa ASCII ổn định (``Số hiệu`` → ``so_hieu``)."""
    normalized = unicodedata.normalize("NFD", text or "")
    normalized = _DIACRITICS.sub("", normalized)
    normalized = normalized.replace("đ", "d").replace("Đ", "D").casefold()
    return _NON_ALNUM.sub("_", normalized).strip("_")


def _load_table_value(raw: str | None, label: str) -> tuple[list[str], list[list[str]]]:
    """Giải mã ``value_text`` của một dữ kiện bảng; thô thì coi cả chuỗi là một cột."""
    if not raw:
        return [], []
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return [raw], []
    if isinstance(payload, dict):
        columns = [str(col) for col in payload.get("columns", []) if str(col).strip()]
        rows = [
            [str(cell) for cell in row]
            for row in payload.get("header_rows", [])
            if isinstance(row, list)
        ]
        return columns, rows
    if isinstance(payload, list):
        return [str(col) for col in payload if str(col).strip()], []
    return [str(payload)], []


def _quotes_for(db: Session, rows: list[dict]) -> dict[int | None, str | None]:
    """Nguyên văn (P1) của từng dữ kiện, đọc từ extraction tương ứng."""
    ids = {row.get("extraction_id") for row in rows if row.get("extraction_id")}
    if not ids:
        return {}
    return {
        extraction.id: extraction.quote
        for extraction in db.query(Extraction).filter(Extraction.id.in_(ids)).all()
    }


def derive_mapping_config(
    db: Session,
    *,
    procedure_id: int,
    procedure_number: str | None = None,
) -> MappingConfig:
    """Dựng cấu hình ánh xạ trường từ dữ kiện Phụ lục A ĐÃ DUYỆT của QTKĐ.

    Chỉ đọc ``v_procedure_fact`` (P3). Trả cấu hình đã kiểm; ném ``TemplateError``
    nếu chưa có dữ kiện Phụ lục A nào đã duyệt hoặc cấu hình mâu thuẫn.
    """
    rows = approved_query.list_approved_facts(
        db,
        procedure_id=procedure_id,
        fact_kind=APPENDIX_FACT_KIND,
        limit=1000,
    )
    # Nguyên văn P1 nằm ở extraction; view fact không mang theo cột quote.
    quote_by_extraction = _quotes_for(db, rows)

    header_fields: list[HeaderField] = []
    result_tables: list[ResultTable] = []
    for row in rows:
        label = (row.get("label") or "").strip()
        if not label:
            continue
        role = (row.get("condition_text") or ROLE_HEADER).strip().casefold()
        fact_id = int(row["id"])
        quote = quote_by_extraction.get(row.get("extraction_id"))
        if role == ROLE_TABLE:
            columns, header_rows = _load_table_value(row.get("value_text"), label)
            result_tables.append(
                ResultTable(
                    key=slugify(label) or f"table_{fact_id}",
                    title=label,
                    columns=columns,
                    fact_id=fact_id,
                    header_rows=header_rows,
                    quote=quote,
                )
            )
        else:
            header_fields.append(
                HeaderField(
                    key=slugify(label) or f"field_{fact_id}",
                    label=label,
                    fact_id=fact_id,
                    value_text=row.get("value_text"),
                    quote=quote,
                )
            )

    config = MappingConfig(
        procedure_id=procedure_id,
        procedure_number=procedure_number,
        header_fields=header_fields,
        result_tables=result_tables,
    )
    validate_mapping_config(config)
    return config


def validate_mapping_config(config: MappingConfig) -> None:
    """Kiểm cấu hình: phải có nội dung, khóa không trùng, cột bảng không rỗng."""
    if not config.header_fields and not config.result_tables:
        raise TemplateError(
            "Chưa có dữ kiện Phụ lục A nào đã duyệt để dựng cấu hình đọc hồ sơ."
        )

    seen: set[str] = set()
    for item in config.header_fields:
        if not item.label.strip():
            raise TemplateError("Trường đầu mục thiếu nhãn.")
        if item.key in seen:
            raise TemplateError(f"Khóa trường trùng lặp: {item.key}.")
        seen.add(item.key)

    for table in config.result_tables:
        if not table.title.strip():
            raise TemplateError("Bảng kết quả thiếu tiêu đề.")
        if table.key in seen:
            raise TemplateError(f"Khóa trùng lặp: {table.key}.")
        seen.add(table.key)
        if not table.columns:
            raise TemplateError(f"Bảng '{table.title}' không có cột nào.")
        if any(not column.strip() for column in table.columns):
            raise TemplateError(f"Bảng '{table.title}' có cột rỗng.")


def load_mapping_config(
    db: Session, *, procedure_id: int, procedure_number: str | None = None
) -> MappingConfig:
    """Bí danh tường minh cho ``derive_mapping_config`` (đường đọc chính)."""
    return derive_mapping_config(
        db, procedure_id=procedure_id, procedure_number=procedure_number
    )
