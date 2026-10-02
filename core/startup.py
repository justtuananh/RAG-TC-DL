"""Khởi động chung cho API và CLI: logging, kiểm cấu hình, kiểm service.

Service chưa lên chỉ cảnh báo (compose có thể bật API trước Qdrant/Ollama). Lệch chiều
vector giữa settings và collection thì dừng: truy hồi sẽ hỏng âm thầm. core không biết
Qdrant: nơi gọi truyền vào hàm đo số chiều (vector_size_probe).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from urllib.parse import urlsplit

import requests

from core.logging_setup import configure_logging
from core.schema import Settings
from core.settings_loader import get_settings

logger = logging.getLogger(__name__)

VectorSizeProbe = Callable[[str], int | None]
_DEV_DB_PASSWORD = "qtkd_password"
_PROBE_TIMEOUT_S = 2.0


class StartupError(RuntimeError):
    """Cấu hình không an toàn hoặc không khớp hạ tầng; không được chạy tiếp."""


def validate_security(settings: Settings) -> None:
    if settings.app.env != "production":
        return
    if settings.auth.enabled and settings.auth.jwt_secret_key is None:
        raise StartupError("production cần JWT_SECRET_KEY")
    uses_default_password = settings.database.password.get_secret_value() == _DEV_DB_PASSWORD
    if settings.database.url is None and uses_default_password:
        raise StartupError("production không được dùng POSTGRES_PASSWORD mặc định")


def _root(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def check_services(settings: Settings) -> dict[str, bool]:
    """Thử gọi từng service; trả trạng thái, cảnh báo service không phản hồi."""
    s = settings.services
    probes = {
        "embedding": _root(s.embedding_url) + "/health",
        "reranker": _root(s.rerank_url) + "/health",
        "qdrant": _root(s.qdrant_url),
        "ollama": _root(s.ollama_url),
    }
    status = {}
    for name, url in probes.items():
        try:
            status[name] = requests.get(url, timeout=_PROBE_TIMEOUT_S).ok
        except (OSError, requests.RequestException):
            status[name] = False
        if not status[name]:
            logger.warning("Service %s chưa phản hồi ở %s", name, url)
    return status


def check_vector_size(settings: Settings, probe: VectorSizeProbe) -> None:
    size = probe(settings.vectorstore.collection)
    expected = settings.models.embedding.vector_size
    if size is not None and size != expected:
        raise StartupError(
            f"Collection {settings.vectorstore.collection} có {size} chiều, settings khai {expected}"
        )


def startup(
    *, vector_size_probe: VectorSizeProbe | None = None, check_services_now: bool | None = None
) -> Settings:
    """Gọi một lần ở đầu mọi entrypoint (API lifespan, CLI)."""
    configure_logging()
    settings = get_settings()
    validate_security(settings)
    should_check = settings.app.startup_checks if check_services_now is None else check_services_now
    if should_check:
        status = check_services(settings)
        if vector_size_probe is not None and status.get("qdrant"):
            check_vector_size(settings, vector_size_probe)
    logger.info("Khởi động: env=%s, model chat=%s", settings.app.env, settings.llm_model("chat"))
    return settings
