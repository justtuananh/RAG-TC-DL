"""Route chat: stream câu trả lời qua SSE."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.schemas import ChatRequest
from api.services.chat_stream import chat_stream_events
from db import get_db

router = APIRouter()


@router.post("/api/chat/stream")
def chat_stream(req: ChatRequest, db: Session = Depends(get_db)):
    return StreamingResponse(
        chat_stream_events(req, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
