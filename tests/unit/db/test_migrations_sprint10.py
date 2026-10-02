"""Migration 010: đơn vị sai số riêng + view điểm đo có đơn vị sai số.

Test lên/xuống trên SQLite sạch theo mẫu ``test_migrations_sprint9*.py``; phần
chèn đơn vị ``%`` idempotent được kiểm bằng gọi trực tiếp helper của migration.
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
    / "010_measurement_error_unit.py"
)
NEW_REVISION = "010_measurement_error_unit"


def _load_migration():
    spec = importlib.util.spec_from_file_location("mig_010", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _columns(url: str, name: str) -> set[str]:
    engine = create_engine(url)
    try:
        return {column["name"] for column in inspect(engine).get_columns(name)}
    finally:
        engine.dispose()


def _scalar(url: str, sql: str) -> int:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return connection.execute(text(sql)).scalar_one()
    finally:
        engine.dispose()


def test_error_unit_migration_up_then_down_on_sqlite(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'sprint10_mig.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    settings_loader.reset_settings()

    _run(url, "upgrade", NEW_REVISION)
    assert _revision(url) == NEW_REVISION
    assert "error_unit_id" in _columns(url, "measurement_point")
    view_columns = _columns(url, "v_measurement_detail")
    assert {"error_unit_id", "error_unit_code", "error_unit_name", "unit_code"} <= view_columns
    # Đơn vị "%" phải có mặt để phân giải được ``error_unit_text`` của bảng A.4.
    assert _scalar(url, "SELECT COUNT(*) FROM unit WHERE code = '%'") == 1
    assert _scalar(url, "SELECT COUNT(*) FROM quantity WHERE code = 'ratio'") == 1

    _run(url, "downgrade", "009_fix_id_sequences")
    assert _revision(url) == "009_fix_id_sequences"
    assert "error_unit_id" not in _columns(url, "measurement_point")
    assert "error_unit_id" not in _columns(url, "v_measurement_detail")

    _run(url, "upgrade", NEW_REVISION)
    assert _revision(url) == NEW_REVISION
    assert "error_unit_id" in _columns(url, "v_measurement_detail")


def test_ensure_percent_unit_is_idempotent_and_repairs_missing(tmp_path):
    from db.models import Base

    module = _load_migration()
    engine = create_engine(f"sqlite:///{tmp_path / 'percent.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        module._ensure_percent_unit(connection)
        module._ensure_percent_unit(connection)
        count = connection.execute(text("SELECT COUNT(*) FROM unit WHERE code = '%'")).scalar_one()
        assert count == 1
        # Xóa bản ghi rồi chèn bù: nhánh "còn thiếu" cũng idempotent.
        connection.execute(text("DELETE FROM unit WHERE code = '%'"))
        connection.execute(text("DELETE FROM quantity WHERE code = 'ratio'"))
        module._ensure_percent_unit(connection)
        count = connection.execute(text("SELECT COUNT(*) FROM unit WHERE code = '%'")).scalar_one()
        assert count == 1
    engine.dispose()
