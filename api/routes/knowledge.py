"""Route trang Hồ sơ QTKĐ: tri thức ĐÃ DUYỆT của từng quy trình.

Bề mặt đọc như ``/api/data/*``: mọi người dùng đã đăng nhập đều xem được; chỉ đọc
qua view đã duyệt ở ``query/procedure_profile`` (P3). Mỗi dòng kèm ``id`` /
``extraction_id`` để giao diện mở nguyên văn qua ``GET /api/data/provenance`` (P1).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.errors import data_http_error
from auth import get_current_user
from core.settings_loader import get_settings
from db import get_db
from db.models import AppUser
from query import procedure_profile as profile_query

router = APIRouter()


@router.get("/api/knowledge/procedures")
def knowledge_procedures(
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Danh sách QTKĐ kèm số tri thức đã duyệt; tìm không dấu theo số hiệu/tên/loại."""
    limit = max(1, min(limit, get_settings().query.list_limit_max))
    offset = max(0, offset)
    items, total = profile_query.list_procedures(db, q=q, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/api/knowledge/procedures/{procedure_id}")
def knowledge_procedure_profile(
    procedure_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hồ sơ một QTKĐ: thông số, điều kiện, các phép kiểm định, phương tiện, công thức,
    thuật ngữ và tóm tắt biên bản - tất cả đã duyệt."""
    try:
        return profile_query.procedure_profile(db, procedure_id)
    except profile_query.NotFoundError as exc:
        raise data_http_error(exc) from exc
