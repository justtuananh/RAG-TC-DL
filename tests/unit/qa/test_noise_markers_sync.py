"""Footgun đã được CLAUDE.md cảnh báo: _NOISE_PATH_MARKERS bị nhân bản ở 2 file.

Nếu ai sửa list lọc boilerplate ở retriever.py mà quên bm25_index.py (hoặc ngược
lại), BM25 và dense sẽ lọc khác nhau. Test này fail ngay khi hai bản lệch.
"""

from retrieval.bm25_index import _NOISE_PATH_MARKERS as BM25_MARKERS
from retrieval.bm25_index import _is_noise_path as BM25_PREDICATE
from retrieval.retriever import _NOISE_PATH_MARKERS as RETRIEVER_MARKERS
from retrieval.retriever import _is_noise_path as RETRIEVER_PREDICATE


def test_noise_markers_in_sync():
    assert RETRIEVER_MARKERS == BM25_MARKERS


def test_noise_predicate_is_shared_object():
    # Cả hai consumer phải import CÙNG một hàm từ _constants — không bản sao tay.
    assert RETRIEVER_PREDICATE is BM25_PREDICATE
