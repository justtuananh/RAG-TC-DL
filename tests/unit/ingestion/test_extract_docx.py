"""Helpers OOXML — ingestion.extract_docx (thuần lxml, không Ruby/Docker).

_heading_level chỉ tin style heading rõ ràng (KHÓA bug QTKD_1.071: bullet/list-item
từng bị nhận nhầm là heading). _table_md dựng Markdown + escape '|'.
"""

from lxml import etree

from ingestion.extract_docx import _heading_level, _load_styles, _local, _q, _table_md

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _p(style):
    if style is None:
        return etree.fromstring(f'<w:p xmlns:w="{W}"><w:r><w:t>hi</w:t></w:r></w:p>')
    return etree.fromstring(f'<w:p xmlns:w="{W}"><w:pPr><w:pStyle w:val="{style}"/></w:pPr></w:p>')


def test_heading_level_from_explicit_style():
    assert _heading_level(_p("heading1")) == 1
    assert _heading_level(_p("heading2")) == 2
    assert _heading_level(_p("Heading3")) == 3  # không phân biệt hoa thường


def test_heading_level_rejects_toc_and_title():
    assert _heading_level(_p("toc1")) is None
    assert _heading_level(_p("title")) is None
    assert _heading_level(_p("tieude")) is None


def test_heading_level_none_without_pstyle():
    assert _heading_level(_p(None)) is None


def test_heading_level_localized_name():
    """K13: style có ``w:name`` là "heading N" vẫn là heading dù styleId khác."""
    assert _heading_level(_p("TieuDeMuc1"), {"TieuDeMuc1": ("heading 1", "Normal")}) == 1


def test_heading_level_follows_based_on_chain():
    """K13: đi theo chuỗi ``basedOn`` để lấy cấp của style heading gốc."""
    styles = {"MucCon2": ("Muc con 2", "TieuDeMuc1"), "TieuDeMuc1": ("heading 2", "Normal")}
    assert _heading_level(_p("MucCon2"), styles) == 2


def test_heading_level_excludes_toc_even_when_based_on_heading():
    """K13: style TOC (styleId/tên bắt đầu ``toc``) không thành heading."""
    styles = {"TOCHeading": ("TOC Heading", "Heading1"), "Heading1": ("heading 1", "Normal")}
    assert _heading_level(_p("TOCHeading"), styles) is None


def test_heading_level_unresolved_style_is_none():
    styles = {"Khach": ("Khach hang", "Normal")}
    assert _heading_level(_p("Khach"), styles) is None


def test_load_styles_reads_name_and_based_on(tmp_path):
    """K13: ``_load_styles`` đọc ``w:name``/``w:basedOn`` của style đoạn văn."""
    import zipfile

    styles_xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<w:styles xmlns:w="{W}">'
        '<w:style w:type="paragraph" w:styleId="TieuDeMuc1">'
        '<w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>'
        "</w:style>"
        '<w:style w:type="character" w:styleId="Heading1Char">'
        '<w:name w:val="Heading 1 Char"/>'
        "</w:style>"
        "</w:styles>"
    )
    path = tmp_path / "styles.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/styles.xml", styles_xml)
    with zipfile.ZipFile(path) as archive:
        styles = _load_styles(archive)

    assert styles["TieuDeMuc1"] == ("heading 1", "Normal")
    assert "Heading1Char" not in styles  # chỉ style đoạn văn


def test_q_expands_and_local_strips():
    assert _q("w:t") == f"{{{W}}}t"
    assert _local(f"{{{W}}}t") == "t"
    assert _local("plain") == "plain"


def test_table_md_basic_grid():
    tbl = etree.fromstring(
        f'<w:tbl xmlns:w="{W}">'
        "<w:tr><w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc></w:tr>"
        "<w:tr><w:tc><w:p><w:r><w:t>C</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>D</w:t></w:r></w:p></w:tc></w:tr>"
        "</w:tbl>"
    )
    lines = _table_md(tbl, {}, [], [], [0]).split("\n")
    assert lines[0] == "| A | B |"
    assert lines[1] == "| --- | --- |"
    assert lines[2] == "| C | D |"


def test_table_md_escapes_pipe():
    tbl = etree.fromstring(
        f'<w:tbl xmlns:w="{W}">'
        "<w:tr><w:tc><w:p><w:r><w:t>a|b</w:t></w:r></w:p></w:tc></w:tr>"
        "</w:tbl>"
    )
    assert "a\\|b" in _table_md(tbl, {}, [], [], [0])


# ── Guard: body giả dạng heading ──────────────────────────────────────────────

from ingestion.extract_docx import _is_body_masquerading_as_heading  # noqa: E402


def test_guard_demotes_sentence_heading():
    # Chuỗi THẬT từ QTKD_1.071: câu tiêu chí bị style Heading1 trong .docx,
    # hoisted khỏi mục 5.3 → fact ±0,1 % không còn trong parent 5.3.
    assert _is_body_masquerading_as_heading(
        "Sai số tương đối của H3000 không được vượt quá ± 0,1 %."
    )


def test_guard_demotes_figure_caption():
    assert _is_body_masquerading_as_heading("Hình 1. Sơ đồ kết nối AKC và H3000 cần kiểm định")
    assert _is_body_masquerading_as_heading("Bảng 3 - Số loạt đo, số lượng điểm đo")


def test_guard_demotes_bullets_and_long_sentences():
    assert _is_body_masquerading_as_heading("- Nhiệt độ môi trường: (23 ± 5) oC;")
    assert _is_body_masquerading_as_heading(
        "Sau khi đã tiến hành các bước kiểm tra tại 5.2, tạo áp suất tới áp suất "
        "giới hạn và chịu tải 15 min. Độ tụt áp suất phải đạt yêu cầu"
    )


def test_guard_keeps_real_headings():
    for h in [
        "1 Phạm vi áp dụng",
        "6.2.3 Kiểm tra thời gian quay tự do của píttông",
        "Phụ lục A",
        "(Quy định)",
        "Mẫu biên bản kiểm định (không đạt cấp cho đơn vị)",
        "Đánh giá độ không đảm bảo đo",
        "Áp kế pít tông kiểu H3000-SP-70/700",
    ]:
        assert not _is_body_masquerading_as_heading(h), h


def test_table_md_k07_honors_gridspan_and_vmerge():
    """K07: ô gridSpan chiếm N cột (văn bản ở cột đầu, N-1 cột rỗng); ô vMerge
    tiếp nối để trống, giữ đúng vị trí cột cho bảng Markdown."""
    xml = (
        f'<w:tbl xmlns:w="{W}">'
        "<w:tr>"
        '<w:tc><w:tcPr><w:gridSpan w:val="3"/></w:tcPr>'
        "<w:p><w:r><w:t>Áp suất</w:t></w:r></w:p></w:tc>"
        '<w:tc><w:tcPr><w:vMerge w:val="restart"/></w:tcPr>'
        "<w:p><w:r><w:t>Ghi chú</w:t></w:r></w:p></w:tc>"
        "</w:tr>"
        "<w:tr>"
        "<w:tc><w:p><w:r><w:t>Mở</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>Đóng</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>Độ chênh</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:tcPr><w:vMerge/></w:tcPr>"
        "<w:p><w:r><w:t>bị bỏ</w:t></w:r></w:p></w:tc>"
        "</w:tr>"
        "</w:tbl>"
    )
    md = _table_md(etree.fromstring(xml), {}, [], [], [0])
    lines = md.split("\n")
    assert lines[0] == "| Áp suất |  |  | Ghi chú |"
    assert lines[2] == "| Mở | Đóng | Độ chênh |  |"
