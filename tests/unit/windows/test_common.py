"""Layout, .env và các tiện ích dùng chung của bộ cài Windows."""

from __future__ import annotations

import socket

from windows.common import (
    IS_WINDOWS,
    Layout,
    copy_missing,
    port_available,
    read_env,
    write_env,
)


def test_layout_paths_are_under_root(tmp_path):
    layout = Layout.at(tmp_path)

    assert layout.app == tmp_path / "app"
    assert layout.data == tmp_path / "data"
    assert layout.python_exe == layout.runtime / "python" / (
        "python.exe" if IS_WINDOWS else "bin/python"
    )
    assert layout.source_dir == tmp_path / "data" / "TC_DL"
    assert layout.qdrant_storage == tmp_path / "data" / "qdrant"


def test_env_round_trip_keeps_quotes_and_backslashes(tmp_path):
    path = tmp_path / "app" / ".env"
    write_env(
        path,
        {"JWT_SECRET_KEY": "abc", "POSTGRES_PASSWORD": "x y", "WIN_PATH": r"C:\QTKD\data"},
    )

    values = read_env(path)

    assert values["JWT_SECRET_KEY"] == "abc"
    assert values["POSTGRES_PASSWORD"] == "x y"
    assert values["WIN_PATH"] == r"C:\QTKD\data"


def test_write_env_preserves_existing_secrets(tmp_path):
    path = tmp_path / ".env"
    write_env(path, {"JWT_SECRET_KEY": "giu-lai", "API_PORT": "8080"})

    merged = write_env(path, {"API_PORT": "9090"})

    assert merged["JWT_SECRET_KEY"] == "giu-lai"
    assert merged["API_PORT"] == "9090"
    assert read_env(path)["API_PORT"] == "9090"


def test_copy_missing_does_not_overwrite_user_files(tmp_path):
    src = tmp_path / "seed"
    dst = tmp_path / "data"
    src.mkdir()
    (src / "a.docx").write_text("moi", encoding="utf-8")
    (src / "b.docx").write_text("moi", encoding="utf-8")
    dst.mkdir()
    (dst / "a.docx").write_text("nguoi dung", encoding="utf-8")

    copy_missing(src, dst)

    assert (dst / "a.docx").read_text(encoding="utf-8") == "nguoi dung"
    assert (dst / "b.docx").read_text(encoding="utf-8") == "moi"


def test_port_available_is_false_when_bound():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]

        assert not port_available(port)
