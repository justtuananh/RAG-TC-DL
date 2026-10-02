"""startup(): bật logging, chặn cấu hình nguy hiểm ở production, kiểm service không bắt buộc."""

import pytest

from core import startup
from core.settings_loader import load_settings, with_overrides


def _prod(**overrides):
    base = load_settings(
        env={
            "APP_ENV": "production",
            "JWT_SECRET_KEY": "k" * 40,
            "POSTGRES_PASSWORD": "mat-khau-that",
        }
    )
    return with_overrides(base, overrides)


def test_production_requires_jwt_secret():
    with pytest.raises(startup.StartupError, match="JWT_SECRET_KEY"):
        startup.validate_security(_prod(**{"auth.jwt_secret_key": None}))


def test_production_rejects_default_db_password():
    with pytest.raises(startup.StartupError, match="POSTGRES_PASSWORD"):
        startup.validate_security(_prod(**{"database.password": "qtkd_password"}))


def test_production_with_real_secrets_passes():
    startup.validate_security(_prod())


def test_development_allows_defaults():
    startup.validate_security(load_settings(env={}))


def test_check_services_reports_down_without_raising(monkeypatch):
    def down(*args, **kwargs):
        raise OSError("down")

    monkeypatch.setattr(startup.requests, "get", down)
    status = startup.check_services(load_settings(env={}))
    assert set(status) == {"embedding", "reranker", "qdrant", "ollama"}
    assert not any(status.values())


def test_vector_size_mismatch_is_fatal():
    with pytest.raises(startup.StartupError, match="768"):
        startup.check_vector_size(load_settings(env={}), probe=lambda name: 768)


def test_missing_collection_is_not_fatal():
    startup.check_vector_size(load_settings(env={}), probe=lambda name: None)
