#!/usr/bin/env python
"""Run Alembic migrations from the repository root."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parent.parent


def _config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "db" / "migrations"))
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
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
