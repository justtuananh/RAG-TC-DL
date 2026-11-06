from retrieval import doc_titles
from retrieval.context_builder import _source_header


def test_parse_title_multiline_until_procedure_marker():
    head = [
        "QTKĐ QUY TRÌNH KIỂM ĐỊNH",
        "",
        "QTKĐ 1.160 : 2021",
        "ÁP KẾ CHUẨN HIỆN SỐ VÀ LÒ XO",
        "CÓ PHẠM VI ĐO (-1 ĐẾN 5 000) bar,",
        "QUY TRÌNH KIỂM ĐỊNH",
        "Hà Nội",
    ]
    assert (
        doc_titles.parse_title(head)
        == "ÁP KẾ CHUẨN HIỆN SỐ VÀ LÒ XO CÓ PHẠM VI ĐO (-1 ĐẾN 5 000) bar,"
    )


def test_parse_title_without_code_line_is_empty():
    assert doc_titles.parse_title(["Mục lục", "1 Phạm vi áp dụng"]) == ""


def test_title_for_unknown_stem_is_empty():
    assert doc_titles.title_for("khong_ton_tai_xyz") == ""


def test_source_header_has_title_only_when_known(monkeypatch):
    monkeypatch.setattr(doc_titles, "title_for", lambda s: "THIẾT BỊ A" if s == "S1" else "")
    assert (
        _source_header(2, {"file_stem": "S1", "section_path": "5.1"})
        == "[2] Nguồn: S1 (THIẾT BỊ A) — 5.1\n---\n"
    )
    assert (
        _source_header(3, {"file_stem": "S2", "section_path": "5.1"})
        == "[3] Nguồn: S2 — 5.1\n---\n"
    )
