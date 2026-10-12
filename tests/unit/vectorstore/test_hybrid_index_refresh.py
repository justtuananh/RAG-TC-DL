"""BM25 cập nhật theo file: thêm/xóa một tài liệu không quét lại cả collection.

Kết quả sau cập nhật phải TRÙNG với dựng lại từ đầu (cùng thứ tự chunk theo
point id như Qdrant scroll), để chất lượng truy hồi không phụ thuộc lịch sử upload.
"""

from __future__ import annotations

import pytest

import vectorstore.hybrid_index as hybrid_index


def _payload(chunk_id: int, stem: str, text: str, section: str = "1. Phạm vi") -> dict:
    return {
        "chunk_id": f"{chunk_id:016x}",
        "file_stem": stem,
        "section_path": section,
        "text": text,
        "is_parent": False,
    }


class _FakeStore:
    """Thay ``qdrant.scroll_child_payloads``: trả theo point id tăng dần như Qdrant."""

    def __init__(self, payloads: list[dict]):
        self.payloads = list(payloads)
        self.calls: list[frozenset[str] | None] = []

    def scroll(self, file_stems=None):
        self.calls.append(None if file_stems is None else frozenset(file_stems))
        rows = [p for p in self.payloads if file_stems is None or p["file_stem"] in file_stems]
        return sorted(rows, key=lambda p: int(p["chunk_id"], 16))


@pytest.fixture
def store(monkeypatch):
    s = _FakeStore(
        [
            _payload(5, "A", "van an toàn áp suất 1400 bar"),
            _payload(9, "B", "áp kế píttông tiêu chuẩn MPa"),
            _payload(2, "A", "phạm vi áp dụng van an toàn"),
        ]
    )
    monkeypatch.setattr(hybrid_index.qdrant, "scroll_child_payloads", s.scroll)
    return s


def test_refresh_adds_new_file_without_full_scan(store):
    hybrid_index.bm25_search("van an toàn")  # dựng lần đầu
    store.payloads += [_payload(7, "C", "bình phân ly van an toàn")]

    hybrid_index.refresh_files({"C"})

    assert store.calls == [None, frozenset({"C"})]
    assert "C" in {h["payload"]["file_stem"] for h in hybrid_index.bm25_search("bình phân ly")}


def test_refresh_drops_deleted_and_replaced_chunks(store):
    hybrid_index.bm25_search("van")
    store.payloads = [p for p in store.payloads if p["file_stem"] != "A"]
    store.payloads.append(_payload(1, "A", "nội dung mới hoàn toàn khác"))

    hybrid_index.refresh_files({"A"})

    assert [c["chunk_id"] for c in hybrid_index._index.chunks] == [f"{1:016x}", f"{9:016x}"]
    assert all(h["payload"]["file_stem"] != "A" for h in hybrid_index.bm25_search("van an toàn"))


def test_refresh_matches_full_rebuild(store):
    hybrid_index.bm25_search("van")
    store.payloads += [_payload(3, "C", "van an toàn bình phân ly"), _payload(8, "C", "1400 bar")]
    hybrid_index.refresh_files({"C"})
    refreshed = hybrid_index._index

    hybrid_index.invalidate()
    hybrid_index.bm25_search("van")
    rebuilt = hybrid_index._index

    assert [c["chunk_id"] for c in refreshed.chunks] == [c["chunk_id"] for c in rebuilt.chunks]
    for query in ("van an toàn", "1400 bar", "MPa"):
        assert refreshed.bm25.get_scores(query.split()).tolist() == pytest.approx(
            rebuilt.bm25.get_scores(query.split()).tolist()
        )


def test_refresh_before_first_build_is_noop(store):
    hybrid_index.refresh_files({"A"})

    assert store.calls == []
    assert hybrid_index._index is None


def test_noise_sections_stay_excluded_after_refresh(store):
    hybrid_index.bm25_search("van")
    store.payloads.append(_payload(4, "C", "van an toàn mẫu", section="Mẫu biên bản"))

    hybrid_index.refresh_files({"C"})

    assert all(c["file_stem"] != "C" for c in hybrid_index._index.chunks)


def test_empty_corpus_returns_no_hits(store):
    store.payloads = []

    assert hybrid_index.bm25_search("van") == []
