"""Migration 003 lên/xuống trên SQLite sạch — không cần Docker.

Cổng Sprint 3: migration đi và lùi được, seed đúng số dòng khung khái niệm.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect, text

from scripts.migrate import _config

NEW_TABLES = {"quantity", "unit", "device_type", "procedure"}


def _upgrade(url: str) -> None:
    config = _config()
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


def _downgrade(url: str, target: str) -> None:
    config = _config()
    config.set_main_option("sqlalchemy.url", url)
    command.downgrade(config, target)


def _table_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _count(url: str, table: str) -> int:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return connection.execute(text(f"select count(*) from {table}")).scalar_one()
    finally:
        engine.dispose()


def test_migration_up_down_up(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'qtkd_mig.db'}"
    monkeypatch.setenv("DATABASE_URL", url)

    _upgrade(url)
    tables = _table_names(url)
    assert NEW_TABLES <= tables
    assert _count(url, "quantity") == 6
    assert _count(url, "unit") == 27
    assert _count(url, "device_type") == 7

    _downgrade(url, "base")
    tables = _table_names(url)
    assert not (NEW_TABLES & tables)
    assert "document" not in tables
    assert "app_user" not in tables

    _upgrade(url)
    tables = _table_names(url)
    assert NEW_TABLES <= tables
    assert _count(url, "unit") == 27


def test_migration_downgrade_one_step_keeps_document(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'qtkd_mig_step.db'}"
    monkeypatch.setenv("DATABASE_URL", url)

    _upgrade(url)
    _downgrade(url, "002_create_document")
    tables = _table_names(url)
    assert not (NEW_TABLES & tables)
    assert "document" in tables

    _upgrade(url)
    assert NEW_TABLES <= _table_names(url)
