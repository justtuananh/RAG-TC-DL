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


def _catalog_md(tmp_path, n_rows: int):
    """Danh mục kiểu Biểu 4: một bảng dài có đề mục nhóm số La Mã."""
    lines = [
        "# Danh mục",
        "",
        "| TT | Số hiệu | Tên |",
        "|---|---|---|",
        "| I | Lĩnh vực áp suất |  |",
    ]
    for i in range(1, n_rows + 1):
        if i == 11:
            lines.append("| II | Lĩnh vực nhiệt độ |  |")
        lines.append(f"| {i} | QTKĐ 1.{i:03d} : 2021 | Quy trình số {i} |")
    path = tmp_path / "danh_muc.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [c for c in parse_file(path) if not c.is_parent and c.kind == "table"]


def test_short_table_stays_one_chunk(tmp_path):
    assert len(_catalog_md(tmp_path, 12)) == 1


def test_long_table_split_into_row_groups_with_header(tmp_path):
    tables = _catalog_md(tmp_path, 30)
    assert len(tables) > 1
    for chunk in tables:
        rows = chunk.text.split("\n")
        assert rows[0] == "| TT | Số hiệu | Tên |" and rows[1] == "|---|---|---|"
    # Mọi dòng dữ liệu có mặt đúng một lần (không mất, không lặp).
    data = [row for chunk in tables for row in chunk.text.split("\n")[2:] if "QTKĐ" in row]
    assert len(data) == 30 and len(set(data)) == 30


def test_row_group_carries_nearest_group_heading(tmp_path):
    tables = _catalog_md(tmp_path, 30)
    holder = next(c for c in tables if "QTKĐ 1.020 : 2021" in c.text)
    # Dòng 20 thuộc nhóm II: chunk chứa nó phải mang đề mục "II" làm ngữ cảnh.
    assert "| II | Lĩnh vực nhiệt độ |  |" in holder.text
    assert "| I | Lĩnh vực áp suất |  |" not in holder.text
    assert len({c.chunk_id for c in tables}) == len(tables)
