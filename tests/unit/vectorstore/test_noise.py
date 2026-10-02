"""Guard boilerplate dùng chung: vectorstore.noise là nguồn duy nhất.

CLAUDE.md cảnh báo _NOISE_PATH_MARKERS từng bị nhân bản ở retriever.py + hybrid_index.py;
nay cả hai import CÙNG một object từ vectorstore.noise → không thể lệch.
"""

from retrieval.hybrid_retriever import filter_noise
from vectorstore import hybrid_index, noise


def test_predicate_is_shared_object():
    # Cả hybrid_retriever lẫn hybrid_index dùng CÙNG hàm của vectorstore.noise.
    assert hybrid_index._is_noise_path is noise.is_noise_path


def test_markers_cover_known_boilerplate():
    assert "Mẫu biên bản" in noise.NOISE_PATH_MARKERS
    assert "(Quy định)" in noise.NOISE_PATH_MARKERS


def test_filter_noise_matches_predicate():
    hits = [{"payload": {"section_path": "Phụ lục B (Quy định)"}}]
    assert filter_noise(hits) == []
    assert noise.is_noise_path("Phụ lục B (Quy định)")
