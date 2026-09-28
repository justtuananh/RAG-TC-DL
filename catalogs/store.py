"""Ghi một ``CatalogDraft`` vào sổ cái ở trạng thái ``pending`` (Pha D1).

Cầu nối giữa bộ đọc thuần dữ liệu (``catalogs.readers``) và DB:

- mỗi lần đọc sinh MỘT ``extraction`` (``extractor = catalog:<kind>.v1``) mang
  toàn bộ dòng; ``quote`` là nguyên văn cả tài liệu đã đọc (P1);
- ``supersede`` chuyển mọi extraction ``catalog:*`` cũ của cùng tài liệu sang
  ``superseded`` chứ không xóa (lịch sử duyệt là dữ liệu nghiệp vụ);
- hạn KĐ/HC kế tiếp của chuẩn mẫu là giá trị DẪN XUẤT duy nhất được phép tính
  (lần KĐ/HC gần nhất + chu kỳ), luôn đi kèm cờ ``next_due_derived`` (P2).

Không commit trong đây; tầng gọi quyết định.
"""

from __future__ import annotations

from dataclasses import asdict

from db.models import (
    Capability,
    Extraction,
    ExtractionStatus,
    Inspector,
    LabStandard,
    ProcedureCatalog,
)
from catalogs.labels import CATALOG_EXTRACTOR_PREFIX, extractor_for, label_for
from catalogs.text import fold as _fold

EXTRACTOR_VERSION = "v1"
# Chỉ hai trạng thái này bị thay khi đọc lại; bản đã từ chối giữ nguyên.
_SUPERSEDE_STATUSES = (ExtractionStatus.PENDING, ExtractionStatus.APPROVED)

_KIND_MODELS = {
    "lab_standard": LabStandard,
    "inspector": Inspector,
    "procedure_catalog": ProcedureCatalog,
    "capability": Capability,
}


def _next_due(
    last_year: int | None, last_month: int | None, interval_months: int | None
) -> tuple[int, int] | None:
    """Hạn kế tiếp = lần KĐ/HC gần nhất + chu kỳ; None khi thiếu bất kỳ phần nào."""
    if not last_year or not last_month or not interval_months:
        return None
    total = last_year * 12 + (last_month - 1) + interval_months
    return total // 12, total % 12 + 1


def _lab_standard_values(item) -> dict:
    due = _next_due(item.last_cal_year, item.last_cal_month, item.interval_months)
    return {
        "ord": item.ord,
        "quote": item.quote,
        "name": item.name,
        "model": item.model,
        "serial": item.serial,
        "characteristics": item.characteristics,
        "interval_text": item.interval_text,
        "interval_months": item.interval_months,
        "last_cal_text": item.last_cal_text,
        "last_cal_year": item.last_cal_year,
        "last_cal_month": item.last_cal_month,
        "last_cal_place": item.last_cal_place,
        "usage_text": item.usage_text,
        "usage_refs": [list(ref) for ref in item.usage_refs],
        "inherited": list(item.inherited),
        "next_due_year": due[0] if due else None,
        "next_due_month": due[1] if due else None,
        "next_due_derived": 1 if due else 0,
        "search_text": _fold(
            " ".join(
                part or ""
                for part in (
                    item.name,
                    item.model,
                    item.serial,
                    item.characteristics,
                    item.interval_text,
                    item.usage_text,
                )
            )
        ),
    }


def _inspector_values(item) -> dict:
    return {
        "ord": item.ord,
        "quote": item.quote,
        "name": item.name,
        "birth_year": item.birth_year,
        "rank": item.rank,
        "position": item.position,
        "education": item.education,
        "specialization": item.specialization,
        "fields": list(item.fields),
        "card_no": item.card_no,
        "card_date": item.card_date,
        "search_text": _fold(
            " ".join(
                part or ""
                for part in (
                    item.name,
                    item.rank,
                    item.position,
                    item.education,
                    item.specialization,
                    " ".join(item.fields),
                    item.card_no,
                )
            )
        ),
    }


def _procedure_catalog_values(item) -> dict:
    return {
        "ord": item.ord,
        "quote": item.quote,
        "domain": item.domain,
        "group_code": item.group_code,
        "group_title": item.group_title,
        "code_text": item.code_text,
        "codes": [asdict(code) for code in item.codes],
        "title": item.title,
        "issuer": item.issuer,
        "year_issued": item.year_issued,
        "inherited": list(item.inherited),
        "procedure_number": item.procedure_number,
        "search_text": _fold(
            " ".join(
                part or ""
                for part in (
                    item.code_text,
                    item.title,
                    item.issuer,
                    item.domain,
                    item.group_title,
                    item.group_code,
                )
            )
        ),
    }


def _capability_values(item) -> dict:
    return {
        "ord": item.ord,
        "quote": item.quote,
        "group_code": item.group_code,
        "group_title": item.group_title,
        "name": item.name,
        "parameters": list(item.parameters),
        "procedure_codes": [asdict(code) for code in item.procedure_codes],
        "inspector_count": item.inspector_count,
        "recognition": item.recognition,
        "search_text": _fold(
            " ".join(
                part or ""
                for part in (
                    item.name,
                    item.group_title,
                    item.group_code,
                    " ".join(item.parameters),
                    " ".join(code.normalized for code in item.procedure_codes),
                )
            )
        ),
    }


_VALUE_BUILDERS = {
    "lab_standard": _lab_standard_values,
    "inspector": _inspector_values,
    "procedure_catalog": _procedure_catalog_values,
    "capability": _capability_values,
}


def _supersede_catalog(session, document) -> tuple[int, int | None]:
    """Chuyển extraction ``catalog:*`` cũ của tài liệu sang ``superseded``.

    Trả ``(số dòng đã chuyển, id bản cũ mới nhất)`` để bản mới có thể trỏ tới.
    """
    rows = (
        session.query(Extraction)
        .filter(
            Extraction.document_id == document.id,
            Extraction.status.in_(_SUPERSEDE_STATUSES),
            Extraction.extractor.like(f"{CATALOG_EXTRACTOR_PREFIX}%"),
        )
        .order_by(Extraction.id)
        .all()
    )
    for row in rows:
        row.status = ExtractionStatus.SUPERSEDED
    return len(rows), (rows[-1].id if rows else None)


def store_catalog_draft(
    session, *, document, draft, supersede: bool = True
) -> dict:
    """Ghi toàn bộ dòng của ``draft`` thành một extraction ``pending``; không commit.

    Trả tổng kết ``{kind, label, rows, extraction_id, superseded, warnings}``.
    Draft rỗng thì không tạo extraction và không supersede gì.
    """
    model = _KIND_MODELS.get(draft.kind)
    build = _VALUE_BUILDERS.get(draft.kind)
    if model is None or build is None:
        raise ValueError(f"Loại danh mục không hỗ trợ: {draft.kind!r}.")
    summary = {
        "kind": draft.kind,
        "label": label_for(draft.kind),
        "rows": 0,
        "extraction_id": None,
        "superseded": 0,
        "warnings": list(draft.warnings),
    }
    if not draft.items:
        return summary

    superseded, previous_id = (0, None)
    if supersede:
        superseded, previous_id = _supersede_catalog(session, document)

    extraction = Extraction(
        document_id=document.id,
        section_path=draft.title,
        quote=draft.source_text,
        extractor=extractor_for(draft.kind),
        extractor_version=EXTRACTOR_VERSION,
        confidence=1.0,
        status=ExtractionStatus.PENDING,
        supersedes_id=previous_id,
    )
    session.add(extraction)
    session.flush()

    for item in draft.items:
        session.add(
            model(document_id=document.id, extraction_id=extraction.id, **build(item))
        )
    session.flush()

    summary["rows"] = len(draft.items)
    summary["extraction_id"] = extraction.id
    summary["superseded"] = superseded
    return summary
