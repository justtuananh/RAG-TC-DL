"""Schema tham số pydantic cho bốn intent tra cứu danh mục NAS (Pha D2).

Tách khỏi ``query/intents.py`` để giữ mỗi tệp gọn. LLM chỉ chọn intent + điền
tham số; mọi tham số vẫn qua pydantic trước khi tới truy vấn tham số hóa của
``query/catalogs.py`` (chỉ view đã duyệt, P3). Không có text-to-SQL tự do.

Bất biến:
- P1: tham số chỉ là bộ lọc/định danh; kết quả vẫn kèm tham chiếu xuất xứ.
- P2: không có phép tính nào trên số liệu nguồn ở đây.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class LabStandardLookupParams(BaseModel):
    """Chuẩn mẫu: tra theo tên/ký hiệu/số hiệu, lọc thêm theo mục sử dụng."""

    query: str | None = Field(default=None, max_length=255)
    usage_ref: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def _require_selector(self) -> LabStandardLookupParams:
        if not (self.query or self.usage_ref):
            raise ValueError("Cần tên/ký hiệu/số hiệu chuẩn mẫu hoặc mục sử dụng.")
        return self


class InspectorLookupParams(BaseModel):
    """Kiểm định viên: tra theo họ tên và/hoặc lĩnh vực được chứng nhận."""

    name: str | None = Field(default=None, max_length=255)
    field: str | None = Field(default=None, max_length=255)


class ProcedureCatalogLookupParams(BaseModel):
    """Danh mục tiêu chuẩn, quy trình: tra theo mã, tên thiết bị hoặc nhóm lĩnh vực."""

    code: str | None = Field(default=None, max_length=64)
    keyword: str | None = Field(default=None, max_length=255)
    group: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _require_selector(self) -> ProcedureCatalogLookupParams:
        if not (self.code or self.keyword or self.group):
            raise ValueError("Cần mã quy trình, tên thiết bị hoặc nhóm lĩnh vực.")
        return self


class CapabilityLookupParams(BaseModel):
    """Lĩnh vực được công nhận: tra theo tên đại lượng/trang bị."""

    keyword: str = Field(min_length=1, max_length=255)


class LabStandardLookupRequest(BaseModel):
    intent: Literal["lab_standard_lookup"] = "lab_standard_lookup"
    params: LabStandardLookupParams


class InspectorLookupRequest(BaseModel):
    intent: Literal["inspector_lookup"] = "inspector_lookup"
    params: InspectorLookupParams


class ProcedureCatalogLookupRequest(BaseModel):
    intent: Literal["procedure_catalog_lookup"] = "procedure_catalog_lookup"
    params: ProcedureCatalogLookupParams


class CapabilityLookupRequest(BaseModel):
    intent: Literal["capability_lookup"] = "capability_lookup"
    params: CapabilityLookupParams


CATALOG_INTENT_NAMES: tuple[str, ...] = (
    "lab_standard_lookup",
    "inspector_lookup",
    "procedure_catalog_lookup",
    "capability_lookup",
)

CATALOG_PARAM_MODELS: dict[str, type[BaseModel]] = {
    "lab_standard_lookup": LabStandardLookupParams,
    "inspector_lookup": InspectorLookupParams,
    "procedure_catalog_lookup": ProcedureCatalogLookupParams,
    "capability_lookup": CapabilityLookupParams,
}

CATALOG_REQUESTS: tuple[type[BaseModel], ...] = (
    LabStandardLookupRequest,
    InspectorLookupRequest,
    ProcedureCatalogLookupRequest,
    CapabilityLookupRequest,
)

# Từ đồng nghĩa khoá tham số riêng của danh mục (LLM hay trả tiếng Việt).
CATALOG_PARAM_ALIASES: dict[str, str] = {
    "ten": "query",
    "tên": "query",
    "ten_chuan_mau": "query",
    "tên_chuẩn_mẫu": "query",
    "ten_chuan": "query",
    "ky_hieu": "query",
    "ký_hiệu": "query",
    "usage": "usage_ref",
    "usage_ref": "usage_ref",
    "muc_su_dung": "usage_ref",
    "mục_sử_dụng": "usage_ref",
    "linh_vuc": "field",
    "lĩnh_vực": "field",
    "field_name": "field",
    "nhom": "group",
    "nhóm": "group",
    "group_title": "group",
    "linh_vuc_nhom": "group",
    "ma": "code",
    "mã": "code",
    "code_text": "code",
    "so_hieu_quy_trinh": "code",
    "tu_khoa": "keyword",
    "từ_khóa": "keyword",
    "keyword_text": "keyword",
    "ten_thiet_bi": "keyword",
    "tên_thiết_bị": "keyword",
}
