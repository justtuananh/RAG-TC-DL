"""Số trang lấy từ Mục lục của tài liệu."""

from retrieval import doc_pages

TOC = [
    "Mục lục",
    "1 Phạm vi áp dụng 5",
    "5 Điều kiện và chuẩn bị kiểm định 6",
    "5.1 Điều kiện kiểm định 6",
    "6 Tiến hành kiểm định 9",
    "6.3 Kiểm tra đo lường 12",
    "Xác định sai số đo áp suất. 9",
    "Phụ lục A (Quy định) Mẫu Biên bản kiểm định 13",
    "",
    "Lời nói đầu",
]


def _use(monkeypatch):
    monkeypatch.setattr(doc_pages, "_toc", lambda stem: doc_pages.parse_toc(TOC))


def test_parse_toc_keeps_sections_and_appendix():
    toc = doc_pages.parse_toc(TOC)
    assert toc["5.1"][0] == 6 and toc["6.3"][0] == 12 and toc["Phụ lục A"][0] == 13


def test_exact_page(monkeypatch):
    _use(monkeypatch)
    assert doc_pages.page_for("S", "5 Điều kiện và chuẩn bị kiểm định > 5.1 Điều kiện kiểm định") == (6, True)
    assert doc_pages.label("S", "5 Điều kiện và chuẩn bị kiểm định > 5.1 Điều kiện kiểm định") == "tr. 6"


def test_deeper_section_uses_parent_and_is_marked(monkeypatch):
    _use(monkeypatch)
    assert doc_pages.page_for("S", "6 Tiến hành kiểm định > 6.3 Kiểm tra đo lường > 6.3.2 Xác định độ chênh áp") == (12, False)
    assert doc_pages.label("S", "6 Tiến hành kiểm định > 6.3 Kiểm tra đo lường > 6.3.2 Xác định độ chênh áp") == "từ tr. 12"


def test_title_mismatch_gives_no_page(monkeypatch):
    _use(monkeypatch)
    assert doc_pages.page_for("S", "5.1 Một mục hoàn toàn khác tên") == (None, False)


def test_appendix_and_unknown(monkeypatch):
    _use(monkeypatch)
    assert doc_pages.page_for("S", "Phụ lục A (Quy định) Mẫu Biên bản kiểm định") == (13, True)
    assert doc_pages.page_for("S", "Lời nói đầu") == (None, False)


def test_missing_file_has_no_page(monkeypatch):
    monkeypatch.setattr(doc_pages, "_toc", lambda stem: {})
    assert doc_pages.page_for("S", "5.1 X") == (None, False)
