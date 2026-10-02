"""Bật logging cho mọi entrypoint (API, CLI index, eval) từ config/logging.yaml."""

from __future__ import annotations

import logging
import logging.config
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.settings_loader import CONFIG_DIR, REPO_ROOT, load_yaml

LOGGING_FILE_ENV = "QTKD_LOGGING_FILE"


def _resolve_file_handlers(config: dict[str, Any]) -> dict[str, Any]:
    handlers = {}
    for name, handler in (config.get("handlers") or {}).items():
        filename = handler.get("filename")
        if filename:
            path = Path(filename)
            path = path if path.is_absolute() else REPO_ROOT / path
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = {**handler, "filename": str(path)}
        handlers[name] = handler
    return {**config, "handlers": handlers}


def configure_logging(path: Path | None = None, env: Mapping[str, str] | None = None) -> None:
    """Áp logging.yaml; gọi lại an toàn (đóng handler cũ của root trước khi áp)."""
    source = os.environ if env is None else env
    config_path = path or Path(source.get(LOGGING_FILE_ENV) or CONFIG_DIR / "logging.yaml")
    config = _resolve_file_handlers(load_yaml(config_path, source))
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    logging.config.dictConfig(config)
