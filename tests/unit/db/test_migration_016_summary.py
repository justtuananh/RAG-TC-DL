"""Migration 016: bảng ``document_summary`` lên/xuống trên SQLite sạch - không cần Docker."""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect

from core import settings_loader
from scripts.migrate import _config


def _run(url: str, action, target: str) -> None:
    config = _config()
    config.set_main_option("sqlalchemy.url", url)
    action(config, target)


def _columns(url: str) -> set[str] | None:
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        if "document_summary" not in inspector.get_table_names():
            return None
        return {column["name"] for column in inspector.get_columns("document_summary")}
    finally:
        engine.dispose()


def test_document_summary_table_up_and_down(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'qtkd_016.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    settings_loader.reset_settings()

    _run(url, command.upgrade, "head")
    assert {"document_id", "status", "text", "generated_text", "warnings", "source_sha256", "revision"} <= _columns(url)

    _run(url, command.downgrade, "015_document_superseded")
    assert _columns(url) is None

    _run(url, command.upgrade, "head")
    assert _columns(url) is not None
