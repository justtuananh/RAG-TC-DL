"""Helpers OOXML — ingestion.extract_docx (thuần lxml, không Ruby/Docker).

_heading_level chỉ tin style heading rõ ràng (KHÓA bug QTKD_1.071: bullet/list-item
từng bị nhận nhầm là heading). _table_md dựng Markdown + escape '|'.
"""

from lxml import etree

from ingestion.extract_docx import _heading_level, _local, _q, _table_md

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
