"""Parent-document chunking — index.chunker.parse_file + _make_id.

PARENT = mỗi heading section; CHILD = paragraph/table/formula trong section.
chunk_id idempotent (sha256[:16] → uint64 point id của Qdrant).
"""

from index.chunker import _make_id, parse_file


def test_parents_and_children_counts(data_dir):
    chunks = parse_file(data_dir / "sample_section.md")
    assert sum(c.is_parent for c in chunks) == 2
    assert sum(not c.is_parent for c in chunks) == 3


def test_child_kinds(data_dir):
    chunks = parse_file(data_dir / "sample_section.md")
    kinds = sorted(c.kind for c in chunks if not c.is_parent)
    assert kinds == ["formula", "paragraph", "table"]


def test_section_path_nesting(data_dir):
    paths = {c.section_path for c in parse_file(data_dir / "sample_section.md")}
    assert "3 Phép kiểm định" in paths
    assert "3 Phép kiểm định > 3.1 Phép đo cơ bản" in paths


def test_children_carry_parent_id(data_dir):
    chunks = parse_file(data_dir / "sample_section.md")
    parent_id_by_path = {c.section_path: c.chunk_id for c in chunks if c.is_parent}
    for c in chunks:
        if not c.is_parent:
            assert c.parent_id == parent_id_by_path[c.section_path]


def test_formula_only_line_detected(data_dir):
    chunks = parse_file(data_dir / "sample_section.md")
    formulas = [c for c in chunks if c.kind == "formula"]
    assert len(formulas) == 1
    assert formulas[0].text == r"$\Delta P = P_1 - P_2$"


def test_idempotent_ids(data_dir):
    a = parse_file(data_dir / "sample_section.md")
    b = parse_file(data_dir / "sample_section.md")
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]


def test_make_id_is_16_hex_and_fits_uint64():
    cid = _make_id("file", "sec", "text")
    assert len(cid) == 16
    assert all(ch in "0123456789abcdef" for ch in cid)
    assert int(cid, 16) < 2**64


def test_make_id_distinct_and_stable():
    assert _make_id("f", "s", "t1") != _make_id("f", "s", "t2")
    assert _make_id("f", "s", "t") == _make_id("f", "s", "t")
