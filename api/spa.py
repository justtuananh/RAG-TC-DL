"""Phục vụ bản build React (``frontend/dist``) từ chính FastAPI.

Bản chạy native (Windows/Linux không Docker) không có nginx: một cổng API duy nhất
vừa trả ``/api``, vừa trả tệp tĩnh của SPA. Route bắt tất cả được đăng ký SAU các
router API nên ``/api/...`` luôn thắng; đường dẫn không phải tệp có thật trả
``index.html`` để router phía trình duyệt hoạt động khi người dùng tải lại trang.

Route luôn được đăng ký (kể cả khi chưa build frontend) để bảng route không phụ
thuộc máy đang chạy; thiếu ``index.html`` thì trả 404 rõ ràng thay vì 500.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def mount_spa(app: FastAPI, dist: Path) -> None:
    """Gắn route phục vụ SPA từ ``dist``; an toàn khi thư mục chưa tồn tại."""
    root = dist.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        # /api do các router phía trên xử lý; đường dẫn API không khớp là 404 API,
        # không được rơi về index.html (frontend sẽ tưởng là HTML hợp lệ).
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        if full_path:
            candidate = (root / full_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(root):
                # Vite băm tên tệp trong assets/ nên cache dài hạn là an toàn.
                cache = (
                    "public, max-age=31536000, immutable"
                    if full_path.startswith("assets/")
                    else "no-cache"
                )
                return FileResponse(candidate, headers={"Cache-Control": cache})

        index = root / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=404, detail="Frontend chưa được build")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
