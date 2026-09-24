"""Xuất xứ từng ô số (P1) — mỗi con số mở ra đúng tài liệu, mục, chunk, trích dẫn.

Bề mặt tra cứu trả về con số kèm *tham chiếu* (``extraction_id``/``fact_id``/
``measurement_id``); khi người dùng bấm vào ô số, tầng này dựng nguồn nguyên văn
để đối chiếu. Tuyệt đối không đọc bảng gốc: chỉ ``v_extraction``,
``v_record_detail``, ``v_measurement_detail`` và ``v_procedure_fact`` (P3).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from query.source import build_source_view


class ProvenanceError(ValueError):
    """Không dựng được xuất xứ (tham chiếu sai/không còn được duyệt)."""


# Ô số → cột nguyên văn tương ứng trong ``v_measurement_detail``.
CELL_TEXT_COLUMNS: dict[str, str] = {
    "nominal": "nominal_text",
    "measured": "measured_text",
    "error": "error_text",
    "limit": "limit_text",
}


def _extraction(session: Session, extraction_id: int) -> Any:
    row = (
        session.execute(text("SELECT * FROM v_extraction WHERE id = :id"), {"id": extraction_id})
        .mappings()
        .first()
    )
    if row is None:
        raise ProvenanceError(f"Không tìm thấy xuất xứ cho extraction {extraction_id}.")
    return row


def _source(
    session: Session,
    extraction_id: int,
    *,
    kind: str,
    field: str | None = None,
    quote: str | None = None,
    value_text: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dựng nguồn nguyên văn kèm vị trí tô sáng, từ một extraction ĐÃ DUYỆT."""
    row = _extraction(session, extraction_id)
    source = build_source_view(
        file_stem=row["file_stem"],
        section_path=row["section_path"],
        quote=quote or row["quote"],
        char_start=row["char_start"],
        char_end=row["char_end"],
        chunk_id=row["chunk_id"],
    )
    payload: dict[str, Any] = {
        "kind": kind,
        "field": field,
        "document_id": row["document_id"],
        "file_stem": row["file_stem"],
        "display_name": row["display_name"],
        "extractor": row["extractor"],
        "extractor_version": row["extractor_version"],
        "confidence": row["confidence"],
        "value_text": value_text,
        "source_quote": row["quote"],
    }
    payload.update(source)
    if extra:
        payload.update(extra)
    return payload


def record_provenance(session: Session, record_id: int) -> dict[str, Any]:
    """Xuất xứ của một hồ sơ (các ô đầu mục: ngày, nhiệt độ, độ ẩm…)."""
    row = (
        session.execute(
            text("SELECT id, extraction_id FROM v_record_detail WHERE id = :id"),
            {"id": record_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ProvenanceError(f"Không tìm thấy hồ sơ đã duyệt {record_id}.")
    return _source(
        session,
        row["extraction_id"],
        kind="record",
        extra={"record_id": record_id},
    )


def extraction_provenance(session: Session, extraction_id: int) -> dict[str, Any]:
    """Xuất xứ trực tiếp theo ``extraction_id`` (đã duyệt)."""
    return _source(session, extraction_id, kind="extraction")


def fact_provenance(session: Session, fact_id: int) -> dict[str, Any]:
    """Xuất xứ của một dữ kiện QTKĐ đã duyệt (phạm vi đo, cấp chính xác…)."""
    fact = (
        session.execute(text("SELECT * FROM v_procedure_fact WHERE id = :id"), {"id": fact_id})
        .mappings()
        .first()
    )
    if fact is None:
        raise ProvenanceError(f"Không tìm thấy dữ kiện đã duyệt {fact_id}.")
    return _source(
        session,
        fact["extraction_id"],
        kind="fact",
        field=fact.get("fact_kind"),
        quote=fact.get("value_text"),
        value_text=fact.get("value_text"),
        extra={"fact_id": fact_id, "procedure_id": fact.get("procedure_id")},
    )


def measurement_provenance(
    session: Session, measurement_id: int, field: str | None = None
) -> dict[str, Any]:
    """Xuất xứ một ô số liệu đo; ``field`` chọn đúng ô (nominal/measured/error/limit)."""
    point = (
        session.execute(
            text("SELECT * FROM v_measurement_detail WHERE id = :id"),
            {"id": measurement_id},
        )
        .mappings()
        .first()
    )
    if point is None:
        raise ProvenanceError(f"Không tìm thấy số liệu đo đã duyệt {measurement_id}.")
    cell = None
    if field and field in CELL_TEXT_COLUMNS:
        cell = point[CELL_TEXT_COLUMNS[field]]
    if cell is None:
        cell = point["quote"]
    return _source(
        session,
        point["extraction_id"],
        kind="measurement",
        field=field,
        quote=cell,
        value_text=cell,
        extra={
            "measurement_id": measurement_id,
            "record_id": point["record_id"],
            "step_code": point["step_code"],
            "label": point["label"],
            "point_quote": point["quote"],
        },
    )


def resolve(
    session: Session,
    *,
    extraction_id: int | None = None,
    record_id: int | None = None,
    fact_id: int | None = None,
    measurement_id: int | None = None,
    field: str | None = None,
) -> dict[str, Any]:
    """Phân giải một tham chiếu xuất xứ bất kỳ; ưu tiên tham chiếu cụ thể nhất."""
    if measurement_id is not None:
        return measurement_provenance(session, measurement_id, field)
    if fact_id is not None:
        return fact_provenance(session, fact_id)
    if record_id is not None:
        return record_provenance(session, record_id)
    if extraction_id is not None:
        return extraction_provenance(session, extraction_id)
    raise ProvenanceError("Cần ít nhất một tham chiếu xuất xứ.")
