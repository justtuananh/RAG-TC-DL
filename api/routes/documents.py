"""Route tài liệu: liệt kê, tải lên, xử lý, xem Markdown/tệp gốc, xóa, đổi tên."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.audit import document_snapshot, record_audit
from api.schemas import RenameRequest
from auth import require_role
from db import get_db
from db.models import AppUser, UserRole
from ingestion import jobs as ingestion_jobs

router = APIRouter()


@router.get("/api/documents")
def list_documents():
    return {"documents": ingestion_jobs.list_documents()}


@router.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    user: AppUser = Depends(require_role(UserRole.TECHNICIAN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    data = await file.read()
    try:
        file_stem = ingestion_jobs.save_upload(
            file.filename or "",
            data,
            uploaded_by=user.id if isinstance(user, AppUser) else None,
        )
    except ingestion_jobs.UploadError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    doc = next((d for d in ingestion_jobs.list_documents() if d["id"] == file_stem), None)
    if doc is None:
        raise HTTPException(status_code=500, detail="Đã lưu tệp nhưng không đọc lại được.")
    record_audit(db, user, "upload", "document", file_stem, after=document_snapshot(doc))
    return doc


@router.post("/api/documents/{file_stem}/process")
def process_document(
    file_stem: str,
    user: AppUser = Depends(require_role(UserRole.TECHNICIAN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        ingestion_jobs.start_processing(file_stem)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.") from None
    except RuntimeError:
        raise HTTPException(status_code=409, detail="Tài liệu đang được xử lý.") from None
    record_audit(db, user, "process", "document", file_stem, after={"status": "queued"})
    return {"status": "queued"}


@router.get("/api/documents/{file_stem}/markdown")
def document_markdown(file_stem: str):
    md = ingestion_jobs.get_markdown(file_stem)
    if md is None:
        raise HTTPException(status_code=404, detail="Tài liệu chưa được xử lý.")
    return {"file_stem": file_stem, "markdown": md}


_FILE_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.get("/api/documents/{file_stem}/file")
def document_file(file_stem: str):
    """Trả về tệp .docx/.xlsx/.pdf gốc (không phải Markdown đã trích xuất/embed) để
    frontend hiển thị đúng tài liệu nguồn."""
    path = ingestion_jobs.get_source_path(file_stem)
    if path is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp gốc.")
    media_type = _FILE_MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(
        path, media_type=media_type, filename=path.name, content_disposition_type="inline"
    )


@router.get("/api/documents/{file_stem}/preview")
def document_preview(file_stem: str):
    """Bản xem được trên trình duyệt: .doc/.xls cũ trả bản .docx/.xlsx đã chuyển bằng
    LibreOffice (giữ đúng định dạng gốc để render như .docx); định dạng khác trả tệp gốc."""
    from ingestion.convert_legacy import ConvertLegacyError

    try:
        path = ingestion_jobs.get_preview_path(file_stem)
    except ConvertLegacyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if path is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp gốc.")
    media_type = _FILE_MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type, content_disposition_type="inline")


@router.delete("/api/documents/{file_stem}", status_code=204)
def delete_document(
    file_stem: str,
    user: AppUser = Depends(require_role(UserRole.TECHNICIAN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    before = next((d for d in ingestion_jobs.list_documents() if d["id"] == file_stem), None)
    try:
        ingestion_jobs.delete_document(file_stem)
    except ingestion_jobs.DocumentInUseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if before is not None:
        record_audit(db, user, "delete", "document", file_stem, before=document_snapshot(before))


@router.patch("/api/documents/{file_stem}")
def rename_document(
    file_stem: str,
    req: RenameRequest,
    user: AppUser = Depends(require_role(UserRole.TECHNICIAN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    before = next((d for d in ingestion_jobs.list_documents() if d["id"] == file_stem), None)
    try:
        doc = ingestion_jobs.rename_document(file_stem, req.name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.") from None
    record_audit(
        db,
        user,
        "rename",
        "document",
        file_stem,
        before={"name": before["name"]} if before else None,
        after={"name": doc["name"]},
    )
    return doc
