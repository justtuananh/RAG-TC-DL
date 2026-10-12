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
