"""Hàng đợi duyệt — nơi người duyệt làm việc (spec §9, Sprint 6).

Đây là BỀ MẶT LÀM VIỆC CỦA NGƯỜI DUYỆT, không phải bề mặt tra cứu: nó phải thấy
dữ liệu ``pending`` để duyệt, nên đọc bảng gốc một cách có chủ đích. Mọi bề mặt
tra cứu khác chỉ đọc view đã duyệt ở ``query/`` (P3, spec §5.7).

Ba bất biến được giữ ở đây:

- **P1**: không bao giờ sửa ``quote``/``char_start``/``char_end``/``section_path``.
  Sửa giá trị rồi duyệt chỉ đụng bảng dữ kiện, còn nguyên văn nguồn bất động.
- **P3**: chỉ extraction ``pending`` mới duyệt/từ chối/sửa được; view đã duyệt
  tự lộ ra khi status chuyển ``approved`` và tự ẩn khi chuyển ``rejected``.
- **Audit**: mọi thao tác ghi một dòng ``audit_log`` kèm ``before``/``after``
  để lịch sử trả lời được "ai, khi nào, sửa từ giá trị nào sang giá trị nào".

Không đụng FastAPI: các hàm thuần DB, dễ test đơn.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from db.models import (
    AppUser,
    AuditLog,
    Document,
    Extraction,
    ExtractionStatus,
    ProcedureFact,
    ProcedureStandard,
    Term,
)

ENTITY_TYPE = "extraction"

# Trường được phép sửa khi "sửa giá trị rồi duyệt". Mọi trường khác bị từ chối
# để một payload lạ không âm thầm đổi dữ liệu ngoài phạm vi duyệt.
EDITABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "fact": ("label", "rel_op", "value_min", "value_max", "unit_id", "value_text", "condition_text"),
    "standard": ("name_vi", "range_text", "accuracy_text", "note"),
    "term": ("term_vi", "term_en", "definition"),
}

# Trường hiển thị trong response/audit — rộng hơn tập được sửa để UI thấy được
# ``fact_kind``/``ord``… dù chúng không đổi qua đường "sửa giá trị".
_DISPLAY_FIELDS: dict[str, tuple[str, ...]] = {
    "fact": (
        "fact_kind",
        "label",
        "rel_op",
        "value_min",
        "value_max",
        "unit_id",
        "value_text",
        "condition_text",
    ),
    "standard": ("ord", "name_vi", "range_text", "accuracy_text", "note"),
    "term": ("term_vi", "term_en", "definition"),
}


class ReviewError(Exception):
    """Lỗi nghiệp vụ của hàng đợi duyệt (được API ánh xạ sang HTTP)."""


class NotFoundError(ReviewError):
    """Không tìm thấy extraction."""


class ConflictError(ReviewError):
    """Extraction không còn ở trạng thái ``pending``."""


class ValidationError(ReviewError):
    """Payload không hợp lệ (thiếu lý do từ chối, sửa trường không cho phép…)."""


def _now() -> datetime:
    return datetime.utcnow()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _status_value(status: ExtractionStatus | str) -> str:
    return status.value if isinstance(status, ExtractionStatus) else str(status)


def _persisted(actor: Any) -> bool:
    return isinstance(actor, AppUser)


def _actor_id(actor: Any) -> int | None:
    return actor.id if _persisted(actor) else None


def _log(
    db: Session,
    actor: Any,
    action: str,
    extraction_id: int,
    before: dict | None,
    after: dict | None,
) -> None:
    """Ghi audit trong cùng transaction; bỏ qua actor không phải bản ghi thật.

    Chế độ dev tắt xác thực trả về mock user không có hàng ``app_user``; ghi audit
    cho nó sẽ vi phạm khóa ngoại, nên chỉ ghi khi actor là ``AppUser`` thật.
    """
    if not _persisted(actor):
        return
    db.add(
        AuditLog(
            actor_id=actor.id,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=str(extraction_id),
            before=before,
            after=after,
        )
    )


def _data_row(db: Session, extraction: Extraction) -> tuple[str | None, Any]:
    """Trả ``(kind, row)`` của dòng dữ kiện gắn với extraction (fact/standard/term)."""
    fact = (
        db.query(ProcedureFact)
        .filter(ProcedureFact.extraction_id == extraction.id)
        .first()
    )
    if fact is not None:
        return "fact", fact
    standard = (
        db.query(ProcedureStandard)
        .filter(ProcedureStandard.extraction_id == extraction.id)
        .first()
    )
    if standard is not None:
        return "standard", standard
    term = db.query(Term).filter(Term.extraction_id == extraction.id).first()
    if term is not None:
        return "term", term
    return None, None


def _data_snapshot(kind: str | None, row: Any) -> dict | None:
    """Ảnh chụp dòng dữ kiện để hiển thị/audit.

    Gồm cả trường chỉ-để-hiển thị (``fact_kind``, ``name_vi``…) lẫn trường được
    sửa; ``EDITABLE_FIELDS`` vẫn là nguồn sự thật duy nhất cho phép sửa gì.
    """
    if row is None or kind is None:
        return None
    return {field: getattr(row, field) for field in _DISPLAY_FIELDS[kind]}


def build_source_view(file_stem: str | None, extraction: Extraction) -> dict:
    """Dựng nguồn nguyên văn an toàn để tô sáng (P1).

    Ủy nhiệm cho ``query.source.build_source_view`` để bề mặt duyệt và bề mặt tra
    cứu dùng chung đúng một cách dựng nguồn — P1 chỉ có một cài đặt.
    """
    from query.source import build_source_view as _build

    return _build(
        file_stem=file_stem,
        section_path=extraction.section_path,
        quote=extraction.quote,
        char_start=extraction.char_start,
        char_end=extraction.char_end,
        chunk_id=extraction.chunk_id,
    )


def serialize(db: Session, extraction: Extraction, *, with_source: bool = False) -> dict:
    """Chuyển một extraction + dòng dữ kiện thành dict cho API/UI."""
    kind, row = _data_row(db, extraction)
    document = (
        db.query(Document).filter(Document.id == extraction.document_id).one_or_none()
    )
    file_stem = document.file_stem if document is not None else extraction.document_id
    item: dict[str, Any] = {
        "id": extraction.id,
        "document_id": extraction.document_id,
        "file_stem": file_stem,
        "display_name": document.display_name if document is not None else None,
        "section_path": extraction.section_path,
        "chunk_id": extraction.chunk_id,
        "quote": extraction.quote,
        "char_start": extraction.char_start,
        "char_end": extraction.char_end,
        "extractor": extraction.extractor,
        "extractor_version": extraction.extractor_version,
        "confidence": extraction.confidence,
        "status": _status_value(extraction.status),
        "reviewed_by": extraction.reviewed_by,
        "reviewed_at": _iso(extraction.reviewed_at),
        "review_note": extraction.review_note,
        "created_at": _iso(extraction.created_at),
        "kind": kind,
        "data": _data_snapshot(kind, row),
    }
    if with_source:
        item["source"] = build_source_view(file_stem, extraction)
    return item


def list_queue(
    db: Session,
    *,
    status: ExtractionStatus | str = ExtractionStatus.PENDING,
    document_id: str | None = None,
    fact_kind: str | None = None,
    extractor: str | None = None,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Liệt kê extraction theo bộ lọc; mặc định chỉ ``pending`` (spec §9 S6).

    Sắp xếp theo ``confidence`` tăng dần để người duyệt gặp dòng khó trước khi
    mệt (spec §12). Lọc ``fact_kind`` chỉ áp cho dòng ``procedure_fact`` nên nó
    loại luôn standard/term khỏi kết quả.
    """
    query = db.query(Extraction)
    if status is not None:
        query = query.filter(Extraction.status == ExtractionStatus(status))
    if document_id:
        query = query.filter(Extraction.document_id == document_id)
    if extractor:
        query = query.filter(Extraction.extractor == extractor)
    if min_confidence is not None:
        query = query.filter(Extraction.confidence >= min_confidence)
    if max_confidence is not None:
        query = query.filter(Extraction.confidence <= max_confidence)
    if fact_kind:
        # Dùng subquery thay vì join: một extraction §6 có thể có HAI dòng
        # procedure_fact cùng fact_kind (giới hạn + giá trị sàn), join sẽ nhân
        # đôi kết quả và làm sai `total`.
        matching = db.query(ProcedureFact.extraction_id).filter(
            ProcedureFact.fact_kind == fact_kind
        )
        query = query.filter(Extraction.id.in_(matching))

    total = query.count()
    rows = (
        query.order_by(Extraction.confidence.asc(), Extraction.id.asc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [serialize(db, row) for row in rows], total


def get_extraction(db: Session, extraction_id: int) -> dict:
    """Chi tiết một extraction kèm nguồn nguyên văn để tô sáng; 404 nếu không có."""
    extraction = db.get(Extraction, extraction_id)
    if extraction is None:
        raise NotFoundError(f"Không tìm thấy extraction {extraction_id}.")
    return serialize(db, extraction, with_source=True)


def _require_pending(extraction: Extraction) -> None:
    if extraction.status != ExtractionStatus.PENDING:
        raise ConflictError(
            f"Extraction {extraction.id} đang ở trạng thái '{_status_value(extraction.status)}'."
        )


def _set_approved(
    db: Session, extraction: Extraction, actor: Any, note: str | None, *, bulk: bool
) -> None:
    before = {"status": _status_value(extraction.status)}
    extraction.status = ExtractionStatus.APPROVED
    extraction.reviewed_by = _actor_id(actor)
    extraction.reviewed_at = _now()
    extraction.review_note = note
    after: dict[str, Any] = {"status": ExtractionStatus.APPROVED.value, "note": note}
    if bulk:
        after["bulk"] = True
        after["extractor"] = extraction.extractor
    _log(db, actor, "approve", extraction.id, before, after)


def approve(db: Session, extraction_id: int, actor: Any, note: str | None = None) -> dict:
    """Duyệt một extraction đang ``pending``; ghi audit và trả bản đã cập nhật."""
    extraction = db.get(Extraction, extraction_id)
    if extraction is None:
        raise NotFoundError(f"Không tìm thấy extraction {extraction_id}.")
    _require_pending(extraction)
    _set_approved(db, extraction, actor, note, bulk=False)
    db.commit()
    return serialize(db, extraction)


def reject(db: Session, extraction_id: int, actor: Any, reason: str) -> dict:
    """Từ chối kèm lý do bắt buộc; lý do lưu ở ``review_note`` và audit."""
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Từ chối phải kèm lý do.")
    extraction = db.get(Extraction, extraction_id)
    if extraction is None:
        raise NotFoundError(f"Không tìm thấy extraction {extraction_id}.")
    _require_pending(extraction)

    before = {"status": _status_value(extraction.status)}
    extraction.status = ExtractionStatus.REJECTED
    extraction.reviewed_by = _actor_id(actor)
    extraction.reviewed_at = _now()
    extraction.review_note = reason
    _log(
        db,
        actor,
        "reject",
        extraction.id,
        before,
        {"status": ExtractionStatus.REJECTED.value, "reason": reason},
    )
    db.commit()
    return serialize(db, extraction)


def edit_and_approve(
    db: Session,
    extraction_id: int,
    actor: Any,
    edits: dict,
    note: str | None = None,
) -> dict:
    """Sửa giá trị dữ kiện rồi duyệt; nguyên văn nguồn (P1) bất động.

    ``edits`` chỉ chứa các trường người dùng thực sự gửi (kể cả giá trị ``None``
    để xoá trắng). Trường ngoài danh sách cho phép bị từ chối. Audit ghi cả giá
    trị cũ lẫn mới để hiển thị "sửa từ … sang …".
    """
    extraction = db.get(Extraction, extraction_id)
    if extraction is None:
        raise NotFoundError(f"Không tìm thấy extraction {extraction_id}.")
    _require_pending(extraction)

    kind, row = _data_row(db, extraction)
    if row is None or kind is None:
        raise ValidationError("Extraction không có dòng dữ kiện để sửa.")

    allowed = EDITABLE_FIELDS[kind]
    unknown = sorted(set(edits) - set(allowed))
    if unknown:
        raise ValidationError(f"Trường không được phép sửa: {', '.join(unknown)}.")
    if not edits:
        raise ValidationError("Không có trường nào được sửa.")

    before_data = _data_snapshot(kind, row)
    for field, value in edits.items():
        setattr(row, field, value)
    after_data = _data_snapshot(kind, row)

    before = {"status": _status_value(extraction.status), "data": before_data}
    extraction.status = ExtractionStatus.APPROVED
    extraction.reviewed_by = _actor_id(actor)
    extraction.reviewed_at = _now()
    extraction.review_note = note
    after = {
        "status": ExtractionStatus.APPROVED.value,
        "data": after_data,
        "note": note,
    }
    _log(db, actor, "edit_approve", extraction.id, before, after)
    db.commit()
    return serialize(db, extraction)


def bulk_approve(
    db: Session,
    actor: Any,
    *,
    extractor: str,
    section_path: str | None = None,
    document_id: str | None = None,
    note: str | None = None,
) -> dict:
    """Duyệt hàng loạt mọi dòng ``pending`` cùng một luật (``extractor``).

    ``section_path``/``document_id`` thu hẹp phạm vi. Ghi một dòng audit cho mỗi
    extraction để lịch sử từng dòng vẫn đầy đủ, tất cả trong một transaction.
    """
    extractor = (extractor or "").strip()
    if not extractor:
        raise ValidationError("Duyệt hàng loạt phải chỉ rõ luật (extractor).")

    query = db.query(Extraction).filter(
        Extraction.status == ExtractionStatus.PENDING,
        Extraction.extractor == extractor,
    )
    if section_path is not None:
        query = query.filter(Extraction.section_path == section_path)
    if document_id:
        query = query.filter(Extraction.document_id == document_id)

    rows = query.order_by(Extraction.id).all()
    ids: list[int] = []
    for row in rows:
        _set_approved(db, row, actor, note, bulk=True)
        ids.append(row.id)
    db.commit()
    return {"approved_count": len(ids), "ids": ids, "extractor": extractor}


def audit_history(db: Session, extraction_id: int) -> list[dict]:
    """Lịch sử duyệt của một extraction, cũ → mới, kèm tên người thao tác."""
    rows = (
        db.query(AuditLog, AppUser.username)
        .outerjoin(AppUser, AppUser.id == AuditLog.actor_id)
        .filter(
            AuditLog.entity_type == ENTITY_TYPE,
            AuditLog.entity_id == str(extraction_id),
        )
        .order_by(AuditLog.at.asc(), AuditLog.id.asc())
        .all()
    )
    return [
        {
            "id": log.id,
            "actor_id": log.actor_id,
            "actor_username": username,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "before": log.before,
            "after": log.after,
            "at": _iso(log.at),
        }
        for log, username in rows
    ]
