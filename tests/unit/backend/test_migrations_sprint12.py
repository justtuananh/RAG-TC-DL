"""Migration 012: trường đầu mục biên bản + ``cells`` + phạm vi đo của thiết bị (Pha R).

Test lên/xuống trên SQLite sạch theo mẫu ``test_migrations_sprint11.py``.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect, text

from scripts.migrate import _config

NEW_REVISION = "012_record_fields"
PREVIOUS_REVISION = "011_nas_catalogs"


def _run(url: str, action: str, target: str) -> None:
    config = _config()
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    if action == "upgrade":
        command.upgrade(config, target)
    else:
        command.downgrade(config, target)


def _state(url: str) -> tuple[set[str], set[str], set[str], set[str]]:
    """``(views, tables, cột v_record_detail, cột measurement_point)``."""
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        detail = {column["name"] for column in inspector.get_columns("v_record_detail")}
        points = {column["name"] for column in inspector.get_columns("measurement_point")}
        return (
            set(inspector.get_view_names()),
            set(inspector.get_table_names()),
            detail,
            points,
        )
    finally:
        engine.dispose()


def test_record_field_migration_up_then_down_on_sqlite(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'sprint12_mig.db'}"
    monkeypatch.setenv("DATABASE_URL", url)

    _run(url, "upgrade", "head")
    views, tables, detail, points = _state(url)
    assert "v_record_field" in views
    assert "record_field" in tables
    assert {"range_field_id", "range_source", "range_text", "accuracy_field_id"} <= detail
    assert "cells" in points

    _run(url, "downgrade", PREVIOUS_REVISION)
    views, tables, detail, points = _state(url)
    assert "v_record_field" not in views
    assert "record_field" not in tables
    assert "range_field_id" not in detail
    assert "cells" not in points
    # View Sprint M vẫn dùng được sau khi hạ cấp.
    assert {"v_record_detail", "v_measurement_detail"} <= views

    _run(url, "upgrade", "head")
    views, tables, _, _ = _state(url)
    assert "v_record_field" in views


def test_head_revision_is_record_field_migration(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'sprint12_head.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    _run(url, "upgrade", "head")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            revision = connection.execute(
                text("select version_num from alembic_version")
            ).scalar_one()
    finally:
        engine.dispose()
    assert revision == NEW_REVISION
