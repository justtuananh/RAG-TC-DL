"""Tests for authentication module."""

from auth.security import create_access_token, decode_access_token, hash_password, verify_password
from db.models import UserRole


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password(self):
        """Test that password hashing produces a hash."""
        password = "test_password_123"
        hashed = hash_password(password)
        assert hashed != password
        assert len(hashed) > len(password)

    def test_verify_correct_password(self):
        """Test that correct password verifies successfully."""
        password = "test_password_123"
        hashed = hash_password(password)
        assert verify_password(password, hashed)

    def test_verify_wrong_password(self):
        """Test that wrong password fails verification."""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = hash_password(password)
        assert not verify_password(wrong_password, hashed)

    def test_different_hashes_same_password(self):
        """Test that same password produces different hashes (due to salt)."""
        password = "test_password_123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)


class TestJWTToken:
    """Test JWT token creation and verification."""

    def test_create_access_token(self):
        """Test that access token is created."""
        token = create_access_token(user_id=1, username="testuser", role=UserRole.ADMIN.value)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_valid_token(self):
        """Test that valid token is decoded correctly."""
        token = create_access_token(user_id=42, username="testuser", role=UserRole.TECHNICIAN.value)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload.user_id == 42
        assert payload.username == "testuser"
        assert payload.role == UserRole.TECHNICIAN.value

    def test_decode_invalid_token(self):
        """Test that invalid token returns None."""
        invalid_token = "not.a.valid.token"
        payload = decode_access_token(invalid_token)
        assert payload is None

    def test_token_contains_required_fields(self):
        """Test that token payload contains all required fields."""
        token = create_access_token(user_id=1, username="testuser", role=UserRole.VIEWER.value)
        payload = decode_access_token(token)
        assert payload.user_id == 1
        assert payload.username == "testuser"
        assert payload.role == UserRole.VIEWER.value
        assert payload.exp is not None
