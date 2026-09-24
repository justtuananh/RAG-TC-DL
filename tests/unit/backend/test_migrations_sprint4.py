"""Migration 004 lên/xuống trên SQLite sạch — bảng trích xuất + view đã duyệt."""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect

from scripts.migrate import _config

NEW_TABLES = {"extraction", "procedure_fact", "procedure_standard", "term"}
NEW_VIEWS = {"v_procedure_fact", "v_procedure_standard", "v_term"}


def _upgrade(url: str) -> None:
    config = _config()
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


def _downgrade(url: str, target: str) -> None:
    config = _config()
    config.set_main_option("sqlalchemy.url", url)
    command.downgrade(config, target)


def _names(url: str) -> tuple[set[str], set[str]]:
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        return set(inspector.get_table_names()), set(inspector.get_view_names())
    finally:
        engine.dispose()


def test_migration_up_down_up(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'sprint4_mig.db'}"
    monkeypatch.setenv("DATABASE_URL", url)

    _upgrade(url)
    tables, views = _names(url)
    assert NEW_TABLES <= tables
    assert NEW_VIEWS <= views

    _downgrade(url, "base")
    tables, views = _names(url)
    assert not (NEW_TABLES & tables)
    assert not (NEW_VIEWS & views)
    assert "document" not in tables
    assert "procedure" not in tables

    _upgrade(url)
    tables, views = _names(url)
    assert NEW_TABLES <= tables
    assert NEW_VIEWS <= views


def test_downgrade_one_step_keeps_sprint3(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'sprint4_step.db'}"
    monkeypatch.setenv("DATABASE_URL", url)

    _upgrade(url)
    _downgrade(url, "003_create_measurement_framework")
    tables, views = _names(url)
    assert not (NEW_TABLES & tables)
    assert not (NEW_VIEWS & views)
    assert "procedure" in tables

    _upgrade(url)
    tables, views = _names(url)
    assert NEW_TABLES <= tables
    assert NEW_VIEWS <= views
