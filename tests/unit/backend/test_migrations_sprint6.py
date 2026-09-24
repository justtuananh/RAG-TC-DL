"""Migration 005 lên/xuống trên SQLite sạch — index cho hàng đợi duyệt."""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect

from scripts.migrate import _config

NEW_INDEXES = {"ix_extraction_extractor", "ix_extraction_confidence"}


def _run(url: str, action: str, target: str) -> None:
    config = _config()
    config.set_main_option("sqlalchemy.url", url)
    if action == "upgrade":
        command.upgrade(config, target)
    else:
        command.downgrade(config, target)


def _index_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return {index["name"] for index in inspect(engine).get_indexes("extraction")}
    finally:
        engine.dispose()


def test_review_indexes_up_then_down(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'sprint6_mig.db'}"
    monkeypatch.setenv("DATABASE_URL", url)

    _run(url, "upgrade", "head")
    assert NEW_INDEXES <= _index_names(url)

    _run(url, "downgrade", "004_create_extraction")
    assert not (NEW_INDEXES & _index_names(url))
    # Bảng extraction vẫn còn sau khi gỡ index.
    engine = create_engine(url)
    try:
        assert "extraction" in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    _run(url, "upgrade", "head")
    assert NEW_INDEXES <= _index_names(url)
