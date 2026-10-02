"""Route hàng đợi duyệt (Sprint 6): liệt kê, xem, duyệt, từ chối, sửa, audit.

Đây là bề mặt làm việc của người duyệt nên thấy dữ liệu `pending`; mọi bề mặt tra
cứu khác chỉ đọc view đã duyệt ở `query/` (P3). Vai trò approver/admin được ép ở
dependency, trước cả khi chạm DB.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import review.queue as review
from api.errors import review_http_error
from api.schemas import ApproveRequest, BulkApproveRequest, EditApproveRequest, RejectRequest
from auth import require_role
from db import get_db
from db.models import AppUser, ExtractionStatus, UserRole

router = APIRouter()


@router.get("/api/extractions")
def list_extractions(
    document_id: str | None = None,
    fact_kind: str | None = None,
    extractor: str | None = None,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    status: str = "pending",
    limit: int = 50,
    offset: int = 0,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        status_enum = ExtractionStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Trạng thái không hợp lệ: {status}") from None
    items, total = review.list_queue(
        db,
        status=status_enum,
        document_id=document_id,
        fact_kind=fact_kind,
        extractor=extractor,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        limit=max(1, min(limit, 200)),
        offset=max(0, offset),
    )
    return {
        "items": items,
        "total": total,
        "status": status_enum.value,
        "limit": limit,
        "offset": offset,
    }


@router.get("/api/extractions/{extraction_id}")
def get_extraction(
    extraction_id: int,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        return review.get_extraction(db, extraction_id)
    except review.ReviewError as exc:
        raise review_http_error(exc) from exc


@router.post("/api/extractions/{extraction_id}/approve")
def approve_extraction(
    extraction_id: int,
    req: ApproveRequest | None = None,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        return review.approve(db, extraction_id, user, note=req.note if req else None)
    except review.ReviewError as exc:
        raise review_http_error(exc) from exc


@router.post("/api/extractions/{extraction_id}/reject")
def reject_extraction(
    extraction_id: int,
    req: RejectRequest,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        return review.reject(db, extraction_id, user, reason=req.reason)
    except review.ReviewError as exc:
        raise review_http_error(exc) from exc


@router.post("/api/extractions/{extraction_id}/edit")
def edit_extraction(
    extraction_id: int,
    req: EditApproveRequest,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    payload = req.model_dump(exclude_unset=True)
    note = payload.pop("note", None)
    try:
        return review.edit_and_approve(db, extraction_id, user, payload, note=note)
    except review.ReviewError as exc:
        raise review_http_error(exc) from exc


@router.post("/api/extractions/bulk-approve")
def bulk_approve_extractions(
    req: BulkApproveRequest,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        return review.bulk_approve(
            db,
            user,
            extractor=req.extractor,
            section_path=req.section_path,
            document_id=req.document_id,
            note=req.note,
        )
    except review.ReviewError as exc:
        raise review_http_error(exc) from exc


@router.get("/api/extractions/{extraction_id}/audit")
def extraction_audit(
    extraction_id: int,
    user: AppUser = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        review.get_extraction(db, extraction_id)
    except review.ReviewError as exc:
        raise review_http_error(exc) from exc
    return {"entries": review.audit_history(db, extraction_id)}
