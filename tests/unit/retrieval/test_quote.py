"""Đoạn trích nguồn - retrieval.quote.build_quote.

Đoạn con khớp nhất của một mục thường là dòng "trong đó: X là …" hoặc câu dẫn "… công thức
sau:", còn công thức là một đoạn con riêng (chỉ có LaTeX) ít khi lọt top. Panel nguồn phải
hiện cả công thức mà dòng đó nói tới (QTKĐ 1.159 mục 6.3.2, đo 2026-10-05).
"""

from retrieval.quote import build_quote

P_LEAD = "- Áp suất chuẩn tại điểm kiểm tra thứ i được tính theo công thức sau:"
P_FORMULA = "| $P_{s,i} = \\frac{\\sum M_{i,s}g}{A_{0s}}$ |  |\n| --- | --- |"
A_LEAD = "$A_{0t,i}$ là diện tích hiệu dụng của píttông của AKKĐ được tính từ công thức sau:"
A_FORMULA = "| $A_{0t,i} = \\frac{\\sum M_{t,i}g}{P_{s,i}}$ |  |\n| --- | --- |"
A0S_DEF = "$A_{0s}$ là diện tích hiệu dụng của píttông của áp kế píttông chuẩn, m2;"

PARENT = "\n\n".join(
    [
        "### 6.3.2 Xác định diện tích hiệu dụng",
        "6.3.2.2 Quá trình tính toán",
        P_LEAD,
        P_FORMULA,
        "trong đó:",
        "$\\sum M_{i,s}$ là tổng khối lượng, kg;",
        "g là gia tốc trọng trường nơi đo, m/s2;",
        A0S_DEF,
        "h là khoảng cách giữa hai mặt đáy của hai píttông, m.",
        A_LEAD,
        A_FORMULA,
        "trong đó:",
        "$\\sum M_{t,i}$ là tổng khối lượng trên AKKĐ, kg;",
        "- Xác định hệ số tuyến tính R",
    ]
)


def test_definition_line_brings_the_formula_it_defines():
    quote = build_quote(PARENT, [A0S_DEF])
    assert P_FORMULA in quote
    assert quote.index(P_LEAD) < quote.index(P_FORMULA) < quote.index(A0S_DEF)
    assert "trong đó:" in quote


def test_definition_line_skips_the_other_definitions_with_ellipsis():
    quote = build_quote(PARENT, [A0S_DEF])
    assert "gia tốc trọng trường" not in quote
    assert "…" in quote


def test_lead_in_brings_the_formula_after_it():
    quote = build_quote(PARENT, [A_LEAD])
    assert quote == A_LEAD + "\n\n" + A_FORMULA


def test_formula_child_brings_its_lead_in():
    quote = build_quote(PARENT, [A_FORMULA])
    assert quote == A_LEAD + "\n\n" + A_FORMULA


def test_several_anchors_follow_document_order():
    quote = build_quote(PARENT, [A_LEAD, A0S_DEF])
    assert quote.index(P_FORMULA) < quote.index(A0S_DEF) < quote.index(A_FORMULA)


def test_adjacent_blocks_are_not_separated_by_ellipsis():
    quote = build_quote(PARENT, [A_LEAD, A_FORMULA])
    assert quote == A_LEAD + "\n\n" + A_FORMULA


def test_plain_paragraph_is_quoted_alone():
    text = "6.3.2.2 Quá trình tính toán"
    assert build_quote(PARENT, [text]) == text


def test_definition_without_formula_above_is_quoted_alone():
    parent = "\n\n".join(["Đoạn mở đầu.", "trong đó:", "g là gia tốc trọng trường, m/s2;"])
    assert build_quote(parent, ["g là gia tốc trọng trường, m/s2;"]) == (
        "g là gia tốc trọng trường, m/s2;"
    )


def test_anchor_missing_from_parent_is_quoted_verbatim():
    assert build_quote(PARENT, ["đoạn không có trong mục"]) == "đoạn không có trong mục"


def test_no_anchor_gives_empty_quote():
    assert build_quote(PARENT, []) == ""


def test_inline_trong_do_definition_brings_the_formula():
    parent = "\n\n".join(
        ["Giá trị trung bình:", "| $\\bar{x} = \\frac{\\sum x_i}{n}$ |", "Trong đó n là số lần đo."]
    )
    quote = build_quote(parent, ["Trong đó n là số lần đo."])
    assert quote.startswith("Giá trị trung bình:")
    assert quote.endswith("Trong đó n là số lần đo.")
