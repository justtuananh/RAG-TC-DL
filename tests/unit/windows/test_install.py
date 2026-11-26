"""Cấu hình .env và chọn cổng của bộ cài Windows."""

from __future__ import annotations

import socket

import pytest

from windows.common import Layout
from windows.install import PORT_DEFAULTS, build_env, choose_ports, requirements_hash


def test_build_env_sets_production_and_local_urls(tmp_path):
    layout = Layout.at(tmp_path)

    env = build_env(layout, PORT_DEFAULTS, existing={})

    assert env["APP_ENV"] == "production"
    assert env["AUTH_ENABLED"] == "true"
    assert env["EMBED_URL"] == "http://127.0.0.1:8010/v1/embeddings"
    assert env["RERANK_URL"] == "http://127.0.0.1:8011/v1/rerank"
    assert env["QDRANT_URL"] == "http://127.0.0.1:6333"
    assert env["OLLAMA_URL"] == "http://127.0.0.1:11434/api/chat"
    assert env["QTKD_SOURCE_DIR"] == (tmp_path / "data" / "TC_DL").as_posix()
    assert len(env["JWT_SECRET_KEY"]) >= 32


def test_build_env_keeps_existing_secrets(tmp_path):
    layout = Layout.at(tmp_path)
    existing = {
        "JWT_SECRET_KEY": "k" * 40,
        "POSTGRES_PASSWORD": "mat-khau-cu",
        "QDRANT_API_KEY": "qdrant-cu",
    }

    env = build_env(layout, PORT_DEFAULTS, existing)

    assert env["JWT_SECRET_KEY"] == "k" * 40
    assert env["POSTGRES_PASSWORD"] == "mat-khau-cu"
    assert env["QDRANT_API_KEY"] == "qdrant-cu"


def test_build_env_points_at_seeded_paths(tmp_path):
    layout = Layout.at(tmp_path)

    env = build_env(layout, PORT_DEFAULTS, existing={})

    assert env["QTKD_DATA_DIR"] == (tmp_path / "data").as_posix()
    assert env["FORMULA_REGISTRY_DB"].endswith("/data/registry/registry.sqlite3")
    assert env["QTKD_LOGGING_FILE"].endswith("/data/logs/app.log")


def test_choose_ports_keeps_existing_ports():
    def free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    api, embedding, reranker = free_port(), free_port(), free_port()
    ports = choose_ports(
        {
            "API_PORT": str(api),
            "EMBEDDING_PORT": str(embedding),
            "RERANKER_PORT": str(reranker),
            "QDRANT_PORT": "16333",
            "OLLAMA_PORT": "21434",
            "POSTGRES_PORT": "25432",
        }
    )

    assert ports["api"] == api
    assert ports["embedding"] == embedding
    assert ports["postgres"] == 25432


def test_choose_ports_refuses_when_our_api_port_is_taken():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        busy = sock.getsockname()[1]

        with pytest.raises(SystemExit, match="đang bận"):
            choose_ports({"API_PORT": str(busy)})


def test_requirements_hash_changes_with_inference_pins(tmp_path):
    layout = Layout.at(tmp_path)
    (layout.app).mkdir(parents=True)
    (layout.app / "requirements.txt").write_text("a>=1\n", encoding="utf-8")
    (layout.app / "requirements-app.txt").write_text("b>=1\n", encoding="utf-8")
    (layout.app / "windows").mkdir()
    inference = layout.app / "windows" / "requirements-inference.txt"
    inference.write_text("torch==2.9.1\n", encoding="utf-8")

    before = requirements_hash(layout)
    inference.write_text("torch==2.9.2\n", encoding="utf-8")

    assert requirements_hash(layout) != before
