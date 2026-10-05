"""Builder ngữ cảnh + trích dẫn - retrieval.context_builder.build_context_and_citations.

Context dùng PARENT text (đủ ngữ cảnh) cắt theo llm.context.max_block_chars; citations
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


def test_per_source_cap_truncates_huge_parent():
    # 1 nguồn lớn → cắt ở max_block_chars (không phình ~20k gây chôn fact + 500 Ollama).
    long = "A" * (_cap() + 5000)
    ctx, _ = context_builder.build_context_and_citations([_r("c", parent_text=long)])
    assert "…" in ctx
    assert "A" * _cap() in ctx
    assert "A" * (_cap() + 1) not in ctx


def test_short_parent_not_truncated():
    # Parent dưới cap KHÔNG bị cắt.
    short = "B" * (_cap() - 200)
    ctx, _ = context_builder.build_context_and_citations([_r("c", parent_text=short)])
    assert short in ctx


def test_no_source_exceeds_cap_even_with_donation():
    # Nguồn ngắn nhường quota, nhưng KHÔNG nguồn nào vượt max_block_chars.
    short = "x" * 50
    big = "Y" * (_cap() + 4000)
    results = [_r("c", parent_text=short)] * 4 + [_r("c", parent_text=big)]
    ctx, _ = context_builder.build_context_and_citations(results)
    assert "Y" * _cap() in ctx
    assert "Y" * (_cap() + 1) not in ctx


def test_short_sources_donate_budget_to_an_earlier_long_source():
    """Phần dư của nguồn ngắn về CẢ nguồn đứng trước (không chỉ nguồn sau): nguồn top dài
    (QTKĐ 1.159 mục 6.3.2) được dùng ngân sách mà các nguồn sau ngắn không cần."""
    llm = get_settings().llm
    n = 5
    fair = llm.total_context_chars // n
    long = "L" * (llm.context.max_block_chars + 1000)
    results = [_r("c", parent_text=long)] + [_r("c", parent_text="s" * 100)] * (n - 1)
    ctx, _ = context_builder.build_context_and_citations(results)
    assert fair < llm.context.max_block_chars  # nếu không, test không phân biệt được
    assert "L" * llm.context.max_block_chars in ctx


def test_total_context_stays_within_budget():
    llm = get_settings().llm
    big = "Z" * (llm.context.max_block_chars * 2)
    results = [_r("c", parent_text=big)] * 8
    ctx, _ = context_builder.build_context_and_citations(results)
    assert ctx.count("Z") <= llm.total_context_chars


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


def test_long_parent_keeps_the_retrieved_child():
    """Đoạn con được truy hồi nằm cuối mục dài vẫn phải có trong ngữ cảnh.

    QTKĐ 1.071 mục 5.3 dài ~3 500 ký tự; câu "Sai số tương đối của H3000 không được vượt
    quá ± 0,1 %." ở cuối mục bị cắt mất khi luôn lấy 2 400 ký tự đầu, model từ chối oan.
    """
    child = "Sai số tương đối của H3000 không được vượt quá ± 0,1 %."
    parent = "C" * (_cap() + 1000) + "\n" + child
    ctx, _ = context_builder.build_context_and_citations([_r(child, parent_text=parent)])
    assert child in ctx
    block = ctx.split("---\n", 1)[1]
    assert len(block) <= _cap() + 3  # + "\n…\n"


def test_long_parent_keeps_its_start_when_the_child_is_far_from_it():
    """Đoạn con là dòng "trong đó" ở cuối mục: công thức ở đầu mục vẫn phải có.

    QTKĐ 1.159 mục 6.3.1: công thức khối lượng quy đổi M ở ký tự 348, đoạn con được truy
    hồi ("$A_{0s}$ là diện tích hiệu dụng…") ở ký tự 3 449.
    """
    formula = "$M = P A_{0} g_{0} / g$"
    child = "$A_{0s}$ là diện tích hiệu dụng của píttông của áp kế píttông chuẩn, m2;"
    parent = formula + "E" * (_cap() + 1000) + child + "F" * 500
    ctx, _ = context_builder.build_context_and_citations([_r(child, parent_text=parent)])
    block = ctx.split("---\n", 1)[1]
    assert block.startswith(formula)
    assert child in block
    assert "\n…\n" in block


def test_long_parent_keeps_its_start_when_child_is_near_it():
    child = "Đoạn đầu mục."
    parent = child + "D" * (_cap() + 1000)
    ctx, _ = context_builder.build_context_and_citations([_r(child, parent_text=parent)])
    block = ctx.split("---\n", 1)[1]
    assert block.startswith(child)
    assert block.endswith("…")


def test_long_parent_keeps_every_anchor_of_the_section():
    """Mục dài có nhiều đoạn con khớp: ngữ cảnh giữ quanh CẢ các đoạn neo theo thứ hạng.

    QTKĐ 1.159 mục 6.3.2 (5 623 ký tự): đoạn đại diện là "$A_{0s}$ là diện tích hiệu
    dụng…" (ký tự 1 997), công thức diện tích hiệu dụng (10) của AKKĐ ở ký tự 3 967 ngay
    sau đoạn khớp thứ hai; chỉ neo đoạn đầu thì model báo "không tìm thấy".
    """
    first = "$A_{0s}$ là diện tích hiệu dụng của píttông chuẩn, m2;"
    second = "$A_{0t,i}$ là diện tích hiệu dụng của AKKĐ được tính từ công thức sau:"
    formula = "| $A_{0t,i}(1 + \\lambda_{t}P_{s,i}) = \\frac{M g}{P_{s,i}}$ |  |"
    filler = "dòng đệm của mục dài\n" * 120
    parent = (
        "Đầu mục\n" + filler + first + "\n" + filler + second + "\n\n" + formula + "\n" + filler
    )
    hit = _r(first, parent_text=parent)
    hit["anchor_texts"] = [first, second]
    ctx, _ = context_builder.build_context_and_citations([hit])
    block = ctx.split("---\n", 1)[1]
    assert block.startswith("Đầu mục")
    assert first in block and second in block
    assert formula in block


def test_window_never_cuts_a_formula_line():
    """Cửa sổ cắt theo dòng: một dòng công thức hoặc có trọn, hoặc không có."""
    formula = "| $P_{s,i} = \\frac{\\sum M_{i,s} g}{A_{0s}(1 + \\lambda_{s}P_{s,i})} + (\\rho_{f} - \\rho_{a})gh$ |  |"
    child = "$A_{0s}$ là diện tích hiệu dụng"
    parent = ("đệm\n" * 400) + formula + "\n" + child + "\n" + ("đệm\n" * 400)
    ctx, _ = context_builder.build_context_and_citations([_r(child, parent_text=parent)])
    block = ctx.split("---\n", 1)[1]
    lines = [line.strip("…") for line in block.splitlines()]
    assert all(("$" not in line) or line in (formula, child) for line in lines)
    assert formula in lines
    assert child in block


def test_anchor_introducing_a_formula_keeps_what_follows():
    """Đoạn neo kết thúc bằng ":" dẫn vào công thức + "trong đó": giữ phần phía sau nó.

    QTKĐ 1.159 mục 6.3.2: "$A_{0t,i}$ … được tính từ công thức sau:" nằm vừa trong ngân
    sách đầu mục nhưng công thức (10) và định nghĩa $t_{t}$, $t_{r}$ thì không; model tự
    bịa nghĩa của ký hiệu.
    """
    budget = get_settings().llm.context.max_block_chars
    intro = "$A_{0t,i}$ là diện tích hiệu dụng của AKKĐ được tính từ công thức sau:"
    tail = "\n| $A_{0t,i} = x$ |  |\n" + "".join(
        f"$k_{{{i}}}$ là ký hiệu thứ {i};\n" for i in range(20)
    )
    parent = "đệm đầu mục\n" * ((budget - 300) // 12) + intro + tail + "đệm cuối\n" * 300
    hit = _r(intro, parent_text=parent)
    ctx, _ = context_builder.build_context_and_citations([hit])
    block = ctx.split("---\n", 1)[1]
    assert intro in block
    assert "$k_{19}$ là ký hiệu thứ 19;" in block
