from llm import citations
from llm.guards import REFUSAL_SENTENCE


def _src(i, stem="S1", section="5 Tiến hành > 5.2 Kiểm tra", page=7, exact=True, score=0.5, text=""):
    return {
        "index": i, "file_stem": stem, "section_path": section, "page": page, "page_exact": exact,
        "rerank_score": score, "child_text": text, "parent_text": text, "snippet": text,
    }


def test_block_uses_deepest_section_title_and_page():
    out = citations.add_citations("Sai số 0,5 % [1].", [_src(1)], lambda s: "ÁP KẾ A")
    assert out.endswith("Nguồn:\n- [1] S1 (ÁP KẾ A) — 5.2 Kiểm tra, tr. 7")


def test_inexact_page_marked_and_missing_page_omitted():
    srcs = [_src(1, exact=False), _src(2, page=None)]
    out = citations.add_citations("A [1] B [2]", srcs)
    assert "- [1] S1 — 5.2 Kiểm tra, tr. ~7" in out
    assert "- [2] S1 — 5.2 Kiểm tra" in out and "tr." not in out.split("- [2]")[1]


def test_invalid_refs_removed_and_groups_trimmed():
    out = citations.add_citations("A [9] B [1, 5].", [_src(1)])
    body = out.split("\n\nNguồn:")[0]
    assert body == "A B [1]."


def test_own_block_replaced():
    out = citations.add_citations("Đáp [1].\n\nTrích dẫn:\n- [1] bịa", [_src(1)])
    assert "bịa" not in out and out.count("Nguồn:") == 1


def test_refusal_untouched():
    assert citations.add_citations(REFUSAL_SENTENCE, [_src(1)]) == REFUSAL_SENTENCE


def test_missing_refs_pick_top_rerank_source_with_number():
    srcs = [_src(1, score=0.9, text="không liên quan"), _src(2, score=0.6, text="Sai số cho phép 0,4 oC"),
            _src(3, score=0.8, text="giá trị 0,4 oC khác")]
    out = citations.add_citations("Sai số là 0,4 oC.", srcs)
    assert out.startswith("Sai số là 0,4 oC. [3]") and "- [3] S1" in out


def test_missing_refs_keywords_when_no_numbers():
    srcs = [_src(1, score=0.9, text="nội dung khác hẳn"), _src(2, score=0.4, text="Môi trường truyền áp suất là nước cất")]
    out = citations.add_citations("Dùng nước cất làm môi trường truyền.", srcs)
    assert "[2]" in out.split("\n\nNguồn:")[0]


def test_unknown_source_when_nothing_matches():
    out = citations.add_citations("Giá trị 12,5 mm.", [_src(1, text="không có")])
    assert out.endswith("Nguồn: " + citations.UNKNOWN_SOURCE)


def test_language_fallback_gets_no_sources_block():
    from llm.lang_guard import LANGUAGE_FALLBACK

    assert citations.add_citations(LANGUAGE_FALLBACK, [_src(1)]) == LANGUAGE_FALLBACK
