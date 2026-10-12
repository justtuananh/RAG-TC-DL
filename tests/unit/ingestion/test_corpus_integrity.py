"""T1: corpus tổng hợp (``tests/data/knowledge_corpus``) khớp manifest và đúng định dạng."""

from __future__ import annotations

import zipfile

import pytest

from tests.unit.ingestion.conftest import load_manifest

_ALL_IDS = sorted(load_manifest())


def test_files_match_manifest(corpus_manifest, corpus_file_paths):
    """Tập tên file trong ``files/`` bằng đúng tập ``file`` trong manifest."""
    manifest_files = {obj["file"] for obj in corpus_manifest.values()}
    actual_files = set(corpus_file_paths.keys())
    assert actual_files == manifest_files, (
        f"Chỉ trong manifest: {manifest_files - actual_files}\n"
        f"Chỉ trong files/: {actual_files - manifest_files}"
    )


def test_group_counts(corpus_manifest):
    """Số file theo nhóm: A=12, B>=8, C=3, D=14, E=8, F=3, G=2; tổng 48..55."""
    by_group: dict[str, int] = {}
    for obj in corpus_manifest.values():
        by_group[obj["group"]] = by_group.get(obj["group"], 0) + 1

    assert by_group.get("A") == 12
    assert by_group.get("B", 0) >= 8
    assert by_group.get("C") == 3
    assert by_group.get("D") == 14
    assert by_group.get("E") == 8
    assert by_group.get("F") == 3
    assert by_group.get("G") == 2
    assert 48 <= sum(by_group.values()) <= 55


@pytest.mark.parametrize("manifest_id", _ALL_IDS)
def test_file_format_valid(manifest_id, corpus_manifest, corpus_file_paths):
    """Mọi .docx/.xlsx là zip hợp lệ có phần lõi OOXML; .pdf bắt đầu bằng %PDF.

    .doc/.xls (nhóm G) không phải zip - chỉ cần tồn tại, không kiểm cấu trúc.
    """
    obj = corpus_manifest[manifest_id]
    file_path = corpus_file_paths[obj["file"]]
    suffix = file_path.suffix.lower()

    if suffix in (".docx", ".xlsx"):
        assert zipfile.is_zipfile(file_path), f"{file_path.name} không phải zip hợp lệ"
        with zipfile.ZipFile(file_path) as zf:
            names = zf.namelist()
            required = "word/document.xml" if suffix == ".docx" else "xl/workbook.xml"
            assert any(required in n for n in names), f"{file_path.name} thiếu {required}"
    elif suffix == ".pdf":
        assert file_path.read_bytes()[:5] == b"%PDF-", f"{file_path.name} không phải PDF hợp lệ"
    else:
        assert suffix in (".doc", ".xls"), f"{file_path.name}: đuôi lạ {suffix}"
        assert file_path.stat().st_size > 0
