"""Chuyển .doc/.xls cũ bằng LibreOffice (ingestion.convert_legacy).

Ca chuyển đổi thật tự sinh .doc/.xls nhỏ trong ``tmp_path`` và bỏ qua khi máy
không có soffice; ca cache kiểm bằng cách nạp sẵn tệp cache nên không cần soffice.
"""

from __future__ import annotations

import hashlib
import subprocess
import zipfile
from pathlib import Path

import pytest

from ingestion import convert_legacy
from ingestion.convert_legacy import ConvertLegacyError, cache_path
from ingestion.convert_legacy import convert_legacy as convert
from scripts.knowledge_corpus import ooxml as ox

HAS_SOFFICE = Path(convert_legacy._soffice_bin()).exists()

_BLOCKS = [
    {"t": "h", "text": "Danh muc NAS", "style": "heading1"},
    {"t": "p", "text": "Noi dung mau de kiem chuyen doi."},
]


def _needs_soffice():
    return pytest.mark.skipif(not HAS_SOFFICE, reason="không có soffice")


def _soffice(src: Path, out_ext: str) -> Path:
    """Xuất ``src`` sang ``out_ext`` bằng soffice (dùng cho test, hồ sơ mặc định)."""
    subprocess.run(
        [
            convert_legacy._soffice_bin(),
            "--headless",
            "--convert-to",
            out_ext,
            "--outdir",
            str(src.parent),
            str(src),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return src.with_suffix(f".{out_ext}")


@_needs_soffice()
def test_converts_doc_to_docx_and_keeps_source(tmp_path):
    docx = tmp_path / "mau.docx"
    ox.write_docx(docx, _BLOCKS)
    doc = _soffice(docx, "doc")
    before = hashlib.sha256(doc.read_bytes()).hexdigest()

    out = convert(doc, tmp_path / "converted")

    assert out.exists() and out.suffix == ".docx"
    assert zipfile.is_zipfile(out)
    with zipfile.ZipFile(out) as archive:
        assert "Danh muc NAS" in archive.read("word/document.xml").decode("utf-8")
    # Bản gốc không bị sửa.
    assert hashlib.sha256(doc.read_bytes()).hexdigest() == before


@_needs_soffice()
def test_converts_xls_to_xlsx(tmp_path):
    xlsx = tmp_path / "mau.xlsx"
    ox.write_xlsx(xlsx, [ox.Sheet("NAS-2022", [["TT", "Ten"], [1, "abc"]])])
    xls = _soffice(xlsx, "xls")

    out = convert(xls, tmp_path / "converted")

    assert out.exists() and out.suffix == ".xlsx"
    assert zipfile.is_zipfile(out)


@_needs_soffice()
def test_cache_reuses_same_content_without_reconverting(tmp_path, monkeypatch):
    docx = tmp_path / "mau2.docx"
    ox.write_docx(docx, _BLOCKS)
    doc = _soffice(docx, "doc")
    first = convert(doc, tmp_path / "converted")

    def bomb(*_args, **_kwargs):
        raise AssertionError("không được chuyển lại khi đã có cache")

    monkeypatch.setattr(convert_legacy, "_run_soffice", bomb)
    assert convert(doc, tmp_path / "converted") == first


def test_cache_key_follows_content_not_name(tmp_path):
    a = tmp_path / "a.doc"
    b = tmp_path / "b-that-dai.doc"
    a.write_bytes(b"cung noi dung")
    b.write_bytes(b"cung noi dung")
    assert cache_path(a, tmp_path / "conv") == cache_path(b, tmp_path / "conv")


def test_cache_hit_avoids_soffice(tmp_path, monkeypatch):
    src = tmp_path / "co-san.doc"
    src.write_bytes(b"noi dung")
    cached = cache_path(src, tmp_path / "conv")
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"da chuyen")

    monkeypatch.setattr(
        convert_legacy.subprocess, "run", lambda *a, **k: pytest.fail("không gọi soffice")
    )
    assert convert(src, tmp_path / "conv") == cached


def test_rejects_unsupported_extension(tmp_path):
    txt = tmp_path / "ghi-chu.txt"
    txt.write_bytes(b"x")
    with pytest.raises(ConvertLegacyError, match="Không hỗ trợ"):
        convert(txt, tmp_path / "conv")


def test_reports_missing_source(tmp_path):
    with pytest.raises(ConvertLegacyError, match="Không tìm thấy tệp nguồn"):
        convert(tmp_path / "khong-co.doc", tmp_path / "conv")
