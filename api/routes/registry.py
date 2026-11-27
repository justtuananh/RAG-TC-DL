"""Route sổ đăng ký danh mục 877: nạp file danh mục (bản nháp), xem báo cáo lỗi, duyệt / từ chối.

Kỹ thuật viên / quản trị nạp và xoá bản nháp; người duyệt / quản trị phê duyệt. Chat chỉ dùng bản đã
duyệt mới nhất mỗi loại. Mọi thao tác ghi vào audit_log.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from api.audit import record_audit
from auth import get_current_user, require_role
from core.settings_loader import get_settings
from db import get_db
from db.models import AppUser, UserRole
from ingestion.registry_import import CatalogFormatError
from knowledge import registry
from retrieval import registry_match

router = APIRouter(prefix="/api/registry", tags=["registry"], dependencies=[Depends(get_current_user)])

_editor = require_role(UserRole.TECHNICIAN, UserRole.ADMIN)
_approver = require_role(UserRole.APPROVER, UserRole.ADMIN)
_ENTITY = "catalog_source"


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1, strict=True)
    note: str = Field(default="", max_length=4000)


def _account(user: AppUser) -> AppUser | None:
    return user if isinstance(user, AppUser) else None


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except registry.RegistryError as e:
        raise HTTPException(e.status, str(e)) from e
    except CatalogFormatError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/sources")
def list_sources():
    return {"sources": _call(registry.list_sources)}


@router.get("/sources/{source_id}")
def read_source(source_id: int):
    return {"source": _call(registry.get_source, source_id)}


@router.post("/sources", status_code=201)
async def upload_source(
    file: UploadFile = File(...),
    user: AppUser = Depends(_editor),
    db: Session = Depends(get_db),
):
    max_mb = get_settings().registry.max_upload_mb
    data = await file.read()
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(413, f"File danh mục vượt quá {max_mb} MB.")
    source = _call(registry.import_file, file.filename or "", data, _account(user))
    after = {"kind": source["kind"], "file_name": source["file_name"], "rows": source["row_count"]}
    record_audit(db, user, "upload", _ENTITY, str(source["id"]), after=after)
    return {"source": source}


def _decide(source_id: int, req: DecisionRequest, approve: bool, user: AppUser, db: Session) -> dict:
    source = _call(registry.decide, source_id, req.revision, approve=approve, note=req.note, user=_account(user))
    if approve:
        registry_match.reload()
    action = "approve" if approve else "reject"
    record_audit(db, user, action, _ENTITY, str(source_id), after={"status": source["status"]})
    return {"source": source}


@router.post("/sources/{source_id}/approve")
def approve_source(
    source_id: int, req: DecisionRequest, user: AppUser = Depends(_approver), db: Session = Depends(get_db)
):
    return _decide(source_id, req, True, user, db)


@router.post("/sources/{source_id}/reject")
def reject_source(
    source_id: int, req: DecisionRequest, user: AppUser = Depends(_approver), db: Session = Depends(get_db)
):
    return _decide(source_id, req, False, user, db)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: int, user: AppUser = Depends(_editor), db: Session = Depends(get_db)):
    _call(registry.delete_source, source_id)
    record_audit(db, user, "delete", _ENTITY, str(source_id))


@router.get("/gaps")
def document_gaps():
    """Quy trình có trong danh mục đã duyệt mà kho chưa có văn bản (mục 10.3 tài liệu kiến trúc)."""
    procedures = registry_match.data().procedures
    missing = [
        {"code": entry.code.key, "title": entry.title, "row": entry.row}
        for entry in procedures
        if entry.code is not None and not registry_match.docs_for(entry)
    ]
    return {"missing": missing, "total": len(procedures)}
