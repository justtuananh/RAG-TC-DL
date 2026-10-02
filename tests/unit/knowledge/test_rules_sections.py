"""Chia mục QTKĐ theo tiêu đề và tra mục an toàn (không khớp → None)."""

from __future__ import annotations

from knowledge.rules.sections import find_section, split_sections

SAMPLE = """\
# 1 Phạm vi áp dụng

Nội dung phạm vi.

## 5.1 Điều kiện kiểm định

Nội dung điều kiện.

# 7 Xử lý chung

Chu kỳ kiểm định của Van an toàn là 12 tháng;
"""


def test_split_sections_extracts_number_title_and_body():
    sections = split_sections(SAMPLE)
    paths = [section.path for section in sections]
    assert paths == ["1 Phạm vi áp dụng", "5.1 Điều kiện kiểm định", "7 Xử lý chung"]
    assert sections[0].number == "1"
    assert sections[1].number == "5.1"
    assert "Nội dung phạm vi." in sections[0].body
    assert "12 tháng" in sections[2].body


def test_section_body_offsets_are_absolute():
    text = SAMPLE
    section = find_section(split_sections(text), "xử lý chung")
    assert section is not None
    assert text[section.body_start : section.end] == section.body


def test_find_section_requires_all_keywords():
    sections = split_sections(SAMPLE)
    assert find_section(sections, "phạm vi") is not None
    assert find_section(sections, "điều kiện") is not None
    # "phạm vi" và "điều kiện" không cùng một tiêu đề → None.
    assert find_section(sections, "phạm vi", "điều kiện") is None


def test_find_section_returns_none_when_absent():
    assert find_section(split_sections(SAMPLE), "thuật ngữ") is None


def test_split_sections_without_headings():
    assert split_sections("chỉ có văn xuôi") == []
