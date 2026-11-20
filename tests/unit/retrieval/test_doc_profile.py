"""Hồ sơ tài liệu - retrieval.doc_profile: mã, tên, phạm vi nguyên văn, mục lục, từ khoá kiểu."""

from retrieval.doc_profile import build_profile, normalize_keyword

NEW_QTKD = """QTKĐ QUY TRÌNH KIỂM ĐỊNH
QTKĐ 1.197 : 2024
LÒ NHIỆT ĐỘ CHUẨN KIỂU TCH-1200
QUY TRÌNH KIỂM ĐỊNH
(Ban hành kèm theo Quyết định số /QĐ-TĐC ngày tháng năm 2024
Mục lục
1 Phạm vi áp dụng 5
2 Các phép kiểm định 5
# 1 Phạm vi áp dụng

Quy trình này quy định quy trình kiểm định ban đầu, kiểm định định kỳ lò nhiệt độ chuẩn kiểu TCH-1200.

# 2 Các phép kiểm định
Bảng 1
# 4 Điều kiện và chuẩn bị kiểm định
## 4.1 Điều kiện kiểm định
### 4.1.1 Chi tiết
# Phụ lục A
# (Quy định)
"""

OLD_QTKD = """Mục lục
Lời nói đầu
Cơ quan xét duyệt, ban hành: Cục Tiêu chuẩn-Đo lường-Chất lượng/Bộ Quốc phòng.
Cột đo xăng dầu có lưu lượng đo đến 200 L/min,
Cấp chính xác đến 0,5
Quy trình kiểm định
# 1 Phạm vi áp dụng
Quy trình này dùng để kiểm định ban đầu và định kỳ các loại cột đo xăng dầu.
# 2 Thuật ngữ và định nghĩa
"""

TCVN = """TIÊU CHUẨN QUỐC GIA
TCVN ISO/IEC 17025:2017
ISO/IEC 17025:2017
YÊU CẦU CHUNG VỀ NĂNG LỰC CỦA CÁC PHÒNG THỬ NGHIỆM VÀ HIỆU CHUẨN
Mục lục
1 Phạm vi áp dụng
2 Tài liệu viện dẫn
3 Thuật ngữ và định nghĩa
Lời nói đầu
1 Phạm vi áp dụng
Tiêu chuẩn này quy định các yêu cầu chung về năng lực của phòng thí nghiệm.
Tiêu chuẩn này áp dụng cho mọi tổ chức thực hiện hoạt động thí nghiệm.
2 Tài liệu viện dẫn
"""

OUTLINE = """ĐỀ CƯƠNG XÂY DỰNG QUY TRÌNH
1. Tên quy trình: Thiết bị đo tốc độ vòng quay chỉ thị tương tự kiểu ИO-30 - Quy trình kiểm định.
2. Phạm vi sử dụng: Trong nội bộ Cục Tiêu chuẩn-Đo lường-Chất lượng/Bộ tổng Tham mưu.
Số hiệu đăng ký: QTKĐ 1.072 : 2022
3. Cơ quan chủ trì: Trung tâm Đo lường
"""


def test_new_format_qtkd_profile():
    p = build_profile("QTKĐ_1.197_2024_2", NEW_QTKD, 1500)
    assert p.label == "QTKĐ 1.197:2024"
    assert p.title == "LÒ NHIỆT ĐỘ CHUẨN KIỂU TCH-1200"
    assert p.scope_heading == "1 Phạm vi áp dụng"
    assert p.scope_text.startswith("Quy trình này quy định") and p.scope_text.endswith("TCH-1200.")
    labels = [s.label for s in p.sections]
    # Mục cấp 3 bị bỏ; dòng "(Quy định)" gộp vào phụ lục đứng trước.
    assert labels == [
        "1 Phạm vi áp dụng",
        "2 Các phép kiểm định",
        "4 Điều kiện và chuẩn bị kiểm định",
        "4.1 Điều kiện kiểm định",
        "Phụ lục A (Quy định)",
    ]
    assert p.keywords == ("tch1200",)


def test_old_format_takes_code_from_file_name_and_title_before_quy_trinh():
    p = build_profile("QTKĐ_1.062_2016_2", OLD_QTKD, 1500)
    assert p.label == "QTKĐ 1.062:2016"
    assert p.title == "Cột đo xăng dầu có lưu lượng đo đến 200 L/min, Cấp chính xác đến 0,5"
    assert p.scope_text == "Quy trình này dùng để kiểm định ban đầu và định kỳ các loại cột đo xăng dầu."


def test_tcvn_scope_skips_table_of_contents_entry():
    p = build_profile("TCVN_ISO_IEC17025_2017_2", TCVN, 1500)
    assert p.label == "TCVN ISO/IEC 17025:2017"
    assert p.title == "YÊU CẦU CHUNG VỀ NĂNG LỰC CỦA CÁC PHÒNG THỬ NGHIỆM VÀ HIỆU CHUẨN"
    assert p.scope_text.splitlines() == [
        "Tiêu chuẩn này quy định các yêu cầu chung về năng lực của phòng thí nghiệm.",
        "Tiêu chuẩn này áp dụng cho mọi tổ chức thực hiện hoạt động thí nghiệm.",
    ]
    assert [s.label for s in p.sections] == [
        "1 Phạm vi áp dụng",
        "2 Tài liệu viện dẫn",
        "3 Thuật ngữ và định nghĩa",
    ]


def test_outline_document_uses_inline_fields():
    p = build_profile("QTKĐ_1.072_2022_2", OUTLINE, 1500)
    assert p.label == "QTKĐ 1.072:2022"
    assert p.title == "Thiết bị đo tốc độ vòng quay chỉ thị tương tự kiểu ИO-30"
    assert p.scope_heading == "2 Phạm vi sử dụng"
    assert p.scope_text == "Trong nội bộ Cục Tiêu chuẩn-Đo lường-Chất lượng/Bộ tổng Tham mưu."
    assert p.keywords == ("io30",)


def test_scope_is_capped_at_a_word_boundary():
    text = "# 1 Phạm vi áp dụng\n" + " ".join(["từ"] * 200) + "\n# 2 Khác\n"
    p = build_profile("x", text, 50)
    assert len(p.scope_text) <= 52 and p.scope_text.endswith(" …")


def test_appendix_title_comes_from_the_lines_after_its_heading_and_duplicates_are_dropped():
    text = (
        "# 1 Phạm vi áp dụng\nNội dung.\n"
        "# Phụ lục A\n\n(Quy định)\n\nMẫu Biên bản kiểm định\n| a | b |\n"
        "# Phụ lục C\n(Quy định)\nMẫu Giấy chứng nhận kiểm định\n"
        "# Phụ lục C (kết thúc)\nC.2 Mặt sau\n"
    )
    labels = [s.label for s in build_profile("x", text, 1500).sections]
    assert labels == [
        "1 Phạm vi áp dụng",
        "Phụ lục A (Quy định) Mẫu Biên bản kiểm định",
        "Phụ lục C (Quy định) Mẫu Giấy chứng nhận kiểm định",
    ]


def test_keyword_normalization_matches_latin_typing_of_cyrillic_model():
    assert normalize_keyword("ТН-12") == normalize_keyword("TH-12") == "th12"
    assert normalize_keyword("DPI 610") == "dpi610"


def test_subject_is_the_device_name_before_qualifiers():
    from retrieval.doc_profile import parse_subject

    assert parse_subject("VAN AN TOÀN CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar") == "van an toan"
    assert parse_subject("LƯU LƯỢNG KẾ CHẤT LỎNG") == "luu luong ke chat long"
    # "dung tích" không phải "dùng", "động cơ" không phải "có": cắt trên chữ còn dấu.
    assert parse_subject("Phương tiện đo dung tích thí nghiệm bằng thủy tinh Cấp chính xác B") == (
        "phuong tien do dung tich thi nghiem bang thuy tinh"
    )
    assert parse_subject("THIẾT BỊ ĐO TIÊU HAO NHIÊN LIỆU ĐỘNG CƠ KIỂU FC9531") == "thiet bi do tieu hao nhien lieu dong co"
    assert parse_subject("Takhomet") == ""  # một từ: quá mơ hồ để ghim tài liệu
