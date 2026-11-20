"""Parent-document chunking — ingestion.chunker.parse_file + _make_id.

PARENT = mỗi heading section; CHILD = paragraph/table/formula trong section.
chunk_id idempotent (sha256[:16] → uint64 point id của Qdrant).
"""

from ingestion.chunker import _make_id, parse_file


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


EQUIPMENT_MD = """TÀI LIỆU KỸ THUẬT VÀ HƯỚNG DẪN VẬN HÀNH CHUẨN ĐO LƯỜNG

THIẾT BỊ: ÁP KẾ PÍTTÔNG CHUẨN МП-600 (SỐ HIỆU: 994)

| Ký hiệu / Model: | МП-600 (MP-600) |
| --- | --- |

1. TỔNG QUAN

1.1. Vai trò và phạm vi ứng dụng: Áp kế píttông chuẩn МП-600 dùng để kiểm định áp kế lò xo.

2. ĐẶC TÍNH ĐO LƯỜNG

2.1. Điều kiện vận hành tham chiếu và các yếu tố hiệu chính:

Nhiệt độ phòng (20 ± 2) °C.

3. HƯỚNG DẪN SỬ DỤNG NHANH

Bước 1: Chuẩn bị thiết bị.
"""


def _parents(tmp_path, name, text):
    path = tmp_path / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return [c for c in parse_file(path) if c.is_parent]


def test_numbered_lines_become_sections_when_markdown_has_no_headings(tmp_path):
    # Tài liệu thiết bị chuẩn mẫu (A_*) không có tiêu đề "#": mục "1. TỔNG QUAN"... phải thành mục thật,
    # không bị cắt máy móc thành "(phần N)". Phần đầu (tên, bảng kiểu/số hiệu) giữ trong mục riêng.
    paths = [c.section_path for c in _parents(tmp_path, "A_06", EQUIPMENT_MD)]
    assert paths == [
        "Thông tin chung",
        "1. TỔNG QUAN",
        "2. ĐẶC TÍNH ĐO LƯỜNG",  # "2.1. ... hiệu chính:" kết thúc bằng ":" nên ở trong mục 2
        "3. HƯỚNG DẪN SỬ DỤNG NHANH",
    ]
    first = _parents(tmp_path, "A_06", EQUIPMENT_MD)[0]
    assert "MP-600" in first.text and "THIẾT BỊ" in first.text


def test_table_of_contents_is_skipped_and_body_numbering_is_used(tmp_path):
    md = """TIÊU CHUẨN QUỐC GIA

1 Phạm vi áp dụng

2 Thuật ngữ

2.1 Tính khách quan

Lời nói đầu

Nội dung lời nói đầu.

1 Phạm vi áp dụng

Tiêu chuẩn này quy định yêu cầu chung.

2 Thuật ngữ

2.1 Tính khách quan

2.1.1 Hoạt động thí nghiệm phải được thực hiện một cách khách quan và được cơ cấu, quản lý để bảo vệ tính khách quan.

2.2 Bảo mật
"""
    paths = [c.section_path for c in _parents(tmp_path, "TCVN", md)]
    assert paths == [
        "Thông tin chung",
        "1 Phạm vi áp dụng",
        "2 Thuật ngữ",
        "2 Thuật ngữ > 2.1 Tính khách quan",
        "2 Thuật ngữ > 2.2 Bảo mật",
    ]


def test_text_without_numbered_sections_still_gets_synthetic_windows(tmp_path):
    paths = [
        c.section_path for c in _parents(tmp_path, "pdf", "chỉ có văn bản trơn không đánh số mục")
    ]
    assert paths == ["pdf (phần 1)"]


def test_clause_lines_are_not_headings_but_short_dotted_titles_and_appendices_are(tmp_path):
    md = """1 Phạm vi áp dụng

Nội dung.

2 Yêu cầu

2.1 Phòng thí nghiệm phải:

a) có nhân sự.

2.2 Đánh giá độ không đảm bảo đo.

2.2.1 Phòng thí nghiệm phải nhận biết các thành phần độ không đảm bảo đo.

Phụ lục A

Thông tin bổ sung.
"""
    paths = [c.section_path for c in _parents(tmp_path, "TCVN", md)]
    assert paths == [
        "1 Phạm vi áp dụng",
        "2 Yêu cầu",
        "2 Yêu cầu > 2.2 Đánh giá độ không đảm bảo đo.",
        "Phụ lục A",
    ]


def test_oversized_promoted_section_is_split_on_line_boundaries(tmp_path, settings_override):
    settings_override({"chunking.synth_section_chars": 100})
    rows = "\n".join(f"| 1.{i} Thuật ngữ số {i} | Định nghĩa {i} |" for i in range(1, 40))
    md = f"1. Phạm vi áp dụng\n\nNội dung.\n\n2. Thuật ngữ\n\n{rows}\n"
    parents = _parents(tmp_path, "TCVN", md)
    paths = [c.section_path for c in parents]
    assert paths[0] == "1. Phạm vi áp dụng"
    assert paths[1:3] == ["2. Thuật ngữ (phần 1)", "2. Thuật ngữ (phần 2)"]
    body = "\n".join(c.text for c in parents[1:])
    assert all(f"| 1.{i} Thuật ngữ số {i} |" in body for i in range(1, 40))  # không cắt giữa dòng
