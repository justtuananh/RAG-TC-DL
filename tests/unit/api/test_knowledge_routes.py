"""API trang Hồ sơ QTKĐ: ``/api/knowledge/procedures*``.

Chạy in-process (TestClient + SQLite) trên bộ seed dùng chung: mọi vai trò đã đăng
nhập đọc được, thiếu token → 401, QTKĐ không tồn tại → 404.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from auth.security import create_access_token, hash_password
from db import get_db
from db.models import AppUser, UserRole


@pytest.fixture
def client(data_factory, settings_override):
    factory, ids = data_factory
    db = factory()
    try:
        user = AppUser(
            username="viewer",
            full_name="viewer",
            password_hash=hash_password("correct-horse-battery"),
            role=UserRole.VIEWER,
            is_active=1,
        )
        db.add(user)
        db.commit()
        token = create_access_token(user.id, user.username, UserRole.VIEWER.value)
    finally:
        db.close()

    def override_get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    settings_override({"auth.enabled": True})
    with TestClient(app) as test_client:
        yield test_client, {"Authorization": f"Bearer {token}"}, ids
    app.dependency_overrides.clear()


def test_knowledge_routes_require_token(client):
    test_client, _, ids = client
    assert test_client.get("/api/knowledge/procedures").status_code == 401
    path = f"/api/knowledge/procedures/{ids['procedure_id']}"
    assert test_client.get(path).status_code == 401


def test_list_procedures(client):
    test_client, headers, ids = client
    body = test_client.get("/api/knowledge/procedures", headers=headers).json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == ids["procedure_id"]
    assert item["number"] == "1.061"
    assert item["counts"]["facts"] == 3
    assert item["counts"]["records"] == 2


def test_list_procedures_search_and_paging(client):
    test_client, headers, _ = client
    body = test_client.get(
        "/api/knowledge/procedures", headers=headers, params={"q": "khong co"}
    ).json()
    assert body == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_procedure_profile(client):
    test_client, headers, ids = client
    response = test_client.get(f"/api/knowledge/procedures/{ids['procedure_id']}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["procedure"]["number"] == "1.061"
    assert body["standards"][0]["name_vi"] == "Áp kế píttông tiêu chuẩn"
    assert body["records"]["total"] == 2


def test_unknown_procedure_is_404(client):
    test_client, headers, _ = client
    response = test_client.get("/api/knowledge/procedures/999999", headers=headers)
    assert response.status_code == 404
