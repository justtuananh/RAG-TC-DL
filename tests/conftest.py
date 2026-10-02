"""Fixtures + cấu hình chung cho harness QTKĐ.

- Tự gán marker theo thư mục: tests/unit→unit, tests/integration→integration, tests/ruby→ruby.
- Guard mạng cho unit test: chặn socket thật để lời gọi quên-mock FAIL tức thì,
  thay vì treo 60–300s theo timeout của `requests`.
- reset_module_singletons: dọn các singleton lazy của retrieval/* giữa mỗi test.
- require_services: skip test integration khi service chưa sẵn sàng.

Các package nguồn (api, auth, catalogs, core, db, embedding, evaluation, ingestion, knowledge,
llm, query, records, reranking, retrieval, review, scoring, scripts, ui, vectorstore) import
được nhờ pythonpath=["."] khai trong pyproject.toml.
"""

from __future__ import annotations

import importlib
import os
import socket
import sys
from pathlib import Path

import pytest

# Test không phụ thuộc .env của máy dev và không gọi service lúc khởi động.
os.environ["QTKD_LOAD_DOTENV"] = "0"
os.environ["QTKD_STARTUP_CHECKS"] = "false"

import tempfile

os.environ.setdefault("LOG_FILE", str(Path(tempfile.gettempdir()) / "qtkd-test.log"))

_ROOT = Path(__file__).resolve().parent.parent
_DATA = Path(__file__).resolve().parent / "data"

# Singleton lazy rò rỉ giữa các test (và là staleness bug tiềm ẩn trong app thật).
_SINGLETONS = {
    "vectorstore.qdrant": ["_client"],
    "vectorstore.hybrid_index": ["_bm25", "_chunks"],
    "retrieval.router": ["_number_to_stem", "_device_aliases"],
}


# ── Tự gán marker theo thư mục ────────────────────────────────────────────────


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = str(item.fspath).replace("\\", "/")
        if "/tests/unit/" in path:
            item.add_marker("unit")
        elif "/tests/integration/" in path:
            item.add_marker("integration")
        elif "/tests/ruby/" in path:
            item.add_marker("ruby")


def _is_live(request) -> bool:
    """Test có chạm tài nguyên thật (service/Ruby) → KHÔNG áp guard/reset của unit."""
    return any(
        request.node.get_closest_marker(m) for m in ("integration", "services", "ruby", "gpu")
    )


# ── Guard mạng (chỉ áp cho unit) ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _no_real_network(request, monkeypatch):
    if _is_live(request):
        return

    def _guard(self, address, *args, **kwargs):
        raise RuntimeError(
            f"Unit test thử mở kết nối mạng thật tới {address!r} — hãy mock nó "
            f"(responses cho requests, hoặc patch hàm qdrant)."
        )

    monkeypatch.setattr(socket.socket, "connect", _guard, raising=True)
    monkeypatch.setattr(socket.socket, "connect_ex", _guard, raising=True)


# ── Reset singleton lazy của retrieval/* ──────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_module_singletons(request):
    if _is_live(request):
        yield
        return

    def _reset():
        for mod_name, attrs in _SINGLETONS.items():
            try:
                mod = importlib.import_module(mod_name)
            except Exception:
                continue
            for attr in attrs:
                if hasattr(mod, attr):
                    setattr(mod, attr, None)

    _reset()
    yield
    _reset()


@pytest.fixture(autouse=True)
def _fresh_settings():
    """Mỗi test bắt đầu với settings đọc lại từ file + môi trường hiện tại."""
    from core import settings_loader

    settings_loader.reset_settings()
    security = sys.modules.get("auth.security")
    if security is not None:
        security.jwt_secret.cache_clear()
    yield
    settings_loader.reset_settings()
    if security is not None:
        security.jwt_secret.cache_clear()


@pytest.fixture
def settings_override(monkeypatch):
    """Đổi vài khóa cấu hình trong một test: settings_override({"retrieval.top_k": 5})."""
    from core import settings_loader

    def apply(overrides: dict):
        new = settings_loader.with_overrides(settings_loader.get_settings(), overrides)
        monkeypatch.setattr(settings_loader, "_override", new)
        return new

    return apply


# ── Đường dẫn tiện dụng ───────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return _ROOT


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return _DATA


@pytest.fixture(scope="session")
def build_dir() -> Path:
    return _ROOT / "build" / "spike_a"


# ── Skip integration khi service chưa sẵn sàng ────────────────────────────────


@pytest.fixture
def require_services():
    """Trả callable _require(*names); skip nếu service nào trong names chưa lên.

    Dùng: require_services("qdrant", "embedding", "reranker")  hoặc không tham số = cả 4.
    """
    from scripts.healthcheck import health_urls, ping

    urls = health_urls()

    def _require(*names: str) -> None:
        names = names or tuple(urls)
        down = [n for n in names if not ping(urls[n])]
        if down:
            pytest.skip(
                f"Service chưa sẵn sàng: {', '.join(down)}. Chạy `make up` trước khi chạy test integration."
            )

    return _require
