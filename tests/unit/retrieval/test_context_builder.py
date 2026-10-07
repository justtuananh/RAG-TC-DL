"""Builder ngữ cảnh + trích dẫn - retrieval.context_builder.build_context_and_citations.

Context dùng PARENT text (đủ ngữ cảnh) trong ngân sách chia theo thứ hạng nguồn; citations
dùng snippet CHILD (cap 220) - đánh số [n] khớp nhau giữa ngữ cảnh và trích dẫn.
"""

from core.settings_loader import get_settings
from retrieval import context_builder


def _cap() -> int:
    return get_settings().llm.context.max_block_chars


def _r(
    child_text, parent_text=None, file_stem="QTKD_1.061_2021_ND_V2", section="6 Tiến hành > 6.1 Đo"
):
    return {
        "payload": {"text": child_text, "file_stem": file_stem, "section_path": section},
        "parent_payload": {"text": parent_text} if parent_text else None,
    }


def test_uses_parent_text_when_present():
    ctx, _ = context_builder.build_context_and_citations(
        [_r("noi dung con", parent_text="toan bo section")]
    )
    assert "toan bo section" in ctx
    assert "noi dung con" not in ctx  # context dùng parent, không phải child


def test_uses_child_text_when_no_parent():
    ctx, _ = context_builder.build_context_and_citations([_r("chi co child")])
    assert "chi co child" in ctx


def test_citations_numbered_and_formatted():
    _, cites = context_builder.build_context_and_citations([_r("c1"), _r("c2")])
    assert "**[1]**" in cites and "**[2]**" in cites
    assert "`QTKD_1.061_2021_ND_V2`" in cites
    assert "Nguồn tham khảo" in cites


def test_citation_snippet_capped_at_220():
    _, cites = context_builder.build_context_and_citations([_r("B" * 300)])
    assert "B" * 220 in cites
    assert "B" * 221 not in cites
    assert "…" in cites


def test_context_and_citations_share_numbering():
    ctx, cites = context_builder.build_context_and_citations([_r("x"), _r("y"), _r("z")])
    assert "[1]" in ctx and "[2]" in ctx and "[3]" in ctx
    assert "**[3]**" in cites


# ── Ngân sách theo thứ hạng ───────────────────────────────────────────────────


def _blocks(ctx: str) -> list[str]:
    return [part.split("---\n", 1)[1] for part in ctx.split("\n\n---\n\n")]


def test_single_source_is_held_to_the_total_context():
    total = get_settings().llm.total_context_chars
    ctx, _ = context_builder.build_context_and_citations(
        [_r("c", parent_text="A" * (total + 5000))]
    )
    assert ctx.count("A") <= total
    assert "…" in ctx


def test_top_source_is_not_held_to_the_per_source_cap():
    """Nguồn top dài hơn trần mỗi nguồn vẫn vào trọn khi trần tổng còn chỗ.

    QTKĐ 1.159 mục 6.3.2 (5 623 ký tự, điểm rerank 0,999) bị cắt ở 4 000 ký tự trong khi
    nguồn [5] điểm 0,68 vào trọn và 768 ký tự trần tổng bỏ không (đo 2026-10-07).
    """
    long = "L" * (_cap() + 1000)
    results = [_r("c", parent_text=long)] + [_r("c", parent_text="s" * 100)] * 4
    ctx, _ = context_builder.build_context_and_citations(results)
    assert _blocks(ctx)[0] == long


def test_lower_source_is_held_to_the_per_source_cap():
    short = "x" * 50
    big = "Y" * (_cap() + 4000)
    results = [_r("c", parent_text=short)] * 4 + [_r("c", parent_text=big)]
    ctx, _ = context_builder.build_context_and_citations(results)
    assert "Y" * _cap() in ctx
    assert "Y" * (_cap() + 1) not in ctx


def test_higher_ranked_source_gets_its_budget_first():
    llm = get_settings().llm
    floor = llm.context.min_block_chars
    top = "T" * (llm.total_context_chars - 2 * floor)
    second = "S" * (2 * floor + 1000)
    ctx, _ = context_builder.build_context_and_citations(
        [_r("c", parent_text=top), _r("c", parent_text=second)]
    )
    blocks = _blocks(ctx)
    assert blocks[0] == top
    assert floor <= blocks[1].count("S") <= 2 * floor


def test_every_lower_source_keeps_its_floor():
    llm = get_settings().llm
    floor = llm.context.min_block_chars
    results = [_r("c", parent_text="Z" * (llm.total_context_chars * 2))] + [
        _r("c", parent_text="W" * (_cap() * 2))
    ] * 4
    ctx, _ = context_builder.build_context_and_citations(results)
    assert all(block.count("W") >= floor for block in _blocks(ctx)[1:])


def test_total_context_stays_within_budget():
    llm = get_settings().llm
    big = "Z" * (llm.context.max_block_chars * 2)
    results = [_r("c", parent_text=big)] * 8
    ctx, _ = context_builder.build_context_and_citations(results)
    assert ctx.count("Z") <= llm.total_context_chars


def test_long_section_is_cut_around_its_anchors():
    """Mục dài hơn ngân sách: ngữ cảnh lấy quanh các đoạn neo (``anchor_texts``)."""
    filler = "\n\n".join(f"Đoạn đệm số {i} của mục dài." for i in range(400))
    anchor = "Sai số tương đối của H3000 không được vượt quá ± 0,1 %."
    hit = _r(anchor, parent_text=filler + "\n\n" + anchor + "\n\n" + filler)
    hit["anchor_texts"] = [anchor]
    ctx, _ = context_builder.build_context_and_citations([hit])
    assert anchor in ctx
    assert ctx.count("Đoạn đệm") < 800


def test_whole_context_with_source_headers_stays_within_budget():
    """Đầu mục "[n] Nguồn: …" và dấu ngăn cách cũng nằm trong trần tổng: câu 133 của
    answer_set từng có ngữ cảnh 15 463 ký tự trên trần 14 920 (đo 2026-10-07)."""
    llm = get_settings().llm
    results = [
        _r("c", parent_text="\n\n".join(f"Đoạn {i} của mục {k}." for i in range(800)))
        for k in range(5)
    ]
    ctx, _ = context_builder.build_context_and_citations(results)
    assert len(ctx) <= llm.total_context_chars
