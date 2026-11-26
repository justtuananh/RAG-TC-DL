"""API tự phục vụ bản build React: một cổng duy nhất, không cần nginx."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import create_app


@pytest.fixture
def client(tmp_path, settings_override):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id='root'></div>", encoding="utf-8")
    (dist / "assets" / "app-abc123.js").write_text("console.log(1)", encoding="utf-8")
    settings_override({"paths.frontend_dist": str(dist), "app.startup_checks": False})
    with TestClient(create_app()) as test_client:
        yield test_client


def test_root_serves_index(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "id='root'" in response.text
    assert response.headers["cache-control"] == "no-cache"


def test_client_route_falls_back_to_index(client):
    """Tải lại /ho-so/1 phải trả index để router phía trình duyệt tự xử lý."""

    response = client.get("/ho-so/1")

    assert response.status_code == 200
    assert "id='root'" in response.text


def test_asset_is_served_with_long_cache(client):
    response = client.get("/assets/app-abc123.js")

    assert response.status_code == 200
    assert response.text == "console.log(1)"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_unknown_api_path_stays_an_api_404(client):
    response = client.get("/api/khong-ton-tai")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_missing_build_returns_clear_404(tmp_path, settings_override):
    settings_override(
        {"paths.frontend_dist": str(tmp_path / "chua-build"), "app.startup_checks": False}
    )

    with TestClient(create_app()) as test_client:
        response = test_client.get("/")

    assert response.status_code == 404
    assert response.json()["detail"] == "Frontend chưa được build"


def test_path_traversal_cannot_escape_dist(client):
    response = client.get("/../config/settings.yaml")

    # Starlette chuẩn hoá đường dẫn trước khi khớp route; nếu lọt tới handler thì
    # phải rơi về index, tuyệt đối không trả nội dung ngoài dist.
    assert response.status_code == 200
    assert "id='root'" in response.text
