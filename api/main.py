"""Ứng dụng FastAPI cho frontend React: ghép router, CORS, vòng đời khởi động.

Chạy: python -m api.main  (hoặc uvicorn api.main:app)

Endpoints:
  GET    /api/health
  GET    /api/examples
  POST   /api/chat/stream            - SSE streaming (text/event-stream)
    Sprint 9: định tuyến 3 nhánh - text (RAG hiện tại) / data (sổ cái) / mixed.
    Event: status | sources | data (khối số liệu) | delta | done{branch,data} | error
  GET    /api/documents              - list real files in TC_DL/ + ingestion status
  POST   /api/documents/upload       - save a .docx/.xlsx/.pdf (multipart "file"), status "pending"
  POST   /api/documents/{id}/process - extract -> chunk -> embed (background thread)
  GET    /api/documents/{id}/markdown
  GET    /api/documents/{id}/file    - tệp gốc (.docx/.xlsx/.pdf) thô, để hiển thị "tài liệu gốc"
  GET    /api/documents/{id}/preview - bản xem trên trình duyệt (.doc/.xls -> .docx/.xlsx)
  DELETE /api/documents/{id}
  PATCH  /api/documents/{id}         - {"name": str} display-name override

  Sprint 6 - hàng đợi duyệt (vai trò approver/admin): /api/extractions*
  Sprint 7 - nạp và đọc hồ sơ kiểm định: /api/records*
  Sprint 8 - tra cứu dữ liệu và danh mục NAS: /api/data/*
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import auth, chat, data, documents, extractions, records, system
from core.settings_loader import get_settings
from core.startup import startup
from vectorstore import qdrant

_ROUTERS = (system, auth, chat, documents, extractions, records, data)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    startup(vector_size_probe=qdrant.collection_vector_size)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="QTKĐ RAG API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.api.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in _ROUTERS:
        app.include_router(module.router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run("api.main:app", host=settings.api.host, port=settings.api.port)


if __name__ == "__main__":
    main()
