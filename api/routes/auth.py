"""Route xác thực: đăng nhập, hồ sơ, đăng xuất, làm mới token."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas import LoginRequest
from auth import create_access_token, get_current_user, verify_password
from db import get_db
from db.models import AppUser

router = APIRouter()


@router.post("/api/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(AppUser).filter(AppUser.username == req.username).one_or_none()
    if user is None or not user.is_active or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu.")
    return {
        "access_token": create_access_token(user.id, user.username, user.role.value),
        "token_type": "bearer",
    }


@router.get("/api/auth/me")
def me(user: AppUser = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role.value,
    }


@router.post("/api/auth/logout", status_code=204)
def logout(user: AppUser = Depends(get_current_user)):
    """Stateless JWT logout - the client discards the token. Kept server-side so
    the frontend has a single, authenticated place to end a session."""
    return None


@router.post("/api/auth/refresh")
def refresh(user: AppUser = Depends(get_current_user)):
    """Issue a fresh access token for the current user (sliding expiry)."""
    return {
        "access_token": create_access_token(user.id, user.username, user.role.value),
        "token_type": "bearer",
    }
