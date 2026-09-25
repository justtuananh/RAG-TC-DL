"""T3: kiểm tra rào cản ingestion (định dạng cũ, trùng lặp, đuôi tệp được nhận).

Cô lập ``ingestion_jobs.TC_DL_DIR``/``SessionLocal`` bằng monkeypatch theo đúng
cách các test hiện có (``tests/unit/backend``) làm — không chạm ``TC_DL/`` thật.
"""

from __future__ import annotations

import hashlib

import pytest

import ingestion_jobs
from ingestion import spike_a
from ingestion_jobs import UploadError, save_upload
from tests.unit.knowledge_corpus.conftest import load_manifest

_MANIFEST = load_manifest()


def _ids(group: str) -> list[str]:
    return sorted(mid for mid, obj in _MANIFEST.items() if obj["group"] == group)


def _ok_docx_pdf_ids() -> list[str]:
    return sorted(
        mid
        for mid, obj in _MANIFEST.items()
        if obj["expected_ingest"] == "ok" and obj["file"].lower().endswith((".docx", ".pdf"))
    )


def _xlsx_ids() -> list[str]:
    return sorted(mid for mid, obj in _MANIFEST.items() if obj["file"].lower().endswith(".xlsx"))


@pytest.fixture(autouse=True)
def _isolate_ingestion_jobs(tmp_path, monkeypatch, session):
    """Cô lập thư mục upload + DB của ``ingestion_jobs`` cho mọi test trong file này."""
    monkeypatch.setattr(ingestion_jobs, "TC_DL_DIR", tmp_path / "tc_dl")
    monkeypatch.setattr(ingestion_jobs, "SessionLocal", lambda: session)


@pytest.mark.parametrize("manifest_id", _ids("G"))
def test_legacy_formats_skipped_by_spike_a(manifest_id, corpus_file_paths, tmp_path):
    """G01/G02 (.doc/.xls): ``spike_a.process_one`` trả trạng thái ``skipped-legacy``."""
    obj = _MANIFEST[manifest_id]
    file_path = corpus_file_paths[obj["file"]]
    result = spike_a.process_one(file_path, out_dir=tmp_path)
    assert result.get("status") == "skipped-legacy"


@pytest.mark.parametrize("manifest_id", _ids("G"))
def test_legacy_formats_rejected_on_upload(manifest_id, corpus_file_paths):
    """G01/G02 (.doc/.xls): ``save_upload`` từ chối (đuôi không được hỗ trợ)."""
    obj = _MANIFEST[manifest_id]
    file_path = corpus_file_paths[obj["file"]]
    with pytest.raises(UploadError):
        save_upload(file_path.name, file_path.read_bytes())


def test_f01_duplicate_has_same_sha256_as_a01(corpus_file_paths):
    """F01 trùng byte-for-byte với A01 (khác tên) — sha256 phải bằng nhau."""
    f01_path = corpus_file_paths[_MANIFEST["F01"]["file"]]
    a01_path = corpus_file_paths[_MANIFEST["A01"]["file"]]
    f01_sha = hashlib.sha256(f01_path.read_bytes()).hexdigest()
    a01_sha = hashlib.sha256(a01_path.read_bytes()).hexdigest()
    assert f01_sha == a01_sha


def test_f01_upload_blocked_as_duplicate_after_a01(corpus_file_paths):
    """Nạp A01 qua ``save_upload`` thành công; nạp F01 (trùng sha256) sau đó bị chặn."""
    a01_path = corpus_file_paths[_MANIFEST["A01"]["file"]]
    f01_path = corpus_file_paths[_MANIFEST["F01"]["file"]]

    stem = save_upload(a01_path.name, a01_path.read_bytes())
    assert stem

    with pytest.raises(UploadError, match="đã tồn tại"):
        save_upload(f01_path.name, f01_path.read_bytes())


@pytest.mark.parametrize("manifest_id", _ok_docx_pdf_ids())
def test_docx_pdf_with_ok_ingest_are_accepted(manifest_id, corpus_file_paths):
    """Mọi file ``expected_ingest == "ok"`` với đuôi .docx/.pdf được ``save_upload`` nhận."""
    obj = _MANIFEST[manifest_id]
    file_path = corpus_file_paths[obj["file"]]
    stem = save_upload(file_path.name, file_path.read_bytes())
    assert stem


@pytest.mark.parametrize("manifest_id", _xlsx_ids())
def test_xlsx_rejected_on_upload(manifest_id, corpus_file_paths):
    """.xlsx (phiếu đo, nhóm E) KHÔNG được nhận ở upload chung — chỉ .docx/.pdf được
    hỗ trợ (``ingestion_jobs.SUPPORTED_EXTS``, input-contract §1). Đây là hành vi
    hiện tại của hệ thống, không phải một mã K."""
    obj = _MANIFEST[manifest_id]
    file_path = corpus_file_paths[obj["file"]]
    with pytest.raises(UploadError):
        save_upload(file_path.name, file_path.read_bytes())
