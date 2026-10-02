"""configure_logging: đọc logging.yaml, tạo thư mục log, gọi lại không nhân đôi handler."""

import logging

from core import logging_setup


def _flush():
    for handler in logging.getLogger().handlers:
        handler.flush()


def test_configure_logging_writes_to_configured_file(tmp_path):
    log_file = tmp_path / "sub" / "app.log"
    logging_setup.configure_logging(env={"LOG_FILE": str(log_file), "LOG_LEVEL": "INFO"})
    logging.getLogger("qtkd.test").info("xin chào")
    _flush()
    assert "xin chào" in log_file.read_text(encoding="utf-8")


def test_configure_logging_is_idempotent(tmp_path):
    env = {"LOG_FILE": str(tmp_path / "app.log")}
    logging_setup.configure_logging(env=env)
    first = len(logging.getLogger().handlers)
    logging_setup.configure_logging(env=env)
    assert len(logging.getLogger().handlers) == first


def test_level_comes_from_env(tmp_path):
    logging_setup.configure_logging(
        env={"LOG_FILE": str(tmp_path / "a.log"), "LOG_LEVEL": "WARNING"}
    )
    assert logging.getLogger().level == logging.WARNING


def test_relative_log_file_resolves_against_repo_root(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_setup, "REPO_ROOT", tmp_path)
    logging_setup.configure_logging(env={"LOG_FILE": "logs/x.log"})
    assert (tmp_path / "logs").is_dir()
