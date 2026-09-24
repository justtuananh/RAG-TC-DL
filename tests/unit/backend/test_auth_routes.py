"""Route-protection + audit-log tests for the Sprint 1 auth layer.

Runs fully in-process: FastAPI TestClient (ASGI, no sockets) + in-memory SQLite
with the ORM models. `get_db` is dependency-overridden so no PostgreSQL is
needed. Write routes are exercised with `ingestion_jobs` stubbed so the tests
assert authorization/audit behaviour, not ingestion behaviour.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api_server
import auth.dependencies as auth_deps
import ingestion_jobs
from auth.security import create_access_token, hash_password
from db import get_db
from db.models import AppUser, AuditLog, Base, UserRole

PASSWORD = "correct-horse-battery"


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def users(session_factory):
    """Three accounts, one per role, with known ids."""
    db = session_factory()
    try:
        admin = AppUser(
            username="admin",
            full_name="Quản trị",
            password_hash=hash_password(PASSWORD),
            role=UserRole.ADMIN,
            is_active=1,
        )
        tech = AppUser(
            username="tech",
            full_name="Kỹ thuật",
            password_hash=hash_password(PASSWORD),
            role=UserRole.TECHNICIAN,
            is_active=1,
        )
        viewer = AppUser(
            username="viewer",
            full_name="Người xem",
            password_hash=hash_password(PASSWORD),
            role=UserRole.VIEWER,
            is_active=1,
        )
        db.add_all([admin, tech, viewer])
        db.commit()
        return {
            "admin": (admin.id, admin.username),
            "technician": (tech.id, tech.username),
            "viewer": (viewer.id, viewer.username),
        }
    finally:
        db.close()


@pytest.fixture
def client(session_factory, monkeypatch):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    api_server.app.dependency_overrides[get_db] = override_get_db
    # Auth must be ON for the 401/403 matrix; never inherit a dev override.
    monkeypatch.setattr(auth_deps, "AUTH_ENABLED", True)
    with TestClient(api_server.app) as test_client:
        yield test_client
    api_server.app.dependency_overrides.clear()


def _token(users, role: str) -> str:
    user_id, username = users[role]
    return create_access_token(user_id, username, role)


def _audit_rows(session_factory) -> list[AuditLog]:
    db = session_factory()
    try:
        return db.query(AuditLog).order_by(AuditLog.id).all()
    finally:
        db.close()


WRITE_ROUTES = [
    (
        "post",
        "/api/documents/upload",
        {"files": {"file": ("a.docx", b"x", "application/octet-stream")}},
    ),
    ("post", "/api/documents/stem/process", {}),
    ("delete", "/api/documents/stem", {}),
    ("patch", "/api/documents/stem", {"json": {"name": "Tên mới"}}),
]


@pytest.mark.parametrize("method, path, kwargs", WRITE_ROUTES)
def test_write_routes_reject_missing_token(client, method, path, kwargs):
    resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code == 401


@pytest.mark.parametrize("method, path, kwargs", WRITE_ROUTES)
def test_write_routes_forbid_viewer(client, users, method, path, kwargs):
    headers = {"Authorization": f"Bearer {_token(users, 'viewer')}"}
    resp = getattr(client, method)(path, headers=headers, **kwargs)
    assert resp.status_code == 403


def test_write_routes_reject_invalid_token(client):
    headers = {"Authorization": "Bearer not.a.real.token"}
    resp = client.post("/api/documents/stem/process", headers=headers)
    assert resp.status_code == 401


def test_technician_upload_records_audit(client, users, session_factory, monkeypatch):
    captured: dict = {}

    def fake_save_upload(filename, data, uploaded_by=None):
        captured["filename"] = filename
        captured["uploaded_by"] = uploaded_by
        return "a"

    doc = {
        "id": "a",
        "name": "a.docx",
        "ext": "DOCX",
        "size": "1 KB",
        "doc_type": "qtkd",
        "status": "pending",
        "sha256": "ab" * 32,
    }
    monkeypatch.setattr(ingestion_jobs, "save_upload", fake_save_upload)
    monkeypatch.setattr(ingestion_jobs, "list_documents", lambda: [doc])

    headers = {"Authorization": f"Bearer {_token(users, 'technician')}"}
    resp = client.post(
        "/api/documents/upload",
        headers=headers,
        files={"file": ("a.docx", b"hello", "application/octet-stream")},
    )

    assert resp.status_code == 200
    assert resp.json()["id"] == "a"
    assert captured["uploaded_by"] == users["technician"][0]

    rows = _audit_rows(session_factory)
    assert len(rows) == 1
    assert rows[0].action == "upload"
    assert rows[0].entity_type == "document"
    assert rows[0].entity_id == "a"
    assert rows[0].actor_id == users["technician"][0]
    assert rows[0].after["name"] == "a.docx"


def test_process_records_audit(client, users, session_factory, monkeypatch):
    monkeypatch.setattr(ingestion_jobs, "start_processing", lambda stem: None)
    headers = {"Authorization": f"Bearer {_token(users, 'technician')}"}
    resp = client.post("/api/documents/stem/process", headers=headers)
    assert resp.status_code == 200

    rows = _audit_rows(session_factory)
    assert [(r.action, r.entity_id) for r in rows] == [("process", "stem")]


def test_delete_records_before_snapshot(client, users, session_factory, monkeypatch):
    doc = {
        "id": "stem",
        "name": "stem.docx",
        "ext": "DOCX",
        "size": "1 KB",
        "doc_type": "qtkd",
        "status": "ready",
        "sha256": "cd" * 32,
    }
    deleted: list[str] = []
    monkeypatch.setattr(ingestion_jobs, "list_documents", lambda: [doc])
    monkeypatch.setattr(ingestion_jobs, "delete_document", lambda stem: deleted.append(stem))

    headers = {"Authorization": f"Bearer {_token(users, 'admin')}"}
    resp = client.delete("/api/documents/stem", headers=headers)
    assert resp.status_code == 204
    assert deleted == ["stem"]

    rows = _audit_rows(session_factory)
    assert len(rows) == 1
    assert rows[0].action == "delete"
    assert rows[0].before["name"] == "stem.docx"


def test_rename_records_before_and_after(client, users, session_factory, monkeypatch):
    before = {
        "id": "stem",
        "name": "stem.docx",
        "ext": "DOCX",
        "size": "1 KB",
        "doc_type": "qtkd",
        "status": "ready",
        "sha256": "ef" * 32,
    }
    after = {**before, "name": "Tên mới"}
    monkeypatch.setattr(ingestion_jobs, "list_documents", lambda: [before])
    monkeypatch.setattr(ingestion_jobs, "rename_document", lambda stem, name: after)

    headers = {"Authorization": f"Bearer {_token(users, 'technician')}"}
    resp = client.patch("/api/documents/stem", headers=headers, json={"name": "Tên mới"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Tên mới"

    rows = _audit_rows(session_factory)
    assert len(rows) == 1
    assert rows[0].action == "rename"
    assert rows[0].before == {"name": "stem.docx"}
    assert rows[0].after == {"name": "Tên mới"}


# ── Auth endpoints ────────────────────────────────────────────────────────────


def test_login_returns_token_and_me_returns_role(client, users):
    resp = client.post("/api/auth/login", json={"username": "tech", "password": PASSWORD})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "tech"
    assert me.json()["role"] == "technician"


def test_login_rejects_wrong_password(client, users):
    resp = client.post("/api/auth/login", json={"username": "tech", "password": "nope"})
    assert resp.status_code == 401


def test_login_unknown_user(client, users):
    resp = client.post("/api/auth/login", json={"username": "ghost", "password": PASSWORD})
    assert resp.status_code == 401


def test_logout_and_refresh(client, users):
    headers = {"Authorization": f"Bearer {_token(users, 'technician')}"}
    assert client.post("/api/auth/logout", headers=headers).status_code == 204

    refreshed = client.post("/api/auth/refresh", headers=headers)
    assert refreshed.status_code == 200
    new_token = refreshed.json()["access_token"]
    assert (
        client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"}).status_code
        == 200
    )


def test_logout_requires_token(client, users):
    assert client.post("/api/auth/logout").status_code == 401


def test_dev_mode_without_auth_uses_mock_user(client, monkeypatch):
    """AUTH_ENABLED=false must not 401 writes (local frontend workflow) and must
    not crash on the actor FK when no persisted admin exists."""
    monkeypatch.setattr(auth_deps, "AUTH_ENABLED", False)
    monkeypatch.setattr(ingestion_jobs, "start_processing", lambda stem: None)
    resp = client.post("/api/documents/stem/process")
    assert resp.status_code == 200
