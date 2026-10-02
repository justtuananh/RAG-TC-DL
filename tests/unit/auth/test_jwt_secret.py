"""Khóa JWT: lấy từ cấu hình; dev thiếu khóa thì sinh khóa tạm, ổn định trong tiến trình."""

from auth import security


def test_configured_secret_is_used(settings_override):
    settings_override({"auth.jwt_secret_key": "khoa-that"})
    security.jwt_secret.cache_clear()
    assert security.jwt_secret() == "khoa-that"


def test_missing_secret_in_development_is_random_but_stable(settings_override, caplog):
    settings_override({"auth.jwt_secret_key": None, "app.env": "development"})
    security.jwt_secret.cache_clear()
    first = security.jwt_secret()
    assert len(first) >= 32
    assert security.jwt_secret() == first
    assert "JWT_SECRET_KEY" in caplog.text
