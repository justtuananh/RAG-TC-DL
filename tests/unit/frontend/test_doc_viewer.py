"""Document viewer + chat handler — app.build_doc_viewer_html / _md_to_html / bot_fn.

Test thẳng các hàm thuần (không dựng Gradio runtime). bot_fn được drive bằng cách
mock retrieve + _stream_ollama.
"""

import app


def _r(
    child_text,
    parent_text=None,
    kind="paragraph",
    file_stem="QTKD_1.061_2021_ND_V2",
    section="6 Tiến hành > 6.1 Đo",
    score=0.5,
):
    return {
        "payload": {
            "text": child_text,
            "kind": kind,
            "file_stem": file_stem,
            "section_path": section,
        },
        "parent_payload": {"text": parent_text} if parent_text else None,
        "rerank_score": score,
    }


def test_empty_results_returns_empty_viewer():
    assert app.build_doc_viewer_html([]) == app._EMPTY_VIEWER
    assert "Kết quả tìm kiếm sẽ hiển thị ở đây." in app._EMPTY_VIEWER


def test_inline_highlight_when_child_in_parent():
    html = app.build_doc_viewer_html([_r("đoạn con", parent_text="trước đoạn con sau")])
    assert '<mark class="qtkd-hl">đoạn con</mark>' in html


def test_table_child_uses_fallback_block():
    table = "| a | b |\n| --- | --- |\n| 1 | 2 |"
    html = app.build_doc_viewer_html([_r(table, parent_text="văn bản khác", kind="table")])
    assert "Đoạn được truy xuất" in html


def test_section_path_is_html_escaped():
    html = app.build_doc_viewer_html([_r("c", section="A <b> C")])
    assert "&lt;b&gt;" in html
    assert "<b>" not in html


def test_card_shows_metadata():
    html = app.build_doc_viewer_html([_r("c", kind="formula", score=0.42)])
    assert "[1]" in html
    assert "QTKD_1.061_2021_ND_V2" in html
    assert app._KIND_ICON["formula"] in html
    assert "0.42" in html


def test_md_to_html_keeps_inline_dollar_math():
    out = app._md_to_html("Công thức $x^2$ ở đây")
    assert "$x^2$" in out


def test_md_to_html_renders_table():
    out = app._md_to_html("| a | b |\n| --- | --- |\n| 1 | 2 |")
    assert "<table" in out


def test_bot_fn_no_results(monkeypatch):
    monkeypatch.setattr(app, "retrieve", lambda q, **k: [])
    *_, last = app.bot_fn([["câu hỏi", None]])
    hist, _doc = last
    assert hist[-1][1] == "Không tìm thấy thông tin liên quan trong tài liệu QTKĐ."


def test_bot_fn_with_results_streams_and_appends_citations(monkeypatch):
    monkeypatch.setattr(app, "retrieve", lambda q, **k: [_r("nội dung")])
    monkeypatch.setattr(app, "_stream_ollama", lambda msgs: iter(["Trả ", "lời"]))
    *_, last = app.bot_fn([["câu hỏi", None]])
    hist, _doc = last
    assert hist[-1][1].startswith("Trả lời")
    assert "Nguồn tham khảo" in hist[-1][1]


def test_bot_fn_retrieve_error_is_shown(monkeypatch):
    def boom(q, **k):
        raise RuntimeError("qdrant chết")

    monkeypatch.setattr(app, "retrieve", boom)
    *_, last = app.bot_fn([["câu hỏi", None]])
    hist, _doc = last
    assert "Lỗi tìm kiếm" in hist[-1][1]
