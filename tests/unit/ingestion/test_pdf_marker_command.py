"""Marker trên Windows: biến môi trường qua subprocess, không dùng lệnh ``env``."""

from __future__ import annotations

from ingestion import extract_pdf_marker


def test_marker_env_is_a_plain_environment_mapping():
    assert extract_pdf_marker._marker_env("cpu", 4) == {
        "TORCH_DEVICE": "cpu",
        "OMP_NUM_THREADS": "4",
        "MKL_NUM_THREADS": "4",
    }


def test_marker_command_has_no_posix_env_prefix():
    assert extract_pdf_marker._marker_command("marker_single", 0) == ["marker_single"]


def test_systemd_wrapper_is_linux_only(monkeypatch):
    monkeypatch.setattr(extract_pdf_marker.shutil, "which", lambda _name: "/usr/bin/systemd-run")
    monkeypatch.setattr(extract_pdf_marker.sys, "platform", "win32")

    assert extract_pdf_marker._marker_command("marker_single", 512) == ["marker_single"]

    monkeypatch.setattr(extract_pdf_marker.sys, "platform", "linux")

    assert extract_pdf_marker._marker_command("marker_single", 512)[0] == "systemd-run"
