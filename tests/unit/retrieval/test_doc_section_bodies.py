"""Nội dung nguyên văn của mục cấu trúc - retrieval.doc_sections."""

from retrieval import doc_sections

DOC = """QTKĐ 1.061 : 2021
VAN AN TOÀN
QUY TRÌNH KIỂM ĐỊNH
Cơ quan biên soạn: Phòng Đo lường Nhiệt - Áp suất/Trung tâm Đo lường.

Cơ quan đề nghị ban hành: Trung tâm Đo lường.

Cơ quan xét duyệt, ban hành: Cục Tiêu chuẩn-Đo lường-Chất lượng/Bộ Quốc phòng.
Mục lục
# 1 Phạm vi áp dụng
Quy trình này áp dụng cho van an toàn.
# 2 Thuật ngữ và định nghĩa
Các thuật ngữ, định nghĩa trong quy trình này được hiểu như sau:
Áp suất chỉnh đặt (set pressure): là áp suất tại đó van bắt đầu mở ra.
CHÚ THÍCH: Đây là áp suất theo áp kế.
Độ chênh áp (blowdown): là độ chênh lệch giữa áp suất chỉnh đặt và áp suất đóng.
# 3 Phương tiện kiểm định
Bảng 2 - Danh mục phương tiện kiểm định
| 1 | Áp kế chuẩn | (0 đến 1 400) bar | ± 0,1 % |
# 4 Điều kiện và chuẩn bị kiểm định
## 4.1 Điều kiện kiểm định
- Nhiệt độ môi trường: (23 ± 5) oC;
## 4.2 Chuẩn bị kiểm định
- Để van trong phòng ít nhất 2 h.
# 5 Xử lý chung
- Chu kỳ kiểm định của Van an toàn là 12 tháng.
# Phụ lục A
Mẫu biên bản
"""


def test_section_body_includes_subsections_and_stops_at_next_section():
    section = doc_sections.find_section(DOC, r"^dieu kien")
    assert section.label == "4 Điều kiện và chuẩn bị kiểm định"
    assert section.text == (
        "**4.1 Điều kiện kiểm định**\n- Nhiệt độ môi trường: (23 ± 5) oC;\n"
        "**4.2 Chuẩn bị kiểm định**\n- Để van trong phòng ít nhất 2 h."
    )


def test_equipment_section_keeps_its_table_and_appendix_ends_the_last_section():
    assert "| 1 | Áp kế chuẩn |" in doc_sections.find_section(DOC, r"^phuong tien kiem dinh").text
    assert "Mẫu biên bản" not in doc_sections.find_section(DOC, r"^xu ly chung").text


def test_cycle_lines_are_verbatim_without_list_marks():
    assert doc_sections.cycle_lines(DOC) == ["Chu kỳ kiểm định của Van an toàn là 12 tháng."]


def test_agency_block_and_outline_field_with_value_on_next_line():
    assert [line.split(":")[0] for line in doc_sections.agency_lines(DOC)] == [
        "Cơ quan biên soạn",
        "Cơ quan đề nghị ban hành",
        "Cơ quan xét duyệt, ban hành",
    ]
    outline = "3. Cơ quan chủ trì: Trung tâm Đo lường\n# 4. Chủ nhiệm biên soạn quy trình:\nĐại úy A\n# 5. Khác\n"
    assert doc_sections.agency_lines(outline) == [
        "3. Cơ quan chủ trì: Trung tâm Đo lường",
        "4. Chủ nhiệm biên soạn quy trình: Đại úy A",
    ]


def test_definitions_attach_notes_and_support_numbered_terms():
    terms = doc_sections.definitions(DOC)
    assert [t.term for t in terms] == ["Áp suất chỉnh đặt (set pressure)", "Độ chênh áp (blowdown)"]
    assert terms[0].text.endswith("CHÚ THÍCH: Đây là áp suất theo áp kế.")
    numbered = "# 3 Thuật ngữ và định nghĩa\n3.1 Tính khách quan\n\nSự thể hiện của tính vô tư.\n# 4 Khác\n"
    assert [(t.term, t.text) for t in doc_sections.definitions(numbered)] == [
        ("Tính khách quan", "3.1 Tính khách quan\nSự thể hiện của tính vô tư.")
    ]
