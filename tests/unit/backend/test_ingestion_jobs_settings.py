"""ingestion.jobs đọc đường dẫn và giới hạn tải lên từ settings, lúc gọi."""

from __future__ import annotations

import pytest

from ingestion import jobs as ingestion_jobs


def test_empty_report_records_source_dir_relative_to_repo(tmp_path, settings_override):
    # Chưa có extraction_report.json: report mới ghi nguồn tương đối như spike_a ("TC_DL"),
    # không lộ đường dẫn tuyệt đối của máy / container vào file sinh ra.
    settings_override({"paths.markdown_dir": str(tmp_path)})
    assert ingestion_jobs._read_report() == {"source": "TC_DL", "files": [], "totals": {}}


def test_empty_report_keeps_source_dir_outside_repo_absolute(tmp_path, settings_override):
    src = tmp_path / "nguon"
    settings_override({"paths.markdown_dir": str(tmp_path), "paths.source_dir": str(src)})
    assert ingestion_jobs._read_report()["source"] == str(src)


def test_upload_size_message_follows_configured_limit(settings_override):
    settings_override({"ingestion.max_upload_bytes": 2 * 1024 * 1024})
    with pytest.raises(ingestion_jobs.UploadError, match=r"\(2 MB\)"):
        ingestion_jobs.save_upload("qtkd.docx", b"x" * (2 * 1024 * 1024 + 1))
