"""FastAPI dependency functions for authentication and authorization."""
import os
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from db import get_db
from db.models import AppUser, UserRole
from .security import decode_access_token


# Global toggle for auth (dev/prod)
AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> AppUser:
    """Dependency to extract and validate the current user from JWT token."""
    if not AUTH_ENABLED:
        # In dev mode with auth disabled, return a mock admin user
        user = db.query(AppUser).filter(AppUser.role == UserRole.ADMIN).first()
        if user:
            return user
        # If no admin exists yet, create a mock one
        class MockUser:
            id = 1
            username = "dev"
            role = UserRole.ADMIN
            is_active = 1
        return MockUser()

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
                detail=f"Insufficient permissions. Required roles: {allowed_roles}",
            )
        return user

    return role_checker
