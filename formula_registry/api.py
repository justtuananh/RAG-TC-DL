"""Document-scoped review and approved calculation endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from auth import require_role
from db.models import AppUser, UserRole
from formula_lab.engine import UNITS, Invalid

from .drafts import generate_from_docx
from .store import Conflict, Registry

router = APIRouter(prefix='/api', tags=['formula-review'])

# Tạo/sửa nháp là việc của kỹ thuật viên; phê duyệt/từ chối là việc của người duyệt.
# Xem và tính bằng công thức đã duyệt mở cho mọi người dùng, như tra cứu tài liệu.
_editor = require_role(UserRole.TECHNICIAN, UserRole.ADMIN)
_approver = require_role(UserRole.APPROVER, UserRole.ADMIN)


class Request(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=1, strict=True)


class EditRequest(Request):
    proposal: dict


class DecisionRequest(Request):
    # Giữ để tương thích client cũ; người duyệt ghi vào hồ sơ luôn là tài khoản đã đăng nhập.
    reviewer: str | None = Field(default=None, max_length=200)
    note: str = Field(min_length=1, max_length=4000)
    confirmed: StrictBool = False


class CalculationRequest(Request):
    inputs: dict
    confirmations: dict = Field(default_factory=dict)


def _reviewer(user: AppUser) -> str:
    return f'{user.full_name} ({user.username})' if user.full_name else user.username


def call(fn, *args):
    try:
        return fn(*args)
    except KeyError:
        raise HTTPException(404, 'Không tìm thấy bản nháp.') from None
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except (Invalid, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get('/documents/{document_id}/formula-drafts')
def drafts(document_id: str):
    return {'drafts': Registry().list(document_id), 'units': sorted(UNITS)}


@router.post('/documents/{document_id}/formula-drafts/generate')
def generate(document_id: str, _user: AppUser = Depends(_editor)):
    from ingestion import jobs as ingestion_jobs

    source = ingestion_jobs.get_source_path(document_id)
    if source is None:
        raise HTTPException(404, 'Không tìm thấy tài liệu nguồn.')
    return call(generate_from_docx, source, document_id)


@router.get('/formula-drafts/{id}')
def detail(id: str):
    return call(Registry().get, id)


@router.put('/formula-drafts/{id}')
def edit(id: str, req: EditRequest, _user: AppUser = Depends(_editor)):
    return call(Registry().update, id, req.revision, req.proposal)


@router.post('/formula-drafts/{id}/approve')
def approve(id: str, req: DecisionRequest, user: AppUser = Depends(_approver)):
    return call(
        Registry().decide, id, req.revision, 'approve', _reviewer(user), req.note, req.confirmed
    )


@router.post('/formula-drafts/{id}/reject')
def reject(id: str, req: DecisionRequest, user: AppUser = Depends(_approver)):
    return call(
        Registry().decide, id, req.revision, 'reject', _reviewer(user), req.note, req.confirmed
    )


@router.post('/formula-drafts/{id}/calculate')
def compute(id: str, req: CalculationRequest):
    return call(Registry().compute, id, req.revision, req.inputs, req.confirmations)
