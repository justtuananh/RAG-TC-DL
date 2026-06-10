"""Footgun đã được CLAUDE.md cảnh báo: _NOISE_PATH_MARKERS bị nhân bản ở 2 file.

Nếu ai sửa list lọc boilerplate ở retriever.py mà quên bm25_index.py (hoặc ngược
lại), BM25 và dense sẽ lọc khác nhau. Test này fail ngay khi hai bản lệch.
"""

from retrieval.bm25_index import _NOISE_PATH_MARKERS as BM25_MARKERS
from retrieval.retriever import _NOISE_PATH_MARKERS as RETRIEVER_MARKERS


def test_noise_markers_in_sync():
    assert RETRIEVER_MARKERS == BM25_MARKERS
