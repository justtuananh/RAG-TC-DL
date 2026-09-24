"""Migration 006 lên/xuống trên SQLite sạch — bảng hồ sơ + view đã duyệt."""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect

from scripts.migrate import _config

NEW_TABLES = {"device", "calibration_record", "measurement_point"}
NEW_VIEWS = {"v_calibration_record", "v_measurement_point"}


def _run(url: str, action: str, target: str) -> None:
    config = _config()
    config.set_main_option("sqlalchemy.url", url)
    if action == "upgrade":
        command.upgrade(config, target)
    else:
        command.downgrade(config, target)


def _inspect(url: str):
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        return set(inspector.get_table_names()), set(inspector.get_view_names())
    finally:
        engine.dispose()


def test_records_migration_up_then_down(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'sprint7_mig.db'}"
    monkeypatch.setenv("DATABASE_URL", url)

    _run(url, "upgrade", "head")
    tables, views = _inspect(url)
    assert NEW_TABLES <= tables
    assert NEW_VIEWS <= views

    _run(url, "downgrade", "005_review_indexes")
    tables, views = _inspect(url)
    assert not (NEW_TABLES & tables)
    assert not (NEW_VIEWS & views)
    # Bảng tri thức vẫn còn sau khi gỡ bảng hồ sơ.
    assert "extraction" in tables

    _run(url, "upgrade", "head")
    tables, views = _inspect(url)
    assert NEW_TABLES <= tables
    assert NEW_VIEWS <= views
