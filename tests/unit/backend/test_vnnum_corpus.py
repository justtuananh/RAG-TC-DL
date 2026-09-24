"""Quét corpus QTKĐ thật: mọi khoảng ``÷`` và sai số ``±`` phải phân tích được.

Cổng Sprint 3 yêu cầu bộ test vnnum phủ mọi biến thể số gặp trong corpus; test
này chạy trực tiếp trên Markdown đã commit thay vì chỉ bảng gán tay.
"""

from __future__ import annotations

import re

import pytest

from knowledge.vnnum import parse_range, parse_tolerance

_RANGE_RE = re.compile(r"\(([^()]*÷[^()]*)\)")
_TOLERANCE_RE = re.compile(r"±\s*([0-9][0-9 .,]*)")


def _markdown_files(repo_root):
    return sorted((repo_root / "build" / "spike_a").glob("*.md"))


def test_corpus_has_expected_files(repo_root):
    assert len(_markdown_files(repo_root)) == 7


def test_every_corpus_range_parses(repo_root):
    found = 0
    for path in _markdown_files(repo_root):
        text = path.read_text(encoding="utf-8")
        for match in _RANGE_RE.finditer(text):
            parsed = parse_range(match.group(1))
            assert parsed is not None, (path.name, match.group(1))
            assert parsed.low is not None and parsed.high is not None
            found += 1
    assert found >= 3


def test_every_corpus_tolerance_parses(repo_root):
    found = 0
    for path in _markdown_files(repo_root):
        text = path.read_text(encoding="utf-8")
        for match in _TOLERANCE_RE.finditer(text):
            parsed = parse_tolerance("± " + match.group(1).strip())
            assert parsed is not None, (path.name, match.group(1))
            assert parsed.plus > 0
            found += 1
    assert found >= 10


@pytest.mark.parametrize(
    "raw, low, high",
    [
        ("0 ÷ 100", 0.0, 100.0),
        ("800 ÷ 1 100", 800.0, 1100.0),
        ("0 ÷ 500", 0.0, 500.0),
    ],
)
def test_known_corpus_ranges(raw, low, high):
    parsed = parse_range(raw)
    assert parsed is not None
    assert parsed.low == pytest.approx(low)
    assert parsed.high == pytest.approx(high)
