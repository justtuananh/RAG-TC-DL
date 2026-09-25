"""T2: kiểm tra phân loại tài liệu từ tên file (``ingestion.classify``)."""

from __future__ import annotations

import pytest

from ingestion.classify import classify_document
from tests.unit.knowledge_corpus.conftest import load_manifest

# Toàn bộ id manifest, đóng băng ở đây để test_classify_covers_full_manifest phát
# hiện khi corpus thêm/bớt file mà danh sách tham số hoá quên cập nhật theo.
_ALL_IDS = sorted(load_manifest())


@pytest.mark.parametrize("manifest_id", _ALL_IDS)
def test_classify_matches_expected(manifest_id, corpus_manifest):
    """Phân loại chỉ từ tên file (upload thật chỉ truyền tên file) khớp
    ``expected_doc_type`` của từng tài liệu trong manifest."""
    obj = corpus_manifest[manifest_id]
    result = classify_document(obj["file"])
    assert result.doc_type == obj["expected_doc_type"], (
        f"{manifest_id} ({obj['file']}): phân loại '{result.doc_type}' "
        f"(kỳ vọng '{obj['expected_doc_type']}')"
    )


def test_classify_covers_full_manifest(corpus_manifest):
    """Bảo vệ: danh sách tham số hoá ở trên phải khớp đúng manifest hiện tại, để
    một file mới thêm vào corpus không âm thầm thoát khỏi T2."""
    assert set(_ALL_IDS) == set(corpus_manifest)
