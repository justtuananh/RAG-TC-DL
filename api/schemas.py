"""Model pydantic cho request body của các route HTTP."""

from __future__ import annotations

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class RenameRequest(BaseModel):
    name: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ApproveRequest(BaseModel):
    note: str | None = None


class RejectRequest(BaseModel):
    reason: str


class EditApproveRequest(BaseModel):
    """Trường dữ kiện được sửa rồi duyệt (chỉ gửi trường thực sự đổi)."""

    label: str | None = None
    rel_op: str | None = None
    value_min: float | None = None
    value_max: float | None = None
    unit_id: int | None = None
    value_text: str | None = None
    condition_text: str | None = None
    name_vi: str | None = None
    range_text: str | None = None
    accuracy_text: str | None = None
    note: str | None = None
    term_vi: str | None = None
    term_en: str | None = None
    definition: str | None = None


class BulkApproveRequest(BaseModel):
    extractor: str
    section_path: str | None = None
    document_id: str | None = None
    note: str | None = None


class IngestRecordRequest(BaseModel):
    """Chỉ định QTKĐ khi hồ sơ không tự nhận diện được (tùy chọn)."""

    procedure_id: int | None = None
