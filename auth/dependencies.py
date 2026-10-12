"""FastAPI dependency functions for authentication and authorization."""

import secrets
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from core.settings_loader import get_settings
from db import get_db
from db.models import AppUser, UserRole
from .security import decode_access_token, hash_password


security = HTTPBearer(auto_error=False)

LOCAL_ADMIN_USERNAME = "local"


def local_admin(db: Session) -> AppUser:
    """Tài khoản dùng chung khi tắt đăng nhập (auth.enabled=false).

    Lấy quản trị viên đang hoạt động đầu tiên; chưa có thì tạo tài khoản `local`
    trong CSDL để khóa ngoại audit_log / người duyệt luôn trỏ tới một dòng thật.
    Mật khẩu ngẫu nhiên không ai biết: tài khoản này không đăng nhập được khi bật lại.
    """
    user = (
        db.query(AppUser)
        .filter(AppUser.role == UserRole.ADMIN, AppUser.is_active == 1)
        .order_by(AppUser.id)
        .first()
    )
    if user:
        return user
    user = AppUser(
        username=LOCAL_ADMIN_USERNAME,
        full_name="Người dùng cục bộ",
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role=UserRole.ADMIN,
        is_active=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> AppUser:
    """Dependency to extract and validate the current user from JWT token."""
    if not get_settings().auth.enabled:
        return local_admin(db)

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(AppUser).filter(AppUser.id == payload.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


def require_role(*allowed_roles: UserRole):
    """
    Dependency to check user role. Usage:

    @app.get("/admin")
    async def admin_endpoint(user: AppUser = Depends(require_role(UserRole.ADMIN))):
        ...
    """

    async def role_checker(
        user: AppUser = Depends(get_current_user),
    ) -> AppUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản của bạn không có quyền thực hiện thao tác này.",
            )
        return user

    return role_checker
