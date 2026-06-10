"""Builder ngữ cảnh + trích dẫn — generation.build_context_and_citations.

Context dùng PARENT text (đủ ngữ cảnh) cắt theo MAX_CONTEXT_CHARS; citations dùng
snippet CHILD (cap 220) — đánh số [n] khớp nhau giữa ngữ cảnh và trích dẫn.
"""

import generation


def _r(
    child_text, parent_text=None, file_stem="QTKD_1.061_2021_ND_V2", section="6 Tiến hành > 6.1 Đo"
):
    return {
        "payload": {"text": child_text, "file_stem": file_stem, "section_path": section},
        "parent_payload": {"text": parent_text} if parent_text else None,
    }


def test_uses_parent_text_when_present():
    ctx, _ = generation.build_context_and_citations(
        [_r("noi dung con", parent_text="toan bo section")]
    )
    assert "toan bo section" in ctx
    assert "noi dung con" not in ctx  # context dùng parent, không phải child


def test_uses_child_text_when_no_parent():
    ctx, _ = generation.build_context_and_citations([_r("chi co child")])
    assert "chi co child" in ctx


def test_per_source_cap_truncates_huge_parent():
    # 1 nguồn lớn → cắt ở MAX_BLOCK_CHARS (không phình ~20k gây chôn fact + 500 Ollama).
    long = "A" * (generation.MAX_BLOCK_CHARS + 5000)
    ctx, _ = generation.build_context_and_citations([_r("c", parent_text=long)])
    assert "…" in ctx
    assert "A" * generation.MAX_BLOCK_CHARS in ctx
    assert "A" * (generation.MAX_BLOCK_CHARS + 1) not in ctx


def test_short_parent_not_truncated():
    # Parent dưới cap KHÔNG bị cắt.
    short = "B" * (generation.MAX_BLOCK_CHARS - 200)
    ctx, _ = generation.build_context_and_citations([_r("c", parent_text=short)])
    assert short in ctx


def test_no_source_exceeds_cap_even_with_donation():
    # Nguồn ngắn nhường quota, nhưng KHÔNG nguồn nào vượt MAX_BLOCK_CHARS.
    short = "x" * 50
    big = "Y" * (generation.MAX_BLOCK_CHARS + 4000)
    results = [_r("c", parent_text=short)] * 4 + [_r("c", parent_text=big)]
    ctx, _ = generation.build_context_and_citations(results)
    assert "Y" * generation.MAX_BLOCK_CHARS in ctx
    assert "Y" * (generation.MAX_BLOCK_CHARS + 1) not in ctx


def test_citations_numbered_and_formatted():
    _, cites = generation.build_context_and_citations([_r("c1"), _r("c2")])
    assert "**[1]**" in cites and "**[2]**" in cites
    assert "`QTKD_1.061_2021_ND_V2`" in cites
    assert "Nguồn tham khảo" in cites


def test_citation_snippet_capped_at_220():
    _, cites = generation.build_context_and_citations([_r("B" * 300)])
    assert "B" * 220 in cites
    assert "B" * 221 not in cites
    assert "…" in cites


def test_context_and_citations_share_numbering():
    ctx, cites = generation.build_context_and_citations([_r("x"), _r("y"), _r("z")])
    assert "[1]" in ctx and "[2]" in ctx and "[3]" in ctx
    assert "**[3]**" in cites
