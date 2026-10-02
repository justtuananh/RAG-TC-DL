"""Password hashing and JWT token management."""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional

import jwt
from bcrypt import hashpw, checkpw, gensalt
from pydantic import BaseModel, Field

from core.settings_loader import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def jwt_secret() -> str:
    """Khóa ký JWT. Thiếu ở development: sinh khóa tạm (token mất hiệu lực khi khởi động lại)."""
    configured = get_settings().auth.jwt_secret_key
    if configured is not None:
        return configured.get_secret_value()
    logger.warning(
        "JWT_SECRET_KEY chưa đặt: dùng khóa tạm cho tiến trình này (chỉ hợp lệ khi dev)"
    )
    return secrets.token_urlsafe(48)


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return hashpw(password.encode(), gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return checkpw(plain_password.encode(), hashed_password.encode())


class TokenPayload(BaseModel):
    """JWT token payload."""

    user_id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    role: str = Field(..., description="User role")
    exp: datetime = Field(..., description="Expiration time")


def create_access_token(user_id: int, username: str, role: str) -> str:
    """Create a JWT access token."""
    auth = get_settings().auth
    exp = datetime.now(timezone.utc) + timedelta(hours=auth.jwt_expiration_hours)
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, jwt_secret(), algorithm=auth.jwt_algorithm)
    return token


def decode_access_token(token: str) -> Optional[TokenPayload]:
    """Decode and validate a JWT access token."""
    auth = get_settings().auth
    try:
        payload = jwt.decode(token, jwt_secret(), algorithms=[auth.jwt_algorithm])
        return TokenPayload(**payload)
    except (jwt.DecodeError, jwt.ExpiredSignatureError, ValueError):
        return None
