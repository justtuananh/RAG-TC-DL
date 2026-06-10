"""_rerank_doc — dựng document cho cross-encoder (tiền tố breadcrumb + cửa sổ neo child).

Thuần CPU, không network: hàm chỉ thao tác chuỗi trên payload/parent đã có.
"""

from retrieval.retriever import RERANK_DOC_CAP, _rerank_doc


def _payload(text, file_stem="QTKD_1.063_2021_BPL", section_path="4 > 4.1"):
    return {"text": text, "file_stem": file_stem, "section_path": section_path}


def test_short_parent_prefixed_in_full():
    parent = {"text": "## 4.1 Điều kiện kiểm định\n\n- Nhiệt độ: (23 ± 5) oC"}
    doc = _rerank_doc(_payload("- Nhiệt độ: (23 ± 5) oC"), parent)
    assert doc.startswith("QTKD_1.063_2021_BPL — 4 > 4.1\n")
    assert parent["text"] in doc  # ngắn hơn CAP → giữ nguyên toàn bộ


def test_long_parent_windows_around_child():
    heading = "### 6.3.3 Xác định độ chính xác"
    filler = "x" * (RERANK_DOC_CAP * 3)
    child = "ĐKĐBĐ kiểu B lấy từ giấy chứng nhận hiệu chuẩn (k = 2) của quả cân"
    parent = {"text": f"{heading}\n{filler}\n{child}\nphần đuôi sau child"}
    doc = _rerank_doc(_payload(child), parent)
    assert child[:80] in doc  # nội dung child phải nằm trong cửa sổ
    assert doc.splitlines()[1] == heading  # heading giữ lại khi cửa sổ rời đầu mục
    # tiền tố + heading + "…" + cửa sổ — không vượt quá CAP quá nhiều
    assert len(doc) <= RERANK_DOC_CAP + len(heading) + 100


def test_long_parent_child_near_start_keeps_lead():
    child = "Phương tiện kiểm định gồm áp kế chuẩn"
    parent = {"text": child + " " + "y" * (RERANK_DOC_CAP * 2)}
    doc = _rerank_doc(_payload(child), parent)
    # child ở đầu → cửa sổ bắt đầu từ 0, không chèn "…"
    assert "\n…" not in doc
    assert child in doc


def test_missing_parent_falls_back_to_child_text():
    doc = _rerank_doc(_payload("chỉ có child"), None)
    assert doc == "QTKD_1.063_2021_BPL — 4 > 4.1\nchỉ có child"


def test_child_not_found_in_parent_uses_lead_window():
    parent = {"text": "## heading\n" + "z" * (RERANK_DOC_CAP * 2)}
    doc = _rerank_doc(_payload("child không xuất hiện trong parent"), parent)
    assert doc.splitlines()[1].startswith("## heading")  # fallback: đầu mục
