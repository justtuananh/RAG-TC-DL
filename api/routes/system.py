"""Route hệ thống: health (công khai, cho healthcheck) và câu hỏi ví dụ (cần đăng nhập)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from auth import get_current_user
from core.settings_loader import get_settings

router = APIRouter()

EXAMPLES = [
    "Thời gian quay tự do tối thiểu của píttông áp kế là bao lâu?",
    "Công thức hiệu chỉnh nhiệt độ cho thời gian quay tự do?",
    "Sai số cho phép khi kiểm tra van an toàn là bao nhiêu?",
    "Điều kiện môi trường khi tiến hành kiểm định áp suất?",
    "Thiết bị chuẩn cần thiết để kiểm định đồng hồ áp suất?",
    "Số lần đo tối thiểu khi kiểm tra đồng hồ áp suất?",
]


@router.get("/api/health")
def health():
    return {"status": "ok", "model": get_settings().llm_model("chat")}


@router.get("/api/examples", dependencies=[Depends(get_current_user)])
def examples():
    return {"examples": EXAMPLES}
