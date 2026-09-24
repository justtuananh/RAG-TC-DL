"""API bề mặt tra cứu dữ liệu + quyền + P3 (Sprint 8).

Chạy in-process: FastAPI TestClient + SQLite. Kiểm ma trận quyền (mọi vai trò đã
đăng nhập tra cứu được; thiếu token → 401), luồng dữ liệu, và bất biến P3: hồ sơ
``pending`` không lộ ra bất kỳ route nào.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

import api_server
import auth.dependencies as auth_deps
from auth.security import create_access_token, hash_password
from db import get_db
from db.models import AppUser, UserRole

PASSWORD = "correct-horse-battery"


@pytest.fixture
def users(data_factory):
    factory, ids = data_factory
    db = factory()
    try:
        for username, role in (
            ("admin", UserRole.ADMIN),
            ("duyet", UserRole.APPROVER),
            ("tech", UserRole.TECHNICIAN),
            ("viewer", UserRole.VIEWER),
        ):
            db.add(
                AppUser(
                    username=username,
                    full_name=username,
                    password_hash=hash_password(PASSWORD),
                    role=role,
                    is_active=1,
                )
            )
        db.commit()
        return {user.role.value: (user.id, user.username) for user in db.query(AppUser).all()}
    finally:
        db.close()


@pytest.fixture
def client(data_factory, users, monkeypatch):
    factory, _ = data_factory

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    api_server.app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(auth_deps, "AUTH_ENABLED", True)
    with TestClient(api_server.app) as test_client:
        yield test_client
    api_server.app.dependency_overrides.clear()


def _auth(users, role: str) -> dict:
    user_id, username = users[role]
    return {"Authorization": f"Bearer {create_access_token(user_id, username, role)}"}


def test_all_data_routes_require_token(client):
    assert client.get("/api/data/filters").status_code == 401
    assert client.get("/api/data/records").status_code == 401
    assert client.get("/api/data/records/1").status_code == 401
    assert client.get("/api/data/devices").status_code == 401
    assert client.get("/api/data/devices/1/history").status_code == 401
    assert client.get("/api/data/provenance?record_id=1").status_code == 401
    assert client.get("/api/data/records/export.xlsx").status_code == 401


@pytest.mark.parametrize("role", ["viewer", "technician", "approver", "admin"])
def test_all_roles_can_read(client, users, role):
    headers = _auth(users, role)
    assert client.get("/api/data/records", headers=headers).status_code == 200
    assert client.get("/api/data/filters", headers=headers).status_code == 200
    assert client.get("/api/data/devices", headers=headers).status_code == 200


def test_records_list_filters_and_pagination(client, users, data_factory):
    _, ids = data_factory
    headers = _auth(users, "viewer")
    body = client.get("/api/data/records", headers=headers).json()
    assert body["total"] == 2
    assert len(body["items"]) == 2

    body = client.get("/api/data/records", headers=headers, params={"verdict": "khong_dat"}).json()
    assert body["total"] == 1

    body = client.get("/api/data/records", headers=headers, params={"limit": 1, "offset": 1}).json()
    assert body["total"] == 2 and len(body["items"]) == 1

    body = client.get(
        "/api/data/records",
        headers=headers,
        params={"range_min": 0, "range_max": 100, "range_unit": "bar"},
    ).json()
    assert body["total"] == 2

    body = client.get(
        "/api/data/records", headers=headers, params={"procedure_id": ids["procedure_id"]}
    ).json()
    assert body["total"] == 2


def test_pending_record_hidden_through_api(client, users):
    headers = _auth(users, "viewer")
    body = client.get("/api/data/records", headers=headers, params={"search": "PENDING"}).json()
    assert body["total"] == 0
    history = client.get("/api/data/devices/by-serial/SN-PENDING", headers=headers)
    assert history.status_code == 404


def test_record_detail_and_provenance(client, users, data_factory):
    _, ids = data_factory
    headers = _auth(users, "approver")
    detail = client.get(f"/api/data/records/{ids['record_a_id']}", headers=headers).json()
    assert detail["serial_no"] == "SN-1"
    point = detail["measurements"][0]
    source = client.get(
        "/api/data/provenance",
        headers=headers,
        params={"measurement_id": point["id"], "field": "error"},
    ).json()
    assert source["value_text"] == "0,1"
    assert source["chunk_id"] == "chunk-record-a"
    assert source["section_path"] == "Phụ lục A"


def test_provenance_fact_and_record(client, users, data_factory):
    _, ids = data_factory
    headers = _auth(users, "viewer")
    fact = client.get(
        "/api/data/provenance", headers=headers, params={"fact_id": ids["range_fact_id"]}
    ).json()
    assert fact["kind"] == "fact"
    assert fact["value_text"] == "(0 ÷ 1600) bar"

    missing = client.get("/api/data/provenance", headers=headers, params={"fact_id": 999999})
    assert missing.status_code == 400


def test_devices_and_history(client, users, data_factory):
    _, ids = data_factory
    headers = _auth(users, "viewer")
    devices = client.get("/api/data/devices", headers=headers).json()
    assert devices["total"] == 1

    history = client.get(f"/api/data/devices/{ids['device_id']}/history", headers=headers).json()
    assert history["device"]["serial_no"] == "SN-1"
    assert len(history["records"]) == 2
    assert [point["error_value"] for point in history["trend"][0]["points"]] == [0.1, 0.8]

    by_serial = client.get("/api/data/devices/by-serial/SN-1", headers=headers).json()
    assert by_serial["device"]["id"] == ids["device_id"]


def test_export_xlsx_endpoint(client, users):
    headers = _auth(users, "viewer")
    response = client.get("/api/data/records/export.xlsx", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert "xl/worksheets/sheet1.xml" in archive.namelist()
    sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "SN-1" in sheet
    assert "SN-PENDING" not in sheet
    assert "Chunk nguồn" in sheet


def test_unknown_record_is_404(client, users):
    headers = _auth(users, "viewer")
    assert client.get("/api/data/records/999999", headers=headers).status_code == 404
    assert client.get("/api/data/devices/999999/history", headers=headers).status_code == 404
