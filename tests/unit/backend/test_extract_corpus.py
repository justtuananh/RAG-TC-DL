"""Bộ luật trích xuất trên corpus QTKĐ thật + bảo vệ xuất xứ P1.

Cổng Sprint 4: mọi dòng trích ra phải truy ngược được nguyên văn — offset ký tự
phải cắt đúng ``quote`` trong văn bản gốc. Và luật phải trả rỗng thay vì đoán
khi mục không khớp.
"""

from __future__ import annotations

from collections import Counter

import pytest

from knowledge.rules import bang1, bang2, chuky, dieukien, extract_all, phamvi, thuatngu

DOCS = [
    "QTKD_1.061_2021_ND_V2",
    "QTKD_1.062_2021_ND",
    "QTKD_1.063_2021_BPL",
    "QTKD_1.071_2022_FINAL",
    "QTKD_1.159_2021_ND_FINAL",
    "QTKD_1.160_2021_ND_FINAL",
    "2023._QTKD_1.190_2023_DPI_610_ND_24.01.24",
]

# (working_range, inspection_step, env_condition, calibration_interval, standard, term)
EXPECTED_COUNTS = {
    "QTKD_1.061_2021_ND_V2": (1, 3, 3, 1, 6, 6),
    "QTKD_1.062_2021_ND": (1, 3, 3, 1, 3, 0),
    "QTKD_1.063_2021_BPL": (1, 3, 3, 1, 5, 0),
    "QTKD_1.071_2022_FINAL": (1, 9, 2, 1, 7, 0),
    "QTKD_1.159_2021_ND_FINAL": (3, 11, 2, 1, 12, 0),
    "QTKD_1.160_2021_ND_FINAL": (1, 4, 2, 1, 10, 0),
    "2023._QTKD_1.190_2023_DPI_610_ND_24.01.24": (1, 5, 2, 1, 8, 0),
}


@pytest.fixture(scope="module")
def md_dir(repo_root):
    return repo_root / "build" / "spike_a"


def _read(md_dir, stem: str) -> str:
    return (md_dir / f"{stem}.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("stem", DOCS)
def test_every_quote_matches_source_offsets(md_dir, stem):
    text = _read(md_dir, stem)
    hits = extract_all(text)
    assert hits, f"{stem}: không trích được gì"
    for hit in hits:
        assert hit.quote.strip(), f"{stem}: quote rỗng"
        assert text[hit.char_start : hit.char_end] == hit.quote, (
            f"{stem}: offset không khớp nguyên văn cho {hit.extractor}"
        )
        assert hit.section_path


@pytest.mark.parametrize("stem", DOCS)
def test_expected_counts_per_document(md_dir, stem):
    hits = extract_all(_read(md_dir, stem))
    counter = Counter((hit.kind, hit.fact_kind) for hit in hits)
    wr, step, env, ci, standard, term = EXPECTED_COUNTS[stem]
    assert counter[("fact", "working_range")] == wr
    assert counter[("fact", "inspection_step")] == step
    assert counter[("fact", "env_condition")] == env
    assert counter[("fact", "calibration_interval")] == ci
    assert counter[("standard", None)] == standard
    assert counter[("term", None)] == term


def test_working_range_values(md_dir):
    hits = [h for h in phamvi.extract(_read(md_dir, "QTKD_1.061_2021_ND_V2"))]
    assert len(hits) == 1
    assert hits[0].value_text == "đến 1 400 bar"
    assert hits[0].value_min is None
    assert hits[0].value_max == 1400.0
    assert hits[0].unit == "bar"


def test_mixed_unit_range_keeps_both_units(md_dir):
    hits = phamvi.extract(_read(md_dir, "2023._QTKD_1.190_2023_DPI_610_ND_24.01.24"))
    assert len(hits) == 1
    assert hits[0].value_text == "từ -700 mbar đến 700 bar"
    assert hits[0].value_min == -700.0
    assert hits[0].value_max == 700.0
    assert hits[0].unit_min == "mbar"
    assert hits[0].unit_max == "bar"


def test_parenthesised_ranges_1_159(md_dir):
    hits = phamvi.extract(_read(md_dir, "QTKD_1.159_2021_ND_FINAL"))
    values = {(h.value_min, h.value_max) for h in hits}
    assert (0.0015, 7.0) in values
    assert (-0.1, 100.0) in values
    assert (-0.1, 500.0) in values


def test_terms_1_061(md_dir):
    hits = thuatngu.extract(_read(md_dir, "QTKD_1.061_2021_ND_V2"))
    terms = {h.term_vi: h.term_en for h in hits}
    assert terms["Van an toàn"] == "Safety valve"
    assert terms["Độ chênh áp"] == "blowdown"
    assert len(hits) == 6


def test_bang2_combines_split_tables_1_071(md_dir):
    hits = bang2.extract(_read(md_dir, "QTKD_1.071_2022_FINAL"))
    assert [h.ord for h in hits] == list(range(1, 8))
    assert hits[-1].name_vi == "Thiết bị đo tốc độ vòng quay không tiếp xúc"


def test_bang1_reads_two_level_modes(md_dir):
    hits = bang1.extract(_read(md_dir, "QTKD_1.063_2021_BPL"))
    steps = {h.label: h for h in hits}
    assert "Sau sửa chữa" in steps["Kiểm tra kỹ thuật"].condition_text
    # Dòng "Kiểm tra kỹ thuật" của 1.063 chỉ bật Ban đầu + Sau sửa chữa.
    assert "Định kỳ" not in steps["Kiểm tra kỹ thuật"].condition_text


def test_dieukien_single_sided_and_tolerance(md_dir):
    hits = dieukien.extract(_read(md_dir, "QTKD_1.062_2021_ND"))
    by_label = {h.label: h for h in hits}
    assert by_label["Nhiệt độ môi trường"].rel_op == "±"
    assert by_label["Độ ẩm tương đối"].rel_op == "<="
    assert by_label["Độ ẩm tương đối"].value_max == 80.0
    assert by_label["Áp suất khí quyển"].value_text == "(1000 ± 40) mbar"


def test_chuky_value_text(md_dir):
    hits = chuky.extract(_read(md_dir, "QTKD_1.159_2021_ND_FINAL"))
    assert len(hits) == 1
    assert hits[0].value_text == "02 năm"


def test_rules_return_empty_on_non_dlvn_text():
    text = "# Lời nói đầu\n\nĐây không phải quy trình kiểm định."
    assert extract_all(text) == []
    for module in (phamvi, thuatngu, bang1, bang2, dieukien, chuky):
        assert module.extract(text) == []


def test_thuatngu_empty_when_section_is_not_terms(md_dir):
    # 1.159 §2 là "Tài liệu viện dẫn", không phải Thuật ngữ → không được đoán.
    assert thuatngu.extract(_read(md_dir, "QTKD_1.159_2021_ND_FINAL")) == []
