"""Nạp config/settings.yaml: thay ${VAR:-mặc_định} từ môi trường rồi kiểm schema.

Đây là chỗ DUY NHẤT trong backend đọc biến môi trường để lấy cấu hình. Code khác gọi
``get_settings()`` tại thời điểm dùng (không lưu vào hằng module lúc import), nên test
đổi cấu hình bằng fixture ``settings_override`` thay vì monkeypatch từng hằng số.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import ValidationError

from core.schema import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
SETTINGS_FILE_ENV = "QTKD_SETTINGS_FILE"
LOAD_DOTENV_ENV = "QTKD_LOAD_DOTENV"
_PATH_SECTION = "paths"
_ENV_REF_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)(?::-([^}]*))?\}")

# Fixture settings_override đặt biến này; get_settings() trả nó nếu có.
_override: Settings | None = None


class SettingsError(RuntimeError):
    """settings.yaml sai cú pháp, thiếu biến môi trường bắt buộc hoặc sai schema."""


def interpolate(value: Any, env: Mapping[str, str]) -> Any:
    """Thay mọi ${VAR} / ${VAR:-mặc_định} trong chuỗi, đi đệ quy qua dict và list."""
    if isinstance(value, dict):
        return {key: interpolate(item, env) for key, item in value.items()}
    if isinstance(value, list):
        return [interpolate(item, env) for item in value]
    if isinstance(value, str):
        return _ENV_REF_RE.sub(lambda match: _resolve(match, env), value)
    return value


def _resolve(match: re.Match[str], env: Mapping[str, str]) -> str:
    name, default = match.group(1), match.group(2)
    value = env.get(name)
    if value:
        return value
    if default is None:
        raise SettingsError(f"Thiếu biến môi trường bắt buộc {name}")
    return default


def load_yaml(path: Path, env: Mapping[str, str]) -> Any:
    """Đọc một file YAML cấu hình và thay biến môi trường."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SettingsError(f"Không đọc được {path}: {exc}") from exc
    return interpolate(raw, env)


def _absolute_paths(raw: dict[str, Any]) -> dict[str, Any]:
    paths = {
        key: str(value if Path(value).is_absolute() else REPO_ROOT / value)
        for key, value in (raw.get(_PATH_SECTION) or {}).items()
    }
    return {**raw, _PATH_SECTION: paths}


def _default_env() -> Mapping[str, str]:
    if os.environ.get(LOAD_DOTENV_ENV, "1") != "0":
        load_dotenv(REPO_ROOT / ".env", override=False)
    return os.environ


def load_settings(path: Path | None = None, env: Mapping[str, str] | None = None) -> Settings:
    """Nạp + kiểm settings. ``env=None`` dùng os.environ (sau khi đọc .env nếu có)."""
    source = _default_env() if env is None else env
    settings_path = path or Path(source.get(SETTINGS_FILE_ENV) or CONFIG_DIR / "settings.yaml")
    raw = load_yaml(settings_path, source)
    if not isinstance(raw, dict):
        raise SettingsError(f"{settings_path} phải là một mapping YAML")
    try:
        return Settings.model_validate(_absolute_paths(raw))
    except ValidationError as exc:
        raise SettingsError(f"{settings_path} không hợp lệ:\n{exc}") from exc


@lru_cache(maxsize=1)
def _cached() -> Settings:
    return load_settings()


def get_settings() -> Settings:
    """Settings của tiến trình (nạp một lần); test override qua fixture settings_override."""
    return _override if _override is not None else _cached()


def reset_settings() -> None:
    """Bỏ cache để lần gọi sau đọc lại file + môi trường."""
    _cached.cache_clear()


def with_overrides(settings: Settings, overrides: Mapping[str, Any]) -> Settings:
    """Bản sao settings với vài khóa đổi giá trị, khóa dạng "retrieval.top_k"."""
    data = settings.model_dump()
    for dotted, value in overrides.items():
        node = data
        *parents, leaf = dotted.split(".")
        for part in parents:
            if not isinstance(node.get(part), dict):
                raise SettingsError(f"Khóa cấu hình không tồn tại: {dotted}")
            node = node[part]
        if leaf not in node:
            raise SettingsError(f"Khóa cấu hình không tồn tại: {dotted}")
        node[leaf] = value
    try:
        return Settings.model_validate(data)
    except ValidationError as exc:
        raise SettingsError(f"Override không hợp lệ:\n{exc}") from exc


def _lookup(settings: Settings, dotted: str) -> Any:
    node: Any = settings
    for part in dotted.split("."):
        if not hasattr(node, part):
            raise SettingsError(f"Khóa cấu hình không tồn tại: {dotted}")
        node = getattr(node, part)
    return node


def main(argv: list[str] | None = None) -> int:
    """CLI cho shell/Makefile: ``python -m core.settings_loader get models.llm_chat``."""
    parser = argparse.ArgumentParser(prog="python -m core.settings_loader")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("get").add_argument("key")
    args = parser.parse_args(argv)
    print(_lookup(get_settings(), args.key))
    return 0


if __name__ == "__main__":
    sys.exit(main())
