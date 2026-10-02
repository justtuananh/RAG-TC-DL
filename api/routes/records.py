"""Route hồ sơ kiểm định (Sprint 7): nạp hồ sơ và liệt kê hồ sơ đã duyệt.

Nạp hồ sơ là thao tác ghi (technician/admin) và đi qua hàng đợi duyệt: dữ liệu
đo mới luôn `pending`. Bề mặt đọc chỉ trả hồ sơ đã duyệt qua view (P3).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.audit import record_audit
from api.schemas import IngestRecordRequest
from auth import require_role
from db import get_db
from db.models import AppUser, UserRole
from ingestion import jobs as ingestion_jobs

router = APIRouter()


@router.post("/api/records/ingest/{file_stem}")
def ingest_record(
    file_stem: str,
    req: IngestRecordRequest | None = None,
    user: AppUser = Depends(require_role(UserRole.TECHNICIAN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    from db.models import Document, Procedure
    from records.ingest import IngestError, ingest_record_path

    document = db.query(Document).filter(Document.file_stem == file_stem).one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")
    source_path = ingestion_jobs.get_source_path(file_stem)
    if source_path is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp gốc của tài liệu.")

    procedure = None
    if req is not None and req.procedure_id is not None:
        procedure = db.get(Procedure, req.procedure_id)
        if procedure is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy QTKĐ.")

    try:
        result = ingest_record_path(
            db, document=document, source_path=source_path, procedure=procedure
        )
        db.commit()
    except IngestError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    record_audit(db, user, "ingest_record", "document", file_stem, after=result.as_dict())
    return result.as_dict()


@router.get("/api/records")
def list_records(
    procedure_id: int | None = None,
    device_id: int | None = None,
    limit: int = 200,
    offset: int = 0,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Hồ sơ kiểm định ĐÃ DUYỆT (đọc ``v_calibration_record``, P3)."""
    from query import approved as approved_query

    records = approved_query.list_approved_records(
        db, procedure_id=procedure_id, device_id=device_id, limit=limit, offset=offset
    )
    return {"records": records, "total": len(records)}
