"""Route "Tài liệu phê duyệt": bản cứng (PDF scan / ảnh) đính kèm một tài liệu, chỉ để xem.

Không trích xuất, không nhúng, chatbot không đọc. Ai đăng nhập cũng xem được;
kỹ thuật viên / người duyệt / quản trị tải lên và xoá, mọi thao tác ghi vào audit_log.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.audit import record_audit
from auth import get_current_user, require_role
from db import get_db
from db.models import AppUser, UserRole
from ingestion import jobs as ingestion_jobs
from knowledge import approval_copies

router = APIRouter(prefix="/api/documents", tags=["approval-copies"], dependencies=[Depends(get_current_user)])

_uploader = require_role(UserRole.TECHNICIAN, UserRole.APPROVER, UserRole.ADMIN)
_ENTITY = "approval_copy"


def _require_document(file_stem: str) -> None:
    if ingestion_jobs.get_source_path(file_stem) is None:
        raise HTTPException(404, "Không tìm thấy tài liệu.")


def _call(fn, *args):
    try:
        return fn(*args)
    except approval_copies.ApprovalCopyError as e:
        raise HTTPException(e.status, str(e)) from e


@router.get("/{file_stem}/approval-copies")
def list_approval_copies(file_stem: str):
    _require_document(file_stem)
    return {"copies": [asdict(c) for c in _call(approval_copies.list_copies, file_stem)]}


@router.post("/{file_stem}/approval-copies", status_code=201)
async def upload_approval_copy(
    file_stem: str,
    file: UploadFile = File(...),
    user: AppUser = Depends(_uploader),
    db: Session = Depends(get_db),
):
    _require_document(file_stem)
    data = await file.read()
    uploader = user.username if isinstance(user, AppUser) else None
    copy = _call(approval_copies.save_copy, file_stem, file.filename or "", data, uploader)
    record_audit(db, user, "upload", _ENTITY, f"{file_stem}/{copy.id}", after={"name": copy.name, "size": copy.size})
    return asdict(copy)


@router.get("/{file_stem}/approval-copies/{copy_id}/file")
def approval_copy_file(file_stem: str, copy_id: str):
    meta, path = _call(approval_copies.get_copy, file_stem, copy_id)
    return FileResponse(path, media_type=meta.media_type, filename=meta.name, content_disposition_type="inline")


@router.delete("/{file_stem}/approval-copies/{copy_id}", status_code=204)
def delete_approval_copy(
    file_stem: str,
    copy_id: str,
    user: AppUser = Depends(_uploader),
    db: Session = Depends(get_db),
):
    meta = _call(approval_copies.delete_copy, file_stem, copy_id)
    record_audit(db, user, "delete", _ENTITY, f"{file_stem}/{copy_id}", before={"name": meta.name, "size": meta.size})
