"""Password hashing and JWT token management."""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from bcrypt import hashpw, checkpw, gensalt
from pydantic import BaseModel, Field


# JWT configuration
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.environ.get("JWT_EXPIRATION_HOURS", "24"))


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
    exp = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def decode_access_token(token: str) -> Optional[TokenPayload]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return TokenPayload(**payload)
    except (jwt.DecodeError, jwt.ExpiredSignatureError, ValueError):
        return None
