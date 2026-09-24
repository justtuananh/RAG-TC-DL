"""Migration 007 lên/xuống trên SQLite sạch — view bề mặt tra cứu (Sprint 8)."""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect

from scripts.migrate import _config

NEW_VIEWS = {"v_unit", "v_extraction", "v_record_detail", "v_measurement_detail"}


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


def test_query_views_migration_up_then_down(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'sprint8_mig.db'}"
    monkeypatch.setenv("DATABASE_URL", url)

    _run(url, "upgrade", "head")
    views = _views(url)
    assert NEW_VIEWS <= views
    # View cũ vẫn còn.
    assert {"v_procedure_fact", "v_calibration_record"} <= views

    _run(url, "downgrade", "006_create_records")
    views = _views(url)
    assert not (NEW_VIEWS & views)
    assert {"v_procedure_fact", "v_calibration_record"} <= views

    _run(url, "upgrade", "head")
    assert NEW_VIEWS <= _views(url)
