"""Migration 013: ``v_procedure`` lộ tên tài liệu gốc cho trang Hồ sơ QTKĐ.

Test lên/xuống trên SQLite sạch theo mẫu ``test_migrations_sprint12.py``.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect, text

from core import settings_loader
from scripts.migrate import _config

NEW_REVISION = "013_procedure_document"
PREVIOUS_REVISION = "012_record_fields"
DOCUMENT_COLUMNS = {"document_file_stem", "document_name"}


def _run(url: str, action: str, target: str) -> None:
    config = _config()
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    if action == "upgrade":
        command.upgrade(config, target)
    else:
        command.downgrade(config, target)


def _procedure_columns(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return {column["name"] for column in inspect(engine).get_columns("v_procedure")}
    finally:
        engine.dispose()


def test_procedure_document_migration_up_then_down_on_sqlite(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'sprint13_mig.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    settings_loader.reset_settings()

    _run(url, "upgrade", "head")
    assert DOCUMENT_COLUMNS <= _procedure_columns(url)

    _run(url, "downgrade", PREVIOUS_REVISION)
    columns = _procedure_columns(url)
    assert not DOCUMENT_COLUMNS & columns
    assert {"number", "device_type_name", "quantity_name"} <= columns

    _run(url, "upgrade", "head")
    assert DOCUMENT_COLUMNS <= _procedure_columns(url)


def test_head_revision_is_procedure_document_migration(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'sprint13_head.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    settings_loader.reset_settings()
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
