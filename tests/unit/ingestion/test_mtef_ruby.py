"""Ruby của bản cài portable: đường dẫn gem do Ruby tự khai, không đoán phiên bản."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ingestion import mtef_to_latex


@pytest.fixture(autouse=True)
def _clear_cache():
    clear = getattr(mtef_to_latex._detect_gem_path, "cache_clear", None)
    if clear:
        clear()
    yield
    clear = getattr(mtef_to_latex._detect_gem_path, "cache_clear", None)
    if clear:
        clear()


def test_gem_path_from_environment_wins(monkeypatch):
    monkeypatch.setenv("GEM_PATH", "/gems/rieng")
    monkeypatch.setattr(
        mtef_to_latex,
        "_detect_gem_path",
        lambda _ruby: pytest.fail("không được hỏi Ruby khi đã có GEM_PATH"),
    )

    assert mtef_to_latex._ruby_env("ruby")["GEM_PATH"] == "/gems/rieng"


def test_gem_path_is_asked_from_ruby(monkeypatch):
    monkeypatch.delenv("GEM_PATH", raising=False)
    monkeypatch.setattr(
        mtef_to_latex,
        "_detect_gem_path",
        lambda ruby: "/tools/ruby/lib/ruby/gems/4.0.0" if ruby == "ruby-rieng" else None,
    )

    assert mtef_to_latex._ruby_env("ruby-rieng")["GEM_PATH"] == "/tools/ruby/lib/ruby/gems/4.0.0"


def test_detect_gem_path_uses_ruby_output(monkeypatch):
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="/a;/b")

    monkeypatch.setattr(mtef_to_latex.subprocess, "run", fake_run)

    assert mtef_to_latex._detect_gem_path("C:/ruby/bin/ruby.exe") == "/a;/b"
    assert calls["cmd"][0] == "C:/ruby/bin/ruby.exe"


def test_configured_ruby_bin_is_used(settings_override):
    settings_override({"ingestion.ruby_bin": "C:/tools/ruby/bin/ruby.exe"})

    assert mtef_to_latex._ruby_bin() == "C:/tools/ruby/bin/ruby.exe"


def test_bin_to_mathml_runs_configured_ruby(monkeypatch, settings_override):
    settings_override({"ingestion.ruby_bin": "C:/tools/ruby/bin/ruby.exe"})
    monkeypatch.setenv("GEM_PATH", "C:/tools/ruby/gems")
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["env"] = kwargs["env"]
        return SimpleNamespace(returncode=0, stdout="<math/>\n")

    monkeypatch.setattr(mtef_to_latex.subprocess, "run", fake_run)

    assert mtef_to_latex._bin_to_mathml("formula.bin") == "<math/>"
    assert seen["cmd"][0] == "C:/tools/ruby/bin/ruby.exe"
    assert seen["env"]["GEM_PATH"] == "C:/tools/ruby/gems"
