"""Route tra cứu dữ liệu (Sprint 8) và danh mục NAS (Pha D1).

Mọi route chỉ ĐỌC qua các view đã duyệt ở `query/` (P3). Vai trò: mọi người dùng
đã đăng nhập (kể cả viewer) đều tra cứu được; đây là bề mặt đọc. Mỗi ô số trả kèm
tham chiếu xuất xứ; `GET /api/data/provenance` mở đoạn nguồn.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from api.errors import data_http_error
from auth import get_current_user
from core.settings_loader import get_settings
from db import get_db
from db.models import AppUser
from query import catalogs as catalog_query
from query import export as data_export
from query import provenance as provenance_query
from query import records as data_query

router = APIRouter()


@router.get("/api/data/filters")
def data_filters(
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Giá trị bộ lọc (loại thiết bị, đại lượng, QTKĐ, kết luận) đọc từ dữ liệu đã duyệt."""
    return data_query.filter_options(db)


@router.get("/api/data/records")
def data_records(
    device_type_id: int | None = None,
    quantity_id: int | None = None,
    procedure_id: int | None = None,
    verdict: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    range_min: float | None = None,
    range_max: float | None = None,
    range_unit: str | None = None,
    accuracy: str | None = None,
    serial: str | None = None,
    search: str | None = None,
    sort: str = data_query.DEFAULT_SORT,
    order: str = data_query.DEFAULT_ORDER,
    limit: int = 50,
    offset: int = 0,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bảng hồ sơ đã duyệt: phân trang, sắp xếp, lọc nhiều tiêu chí (P3)."""
    try:
        items, total = data_query.list_records(
            db,
            device_type_id=device_type_id,
            quantity_id=quantity_id,
            procedure_id=procedure_id,
            verdict=verdict,
            date_from=date_from,
            date_to=date_to,
            range_min=range_min,
            range_max=range_max,
            range_unit=range_unit,
            accuracy=accuracy,
            serial=serial,
            search=search,
            sort=sort,
            order=order,
            limit=limit,
            offset=offset,
        )
    except data_query.QueryError as exc:
        raise data_http_error(exc) from exc
    return {
        "items": items,
        "total": total,
        "limit": max(1, min(limit, get_settings().query.list_limit_max)),
        "offset": max(0, offset),
        "sort": sort,
        "order": order,
    }


@router.get("/api/data/records/export.xlsx")
def data_records_export(
    device_type_id: int | None = None,
    quantity_id: int | None = None,
    procedure_id: int | None = None,
    verdict: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    range_min: float | None = None,
    range_max: float | None = None,
    range_unit: str | None = None,
    accuracy: str | None = None,
    serial: str | None = None,
    search: str | None = None,
    sort: str = data_query.DEFAULT_SORT,
    order: str = data_query.DEFAULT_ORDER,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Xuất Excel kết quả lọc hiện tại, kèm cột xuất xứ cho từng ô số (P1)."""
    try:
        records = data_query.all_records(
            db,
            device_type_id=device_type_id,
            quantity_id=quantity_id,
            procedure_id=procedure_id,
            verdict=verdict,
            date_from=date_from,
            date_to=date_to,
            range_min=range_min,
            range_max=range_max,
            range_unit=range_unit,
            accuracy=accuracy,
            serial=serial,
            search=search,
            sort=sort,
            order=order,
        )
    except data_query.QueryError as exc:
        raise data_http_error(exc) from exc

    fact_cache: dict[int, dict | None] = {}

    def _fact_lookup(fact_id: int) -> dict | None:
        if fact_id not in fact_cache:
            try:
                fact_cache[fact_id] = provenance_query.fact_provenance(db, fact_id)
            except provenance_query.ProvenanceError:
                fact_cache[fact_id] = None
        return fact_cache[fact_id]

    payload = data_export.records_xlsx(records, _fact_lookup)
    filename = f"du-lieu-kiem-dinh-{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/data/records/{record_id}")
def data_record_detail(
    record_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Chi tiết một hồ sơ đã duyệt + các điểm đo, mỗi ô số có tham chiếu xuất xứ."""
    try:
        return data_query.get_record(db, record_id)
    except data_query.QueryError as exc:
        raise data_http_error(exc) from exc


@router.get("/api/data/devices")
def data_devices(
    q: str | None = None,
    device_type_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Thiết bị có ít nhất một hồ sơ đã duyệt (tìm theo số hiệu/model/hãng)."""
    devices, total = data_query.list_devices(
        db, q=q, device_type_id=device_type_id, limit=limit, offset=offset
    )
    return {
        "items": devices,
        "total": total,
        "limit": max(1, min(limit, get_settings().query.list_limit_max)),
        "offset": max(0, offset),
    }


@router.get("/api/data/devices/{device_id}/history")
def data_device_history(
    device_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trang thiết bị: định danh, dòng thời gian kiểm định, diễn biến sai số (P3)."""
    try:
        return data_query.device_history(db, device_id=device_id)
    except data_query.QueryError as exc:
        raise data_http_error(exc) from exc


@router.get("/api/data/devices/by-serial/{serial}")
def data_device_history_by_serial(
    serial: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trang thiết bị theo số hiệu (đường dẫn tiện dụng cho liên kết từ bảng)."""
    try:
        return data_query.device_history(db, serial=serial)
    except data_query.QueryError as exc:
        raise data_http_error(exc) from exc


@router.get("/api/data/provenance")
def data_provenance(
    extraction_id: int | None = None,
    record_id: int | None = None,
    fact_id: int | None = None,
    measurement_id: int | None = None,
    field: str | None = None,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mở đúng đoạn nguyên văn sinh ra một ô số: tài liệu, mục, chunk, trích dẫn (P1)."""
    try:
        return provenance_query.resolve(
            db,
            extraction_id=extraction_id,
            record_id=record_id,
            fact_id=fact_id,
            measurement_id=measurement_id,
            field=field,
        )
    except provenance_query.ProvenanceError as exc:
        raise data_http_error(exc) from exc


@router.get("/api/data/catalogs")
def data_catalog_counts(
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Số dòng đã duyệt của từng loại danh mục NAS (P3)."""
    return {"counts": catalog_query.catalog_counts(db)}


@router.get("/api/data/catalogs/{kind}")
def data_catalog(
    kind: str,
    q: str | None = None,
    group: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bảng danh mục NAS đã duyệt: tìm không dấu, lọc nhóm, phân trang, kèm xuất xứ."""
    try:
        items, total = catalog_query.list_catalog(
            db, kind, q=q, group=group, limit=limit, offset=offset
        )
        groups = catalog_query.catalog_groups(db, kind)
    except data_query.QueryError as exc:
        raise data_http_error(exc) from exc
    return {
        "items": items,
        "total": total,
        "limit": max(1, min(limit, get_settings().query.list_limit_max)),
        "offset": max(0, offset),
        "groups": groups,
    }
