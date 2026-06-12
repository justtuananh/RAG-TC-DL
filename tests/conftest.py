"""Fixtures + cấu hình chung cho harness QTKĐ.

- Tự gán marker theo thư mục: tests/unit→unit, tests/integration→integration, tests/ruby→ruby.
- Guard mạng cho unit test: chặn socket thật để lời gọi quên-mock FAIL tức thì,
  thay vì treo 60–300s theo timeout của `requests`.
- reset_module_singletons: dọn các singleton lazy của retrieval/* giữa mỗi test.
- require_services: skip test integration khi service chưa sẵn sàng.

Các module nguồn (retrieval/ index/ app / eval.run_eval / scripts) import được nhờ
pythonpath=["."] khai trong pyproject.toml.
"""

from __future__ import annotations

import importlib
import socket
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_DATA = Path(__file__).resolve().parent / "data"

# Singleton lazy rò rỉ giữa các test (và là staleness bug tiềm ẩn trong app thật).
_SINGLETONS = {
    "retrieval.retriever": ["_client"],
    "retrieval.bm25_index": ["_bm25", "_chunks"],
    "retrieval.router": ["_number_to_stem"],
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
