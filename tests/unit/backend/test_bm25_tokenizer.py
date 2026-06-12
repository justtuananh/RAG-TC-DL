"""BM25 tokenizer — KHÓA value-prop: giữ nguyên mã/đơn vị kỹ thuật.

retrieval.bm25_index.tokenize cố tình KHÔNG tách `.` `:` `%` `-` để mã QTKĐ
(1.061:2021), đơn vị (MPa, bar), kích cỡ (DN50) và phần trăm (0.05%) còn nguyên —
dense embedding làm mờ những token này nên BM25 phải bắt chính xác.
"""

from retrieval.bm25_index import _SPLIT_RE, tokenize


def test_keeps_technical_codes_and_units():
    assert tokenize("1.061:2021 MPa bar DN50 0.05%") == [
        "1.061:2021",
        "mpa",
        "bar",
        "dn50",
        "0.05%",
    ]


def test_lowercases():
    assert tokenize("MPa BAR DN50") == ["mpa", "bar", "dn50"]


def test_does_not_split_dot_colon_percent_hyphen():
    assert tokenize("0.6") == ["0.6"]
    assert tokenize("1.061:2021") == ["1.061:2021"]
    assert tokenize("50-60") == ["50-60"]
    assert tokenize("0.05%") == ["0.05%"]


def test_splits_on_whitespace_punctuation_brackets():
    assert tokenize("a,b;c") == ["a", "b", "c"]
    assert tokenize("(x)[y]{z}") == ["x", "y", "z"]
    assert tokenize("a<b>c") == ["a", "b", "c"]
    assert tokenize('a!b"c') == ["a", "b", "c"]
    assert tokenize("a\\b|c") == ["a", "b", "c"]


def test_drops_empty_tokens():
    assert tokenize("a   b\t\nc") == ["a", "b", "c"]
    assert tokenize("   ") == []


def test_split_re_does_not_include_value_chars():
    # Regression guard: nếu ai thêm . : % - / vào _SPLIT_RE thì mã kỹ thuật sẽ vỡ.
    for ch in ".:%-/":
        assert not _SPLIT_RE.match(ch), f"_SPLIT_RE không được tách ký tự {ch!r}"
