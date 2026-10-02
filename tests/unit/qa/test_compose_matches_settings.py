"""Compose không đọc được settings.yaml: tên model/độ dài/num_ctx lặp ở compose, test giữ khớp."""

import yaml

from core.settings_loader import REPO_ROOT, load_settings

_COMPOSE = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))[
    "services"
]


def test_embedding_service_model_matches_settings():
    svc = _COMPOSE["embedding"]
    name = load_settings(env={}).models.embedding.name
    assert svc["build"]["args"]["EMBEDDING_MODEL"] == name
    assert svc["environment"]["EMBEDDING_MODEL"] == name


def test_reranker_service_model_matches_settings():
    svc = _COMPOSE["reranker"]
    model = load_settings(env={}).models.reranker
    assert svc["build"]["args"]["RERANKER_MODEL"] == model.name
    assert svc["environment"]["RERANKER_MODEL"] == model.name
    assert int(svc["environment"]["RERANKER_MAX_LENGTH"]) == model.max_length


def test_ollama_context_length_matches_chat_num_ctx():
    env = _COMPOSE["ollama"]["environment"]
    assert int(env["OLLAMA_CONTEXT_LENGTH"]) == load_settings(env={}).llm.chat.num_ctx


def test_qdrant_data_lives_in_repo_qdrant_storage():
    assert "./qdrant_storage:/qdrant/storage" in _COMPOSE["qdrant"]["volumes"]


def test_api_does_not_pin_a_model_default():
    # Mặc định model nằm ở settings.yaml; compose chỉ chuyển tiếp biến nếu người dùng đặt.
    assert _COMPOSE["api"]["environment"]["OLLAMA_MODEL"] == "${OLLAMA_MODEL:-}"


def test_api_ships_no_default_secret():
    # Mặc định "change-me-in-production" từng khiến production ký token bằng chuỗi công khai.
    env = _COMPOSE["api"]["environment"]
    assert env["JWT_SECRET_KEY"] == "${JWT_SECRET_KEY:-}"
    assert env["APP_ENV"] == "${APP_ENV:-development}"
