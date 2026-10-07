"""Cửa sổ ngữ cảnh của một mục dài - retrieval.context_builder.window.

Mục dài hơn ngân sách được cắt quanh các đoạn neo (đoạn con khớp của mục, theo thứ hạng RRF):
mỗi đoạn neo kéo theo công thức nó nói tới, lần lượt theo thứ hạng tới hết ngân sách, rồi phần
dư mở rộng quanh các đoạn neo. QTKĐ 1.159 mục 6.3.2 (đo 2026-10-07): đoạn khớp thứ ba dẫn vào
công thức kết luận $A_{0t}$ ở cuối mục bị bỏ, vì chỉ 2 đoạn neo được giữ và đầu mục (bảng điểm
áp suất, không liên quan) luôn chiếm một phần ngân sách.
"""

from retrieval.context_builder import window

HEADING = "### 6.3.2 Xác định diện tích hiệu dụng"
TABLE = "| Cấp chính xác | Số điểm đo |\n| --- | --- |\n" + "\n".join(
    f"| 0,0{i} | {i} |" for i in range(1, 30)
)
P_LEAD = "- Áp suất chuẩn tại điểm kiểm tra thứ i được tính theo công thức sau:"
P_FORMULA = "| $P_{s,i} = \\frac{\\sum M_{i,s}g}{A_{0s}}$ |  |\n| --- | --- |"
A0S_DEF = "$A_{0s}$ là diện tích hiệu dụng của píttông của áp kế píttông chuẩn, m2;"
A_LEAD = "$A_{0t,i}$ là diện tích hiệu dụng của píttông của AKKĐ được tính từ công thức sau:"
A_FORMULA = "| $A_{0t,i} = \\frac{\\sum M_{t,i}g}{P_{s,i}}$ |  |\n| --- | --- |"
M_T_DEF = "$\\sum M_{t,i}$ là tổng khối lượng trên AKKĐ, kg;"
T_DEF = "$t_{t}$ là nhiệt độ píttông/xilanh của AKKĐ, oC;"
R_STEP = "- Xác định hệ số tuyến tính R"
FINAL_LEAD = "Diện tích hiệu dụng píttông của AKKĐ và hệ số giãn nở áp suất λ xác định như sau:"
FINAL_FORMULA = "| $A_{0t} = \\overline{A}$ / λ = 0 |  |\n| --- | --- |"
LAST = "So sánh A0t với giá trị diện tích hiệu dụng do nhà sản xuất công bố."

BLOCKS = [
    HEADING,
    "6.3.2.1 Xác định điểm áp suất kiểm định",
    TABLE,
    P_LEAD,
    P_FORMULA,
    "trong đó:",
    "$\\sum M_{i,s}$ là tổng khối lượng của píttông chuẩn, kg;",
    "g là gia tốc trọng trường nơi đo, m/s2;",
    A0S_DEF,
    "h là khoảng cách giữa hai mặt đáy của hai píttông, m.",
    "- Áp suất chuẩn trong chế độ đo áp suất tuyệt đối được tính theo công thức sau:",
    "| $P_{abs} = P_{s,i} + \\mu$ |  |\n| --- | --- |",
    "Vị trí đáy của píttông khi cân bằng là vị trí trùng với mốc cơ sở áp suất.",
    A_LEAD,
    A_FORMULA,
    "trong đó:",
    M_T_DEF,
    T_DEF,
    R_STEP,
    FINAL_LEAD,
    FINAL_FORMULA,
    LAST,
]
PARENT = "\n\n".join(BLOCKS)
A_UNIT = (A_LEAD, A_FORMULA, "trong đó:", M_T_DEF, T_DEF)


def _size(*blocks: str) -> int:
    return sum(len(b) + 2 for b in blocks)


def test_every_anchor_that_fits_is_kept_with_its_formula():
    budget = _size(P_LEAD, P_FORMULA, "trong đó:", A0S_DEF, A_LEAD, A_FORMULA, FINAL_LEAD) + 400
    out = window(PARENT, [A_LEAD, A0S_DEF, FINAL_LEAD], budget)
    for text in (A_LEAD, A_FORMULA, A0S_DEF, P_FORMULA, FINAL_LEAD, FINAL_FORMULA):
        assert text in out


def test_anchors_are_taken_in_rank_order_until_the_budget_is_spent():
    budget = _size(*A_UNIT) + 60
    out = window(PARENT, [A_LEAD, FINAL_LEAD], budget)
    assert A_LEAD in out and A_FORMULA in out
    assert FINAL_LEAD not in out
    assert len(out) <= budget


def test_section_start_is_not_kept_when_no_anchor_needs_it():
    budget = _size(A_LEAD, A_FORMULA, FINAL_LEAD, FINAL_FORMULA) + 300
    out = window(PARENT, [A_LEAD, FINAL_LEAD], budget)
    assert HEADING not in out
    assert TABLE not in out


def test_definition_anchor_brings_the_formula_it_defines():
    """Dòng "trong đó: $A_{0s}$ là …" xa công thức $P_{s,i}$ vẫn kéo công thức đó vào."""
    budget = _size(P_LEAD, P_FORMULA, "trong đó:", A0S_DEF) + 100
    out = window(PARENT, [A0S_DEF], budget)
    assert P_FORMULA in out
    assert out.index(P_FORMULA) < out.index(A0S_DEF)


def test_lead_in_anchor_brings_the_formula_and_its_definitions():
    """Câu dẫn ":" kéo công thức sau nó và danh sách "trong đó" định nghĩa ký hiệu.

    Thiếu định nghĩa $t_{t}$ thì model tự bịa nghĩa của ký hiệu (QTKĐ 1.159 6.3.2).
    """
    out = window(PARENT, [A_LEAD], _size(*A_UNIT) + 60)
    assert A_FORMULA in out
    assert T_DEF in out


def test_leftover_budget_grows_around_the_top_anchor():
    out = window(PARENT, [A_LEAD], _size(*BLOCKS[12:19]) + 40)
    assert "Vị trí đáy của píttông" in out
    assert R_STEP in out


def test_whole_blocks_never_exceed_the_budget():
    for budget in (300, 600, 900, 1500, 2000):
        assert len(window(PARENT, [A_LEAD, A0S_DEF, FINAL_LEAD], budget)) <= budget


def test_adjacent_blocks_are_not_separated_by_ellipsis():
    out = window(PARENT, [A_LEAD], _size(*A_UNIT) + 60)
    assert A_LEAD + "\n\n" + A_FORMULA in out
    assert "\n…\n" not in out


def test_skipped_text_is_marked_with_ellipsis():
    budget = _size(P_LEAD, P_FORMULA, FINAL_LEAD, FINAL_FORMULA) + 30
    out = window(PARENT, [P_LEAD, FINAL_LEAD], budget)
    assert out.startswith("…\n")
    assert "\n…\n" in out
    assert out.endswith("\n…")


def test_anchor_inside_a_block_larger_than_the_budget_is_trimmed_around_it():
    """Không chia được theo khối (mục một dòng): cắt quanh đoạn neo, vẫn giữ đoạn neo."""
    child = "Sai số tương đối của H3000 không được vượt quá ± 0,1 %."
    parent = "C" * 5000 + " " + child + " " + "D" * 5000
    out = window(parent, [child], 1000)
    assert child in out
    assert len(out) <= 1000 + 4


def test_trimmed_window_never_cuts_a_formula_line():
    formula = "| $P_{s,i} = \\frac{\\sum M_{i,s} g}{A_{0s}(1 + \\lambda_{s}P_{s,i})} + (\\rho_{f} - \\rho_{a})gh$ |  |"
    child = "$A_{0s}$ là diện tích hiệu dụng"
    parent = ("đệm\n" * 400) + formula + "\n" + child + "\n" + ("đệm\n" * 400)
    out = window(parent, [child], 1000)
    lines = [line.strip("…") for line in out.splitlines()]
    assert all(("$" not in line) or line in (formula, child) for line in lines)
    assert formula in lines
    assert child in out


def test_anchor_missing_from_the_section_falls_back_to_its_start():
    out = window(PARENT, ["đoạn không có trong mục"], 400)
    assert out.startswith(HEADING)
    assert out.endswith("…")
