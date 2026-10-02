"""Migration 009: đồng bộ sequence id sau id tường minh (B8).

Trên SQLite migration là no-op (không có sequence); test lên/xuống theo mẫu
``test_migrations_sprint9.py``. Phần logic Postgres được kiểm bằng bind giả để
không cần Docker.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, inspect, text

from core import settings_loader
from scripts.migrate import _config

MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "db"
    / "migrations"
    / "versions"
    / "009_fix_id_sequences.py"
)
NEW_REVISION = "009_fix_id_sequences"


def _load_migration():
    spec = importlib.util.spec_from_file_location("mig_009", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeBind:
    """Bind giả ghi lại câu lệnh để kiểm nhánh Postgres/SQLite."""

    def __init__(self, dialect_name: str) -> None:
        self.dialect = type("_Dialect", (), {"name": dialect_name})()
        self.calls: list[str] = []

    def exec_driver_sql(self, statement: str) -> None:
        self.calls.append(statement)


def _run(url: str, action: str, target: str) -> None:
    config = _config()
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    if action == "upgrade":
        command.upgrade(config, target)
    else:
        command.downgrade(config, target)


def _revision(url: str) -> str:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return connection.execute(text("select version_num from alembic_version")).scalar_one()
    finally:
        engine.dispose()


def _table_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_sync_sequences_postgres_targets_seeded_tables():
    module = _load_migration()
    bind = _FakeBind("postgresql")
    module._sync_sequences(bind)

    assert len(bind.calls) == 3
    for table in ("quantity", "unit", "device_type"):
        assert any(table in statement for statement in bind.calls)
    assert all("setval(pg_get_serial_sequence" in statement for statement in bind.calls)
    assert all("MAX(id)" in statement for statement in bind.calls)


def test_sync_sequences_sqlite_is_noop():
    module = _load_migration()
    bind = _FakeBind("sqlite")
    module._sync_sequences(bind)
    assert bind.calls == []


def test_sequence_migration_up_then_down_on_sqlite(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'seq_mig.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    settings_loader.reset_settings()

    # Nhắm đúng revision của migration 009 (head hiện tại đã là 010).
    _run(url, "upgrade", NEW_REVISION)
    assert _revision(url) == NEW_REVISION
    assert {"quantity", "unit", "device_type"} <= _table_names(url)

    # Downgrade là no-op nhưng phải lùi được revision.
    _run(url, "downgrade", "008_reference_views")
    assert _revision(url) == "008_reference_views"
    assert {"quantity", "unit", "device_type"} <= _table_names(url)

    _run(url, "upgrade", NEW_REVISION)
    assert _revision(url) == NEW_REVISION
