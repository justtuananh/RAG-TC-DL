"""Lọc section template/boilerplate trước rerank — retrieval.retriever._filter_noise."""

from retrieval.retriever import _NOISE_PATH_MARKERS, _filter_noise


def _h(section_path):
    return {"payload": {"section_path": section_path}}


def test_removes_noise_sections():
    hits = [
        _h("6 Tiến hành kiểm định > 6.3 Kiểm tra đo lường"),
        _h("Phụ lục A Mẫu biên bản kiểm định"),
        _h("Phụ lục B (Quy định)"),
    ]
    out = _filter_noise(hits)
    assert [h["payload"]["section_path"] for h in out] == [
        "6 Tiến hành kiểm định > 6.3 Kiểm tra đo lường"
    ]


def test_keeps_all_clean():
    hits = [_h("1 Phạm vi áp dụng"), _h("2 Tài liệu viện dẫn")]
    assert _filter_noise(hits) == hits


def test_missing_section_path_is_safe():
    assert _filter_noise([{"payload": {}}]) == [{"payload": {}}]


def test_markers_cover_known_boilerplate():
    assert "Mẫu biên bản" in _NOISE_PATH_MARKERS
    assert "(Quy định)" in _NOISE_PATH_MARKERS
