"""Route tóm tắt tài liệu: xem, sinh lại, sửa (kỹ thuật viên) và phê duyệt / từ chối (người duyệt).

Chat chỉ dùng bản tóm tắt đã được phê duyệt; mọi thao tác ghi đều vào audit_log.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from api.audit import record_audit
from auth import get_current_user, require_role
from db import get_db
from db.models import AppUser, UserRole
from knowledge import doc_summary

router = APIRouter(prefix="/api/documents", tags=["doc-summary"], dependencies=[Depends(get_current_user)])

_editor = require_role(UserRole.TECHNICIAN, UserRole.ADMIN)
_approver = require_role(UserRole.APPROVER, UserRole.ADMIN)


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1, strict=True)


class EditRequest(_Request):
    text: str = Field(min_length=1, max_length=20000)


class DecisionRequest(_Request):
    note: str = Field(default="", max_length=4000)


def _account(user: AppUser) -> AppUser | None:
    return user if isinstance(user, AppUser) else None


def _call(fn, *args):
    try:
        return fn(*args)
    except doc_summary.SummaryError as e:
        raise HTTPException(e.status, str(e)) from e


def _audit(db: Session, user: AppUser, action: str, file_stem: str, result: dict) -> None:
    after = {"status": result["status"], "revision": result["revision"]}
    record_audit(db, user, action, "document_summary", file_stem, after=after)


@router.get("/{file_stem}/summary")
def read_summary(file_stem: str):
    # ``queued``: đang chờ/đang sinh trên luồng nền; dòng "generating" mà không queued là lần sinh bị gián đoạn.
    return {"summary": _call(doc_summary.get, file_stem), "queued": doc_summary.is_queued(file_stem)}


@router.post("/{file_stem}/summary/generate", status_code=202)
def generate_summary(file_stem: str, user: AppUser = Depends(_editor), db: Session = Depends(get_db)):
    _call(doc_summary.check_can_generate, file_stem)
    doc_summary.queue(file_stem, force=True)  # đang sinh thì chạy lại ngay sau lần hiện tại
    record_audit(db, user, "generate", "document_summary", file_stem, after={"status": "queued"})
    return {"status": "queued"}


@router.put("/{file_stem}/summary")
def edit_summary(file_stem: str, req: EditRequest, user: AppUser = Depends(_editor), db: Session = Depends(get_db)):
    result = _call(doc_summary.edit, file_stem, req.revision, req.text, _account(user))
    _audit(db, user, "edit", file_stem, result)
    return {"summary": result}


@router.post("/{file_stem}/summary/approve")
def approve_summary(file_stem: str, req: DecisionRequest, user: AppUser = Depends(_approver), db: Session = Depends(get_db)):
    result = _call(doc_summary.decide, file_stem, req.revision, True, req.note, _account(user))
    _audit(db, user, "approve", file_stem, result)
    return {"summary": result}


@router.post("/{file_stem}/summary/reject")
def reject_summary(file_stem: str, req: DecisionRequest, user: AppUser = Depends(_approver), db: Session = Depends(get_db)):
    result = _call(doc_summary.decide, file_stem, req.revision, False, req.note, _account(user))
    _audit(db, user, "reject", file_stem, result)
    return {"summary": result}
