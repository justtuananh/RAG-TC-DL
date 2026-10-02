#!/usr/bin/env python
"""Run Alembic migrations from the repository root."""

from __future__ import annotations

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config

from db.config import get_database_url

ROOT = Path(__file__).resolve().parent.parent


def _config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "db" / "migrations"))
    config.set_main_option("sqlalchemy.url", get_database_url().replace("%", "%%"))
    return config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run QTKĐ database migrations")
    parser.add_argument("command", choices=("upgrade", "downgrade"))
    parser.add_argument("target", nargs="?", default="head")
    args = parser.parse_args()
    if args.command == "upgrade":
        command.upgrade(_config(), args.target)
    else:
        command.downgrade(_config(), args.target)


if __name__ == "__main__":
    main()
