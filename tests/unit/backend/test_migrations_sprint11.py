"""Migration 011: bốn bảng danh mục NAS + view đã duyệt (Pha D1).

Test lên/xuống trên SQLite sạch theo mẫu ``test_migrations_sprint10.py``.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect

from core import settings_loader
from scripts.migrate import _config

NEW_VIEWS = {"v_lab_standard", "v_inspector", "v_procedure_catalog", "v_capability"}
NEW_TABLES = {"lab_standard", "inspector", "procedure_catalog", "capability"}
NEW_REVISION = "011_nas_catalogs"


def _run(url: str, action: str, target: str) -> None:
    config = _config()
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    if action == "upgrade":
        command.upgrade(config, target)
    else:
        command.downgrade(config, target)


def _inspect(url: str):
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        return set(inspector.get_view_names()), set(inspector.get_table_names())
    finally:
        engine.dispose()


def test_catalog_migration_up_then_down_on_sqlite(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'sprint11_mig.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    settings_loader.reset_settings()

    _run(url, "upgrade", "head")
    views, tables = _inspect(url)
    assert NEW_VIEWS <= views
    assert NEW_TABLES <= tables
    # View các sprint trước vẫn còn.
    assert {"v_record_detail", "v_procedure_fact", "v_procedure"} <= views

    _run(url, "downgrade", "010_measurement_error_unit")
    views, tables = _inspect(url)
    assert not (NEW_VIEWS & views)
    assert not (NEW_TABLES & tables)
    assert {"v_record_detail", "v_procedure"} <= views

    _run(url, "upgrade", "head")
    views, _ = _inspect(url)
    assert NEW_VIEWS <= views


def test_catalog_migration_indexes_procedure_number(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'sprint11_idx.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    settings_loader.reset_settings()
    _run(url, "upgrade", "head")
    engine = create_engine(url)
    try:
        names = {index["name"] for index in inspect(engine).get_indexes("procedure_catalog")}
    finally:
        engine.dispose()
    assert "ix_procedure_catalog_procedure_number" in names


def test_catalog_migration_is_in_head_chain():
    # Head đi tiếp sau 011 (Pha R); 011 phải còn nằm trên chuỗi revision.
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(_config())
    chain = {revision.revision for revision in script.walk_revisions("base", "heads")}
    assert NEW_REVISION in chain
