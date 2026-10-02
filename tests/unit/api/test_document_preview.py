"""Bản xem trên trình duyệt của tệp gốc: .doc/.xls cũ → bản .docx/.xlsx đã chuyển.

Giao diện render .doc bằng cùng bộ xem .docx (docx-preview) và .xls bằng bộ xem
.xlsx, nên ``/preview`` phải trả đúng bản OOXML đã chuyển thay vì tệp nhị phân cũ.
Không cần LibreOffice: bước chuyển đổi được thay bằng tệp giả.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from ingestion import convert_legacy
from ingestion import jobs as ingestion_jobs

pytestmark = pytest.mark.unit


@pytest.fixture
def corpus(tmp_path, monkeypatch, settings_override):
    source = tmp_path / "TC_DL"
    source.mkdir()
    converted = tmp_path / "converted"
    converted.mkdir()
    settings_override({"paths.source_dir": str(source)})
    monkeypatch.setattr(convert_legacy, "CONVERTED_DIR", converted)
    return source, converted


def test_modern_formats_preview_as_the_original(corpus):
    source, _ = corpus
    original = source / "QTKD 1.159.docx"
    original.write_bytes(b"docx")
    assert ingestion_jobs.get_preview_path("QTKD_1.159") == original


def test_legacy_doc_previews_as_cached_docx(corpus):
    source, _ = corpus
    legacy = source / "Bieu 4.doc"
    legacy.write_bytes(b"legacy doc")
    cached = convert_legacy.cache_path(legacy)
    cached.write_bytes(b"converted docx")
    assert ingestion_jobs.get_preview_path("Bieu_4") == cached


def test_legacy_xls_is_converted_when_not_cached(corpus, monkeypatch):
    source, converted = corpus
    legacy = source / "Bieu 3.xls"
    legacy.write_bytes(b"legacy xls")
    produced = converted / "out.xlsx"

    def fake_convert(path):
        produced.write_bytes(b"xlsx")
        return produced

    monkeypatch.setattr(convert_legacy, "convert_legacy", fake_convert)
    assert ingestion_jobs.get_preview_path("Bieu_3") == produced


def test_missing_source_has_no_preview(corpus):
    assert ingestion_jobs.get_preview_path("khong_co") is None


def test_preview_route_serves_converted_docx(corpus):
    source, _ = corpus
    legacy = source / "Bieu 4.doc"
    legacy.write_bytes(b"legacy doc")
    convert_legacy.cache_path(legacy).write_bytes(b"converted docx")
    response = TestClient(app).get("/api/documents/Bieu_4/preview")
    assert response.status_code == 200
    assert response.content == b"converted docx"
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def test_preview_route_404_and_conversion_error(corpus, monkeypatch):
    client = TestClient(app)
    assert client.get("/api/documents/khong_co/preview").status_code == 404

    source, _ = corpus
    (source / "Bieu 7.doc").write_bytes(b"legacy doc")

    def broken(path):
        raise convert_legacy.ConvertLegacyError("Không tìm thấy LibreOffice.")

    monkeypatch.setattr(convert_legacy, "convert_legacy", broken)
    response = client.get("/api/documents/Bieu_7/preview")
    assert response.status_code == 422
    assert "LibreOffice" in response.json()["detail"]
