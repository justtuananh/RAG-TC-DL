"""Nạp settings.yaml: thay biến môi trường, kiểm schema, override cho test."""

from pathlib import Path

import pytest

from core import settings_loader as SL


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "settings.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _default_text() -> str:
    return (SL.CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8")


def test_interpolate_uses_env_when_set():
    assert SL.interpolate("${A:-x}", {"A": "y"}) == "y"


def test_interpolate_falls_back_to_default_when_unset_or_empty():
    assert SL.interpolate("${A:-x}", {}) == "x"
    assert SL.interpolate("${A:-x}", {"A": ""}) == "x"


def test_interpolate_empty_default_gives_empty_string():
    assert SL.interpolate("${A:-}", {}) == ""


def test_interpolate_missing_required_variable_raises():
    with pytest.raises(SL.SettingsError, match="B"):
        SL.interpolate("${B}", {})


def test_interpolate_walks_nested_lists_and_dicts():
    raw = {"a": ["${X:-1}", {"b": "pre-${X:-1}-post"}], "n": 5}
    assert SL.interpolate(raw, {"X": "9"}) == {"a": ["9", {"b": "pre-9-post"}], "n": 5}


def test_default_file_loads_with_empty_env():
    assert SL.load_settings(env={}).vectorstore.collection == "qtkd_rag"


def test_unknown_key_is_rejected(tmp_path):
    path = _write(tmp_path, _default_text() + "\nkhoa_la: 1\n")
    with pytest.raises(SL.SettingsError, match="khoa_la"):
        SL.load_settings(path=path, env={})


def test_wrong_type_is_rejected(tmp_path):
    path = _write(tmp_path, _default_text().replace("top_k: 50", "top_k: nhiều", 1))
    with pytest.raises(SL.SettingsError, match="top_k"):
        SL.load_settings(path=path, env={})


def test_relative_paths_resolve_against_repo_root():
    assert SL.load_settings(env={}).paths.markdown_dir == SL.REPO_ROOT / "build" / "spike_a"


def test_env_overrides_model_and_url():
    settings = SL.load_settings(
        env={"OLLAMA_MODEL": "qwen2.5:7b", "QDRANT_URL": "http://qdrant:6333"}
    )
    assert settings.models.llm_chat == "qwen2.5:7b"
    assert settings.services.qdrant_url == "http://qdrant:6333"


def test_with_overrides_returns_new_settings_and_keeps_original():
    base = SL.load_settings(env={})
    new = SL.with_overrides(base, {"retrieval.top_k": 7})
    assert new.retrieval.top_k == 7
    assert base.retrieval.top_k == 50


def test_with_overrides_unknown_key_raises():
    with pytest.raises(SL.SettingsError, match="retrieval.khong_co"):
        SL.with_overrides(SL.load_settings(env={}), {"retrieval.khong_co": 1})


def test_settings_override_fixture_reaches_get_settings(settings_override):
    settings_override({"retrieval.top_n": 3})
    assert SL.get_settings().retrieval.top_n == 3


def test_cli_get_prints_value(capsys):
    assert SL.main(["get", "vectorstore.collection"]) == 0
    assert capsys.readouterr().out.strip() == "qtkd_rag"
