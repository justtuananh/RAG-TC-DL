"""Migration 008 lên/xuống trên SQLite sạch — view tham chiếu chat số liệu (Sprint 9)."""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect

from scripts.migrate import _config

NEW_VIEWS = {"v_quantity", "v_device_type", "v_procedure"}


def _run(url: str, action: str, target: str) -> None:
    config = _config()
    config.set_main_option("sqlalchemy.url", url)
    if action == "upgrade":
        command.upgrade(config, target)
    else:
        command.downgrade(config, target)


def _views(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_view_names())
    finally:
        engine.dispose()


def test_reference_views_migration_up_then_down(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'sprint9_mig.db'}"
    monkeypatch.setenv("DATABASE_URL", url)

    _run(url, "upgrade", "head")
    views = _views(url)
    assert NEW_VIEWS <= views
    # View Sprint 8 vẫn còn.
    assert {"v_record_detail", "v_procedure_fact"} <= views

    _run(url, "downgrade", "007_query_views")
    views = _views(url)
    assert not (NEW_VIEWS & views)
    assert {"v_record_detail", "v_procedure_fact"} <= views

    _run(url, "upgrade", "head")
    assert NEW_VIEWS <= _views(url)
