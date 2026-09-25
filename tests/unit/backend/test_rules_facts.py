"""Test đơn vị cho các luật trích xuất dữ kiện QTKĐ (``knowledge.rules``).

Mỗi test ở đây khoá một hành vi biên đã sửa (mã K) bằng một đoạn Markdown nhỏ,
tách khỏi corpus tổng hợp để khi hồi quy chỉ rõ luật nào vỡ.
"""

from __future__ import annotations

from knowledge.rules.chuky import extract as extract_chuky
from knowledge.rules.dieukien import extract as extract_dieukien
from knowledge.rules.phamvi import extract as extract_phamvi
from knowledge.rules.phuluc_a import extract as extract_appendix


def test_phamvi_k15_sentence_period_not_part_of_unit():
    """K15: dấu chấm câu cuối câu không thuộc đơn vị lẫn ``value_text``."""
    md = (
        "# 1 Phạm vi áp dụng\n"
        "Phạm vi làm việc của van an toàn kiểm định theo quy trình này "
        "từ 0 bar đến 1 400 bar.\n"
    )
    hits = extract_phamvi(md)
    assert len(hits) == 1
    hit = hits[0]
    assert hit.value_text == "từ 0 bar đến 1 400 bar"
    assert hit.unit == "bar"
    assert hit.unit_min == "bar"
    assert hit.unit_max == "bar"
    assert not hit.quote.endswith(".")


def test_phamvi_k15_internal_unit_token_kept():
    """K15 không được cắt nhầm ký tự bên trong đơn vị (ví dụ ``m3/h``)."""
    md = "# 1 Phạm vi áp dụng\nPhạm vi đo từ 0 m3/h đến 16 m3/h, áp dụng cho kiểm định.\n"
    hits = extract_phamvi(md)
    assert len(hits) == 1
    assert hits[0].value_text == "từ 0 m3/h đến 16 m3/h"
    assert hits[0].unit_max == "m3/h"


def test_chuky_k10_colon_without_la():
    """K10: "Chu kỳ kiểm định: 6 tháng" (dấu hai chấm thay cho "là")."""
    md = "# 8 Xử lý chung\nChu kỳ kiểm định: 6 tháng.\n"
    hits = extract_chuky(md)
    assert [hit.value_text for hit in hits] == ["6 tháng"]


def test_chuky_k10_la_still_works():
    """K10 không được làm hỏng dạng cũ "... là 12 tháng"."""
    md = "# 8 Xử lý chung\nChu kỳ kiểm định của van an toàn là 12 tháng.\n"
    hits = extract_chuky(md)
    assert [hit.value_text for hit in hits] == ["12 tháng"]


def test_dieukien_k02_decimal_comma_not_split():
    """K02: dấu phẩy thập phân trong "(20,5 ± 2) °C" không phải ranh giới tách."""
    md = (
        "# 5.1 Điều kiện kiểm định\n"
        "- Nhiệt độ môi trường: (20,5 ± 2) °C, không thay đổi quá 1 °C;\n"
    )
    hits = extract_dieukien(md)
    assert len(hits) == 1
    assert hits[0].value_text == "(20,5 ± 2) °C"
    assert hits[0].condition_text == "không thay đổi quá 1 °C"


def test_dieukien_k02_condition_comma_still_splits():
    """K02 không được làm hỏng việc tách điều kiện ở dấu phẩy thật."""
    md = "# 5.1 Điều kiện kiểm định\n- Nhiệt độ môi trường: (20 ± 5) °C, không thay đổi quá 1 °C;\n"
    hits = extract_dieukien(md)
    assert len(hits) == 1
    assert hits[0].value_text == "(20 ± 5) °C"
    assert hits[0].condition_text == "không thay đổi quá 1 °C"


def test_phuluc_a_k12_inner_heading_does_not_cut_section():
    """K12: heading con "(Quy định)" bên trong Phụ lục A không kết thúc mục."""
    md = "# Phụ lục A\n## (Quy định)\nMẪU BIÊN BẢN KIỂM ĐỊNH\nSố hiệu:\nNgày kiểm định:\n"
    labels = [hit.label for hit in extract_appendix(md)]
    assert "Số hiệu" in labels
    assert "Ngày kiểm định" in labels


def test_phuluc_a_k12_stops_at_next_phu_luc():
    """K12: thân mục dừng ở heading "Phụ lục" kế tiếp, không nuốt Phụ lục B."""
    md = "# Phụ lục A\nSố hiệu:\n# Phụ lục B\nSố hiệu B:\n"
    labels = [hit.label for hit in extract_appendix(md)]
    assert labels == ["Số hiệu"]


def test_phuluc_a_k12_stops_at_plain_paragraph_phu_luc():
    """K12: "Phụ lục B" là ĐOẠN VĂN THƯỜNG (không #) vẫn là điểm dừng."""
    md = (
        "# Phụ lục A\n"
        "Số hiệu:\n"
        "Phụ lục A (tiếp theo)\n"
        "Phụ lục B\n"
        "Số hiệu B:\n"
        "PHỤ LỤC C\n"
        "Số hiệu C:\n"
    )
    labels = [hit.label for hit in extract_appendix(md)]
    assert labels == ["Số hiệu"]


def test_phuluc_a_k12_plain_stop_matches_phu_luc_b_with_suffix_text():
    """K12: "Phụ lục B (tiếp theo)" trên dòng riêng cũng là điểm dừng."""
    md = "# Phụ lục A\nSố hiệu:\nPhụ lục B (tiếp theo)\nSố hiệu B:\n"
    labels = [hit.label for hit in extract_appendix(md)]
    assert labels == ["Số hiệu"]


def test_phuluc_a_k12_midline_phu_luc_mention_not_stop():
    """K12: câu văn nhắc "Phụ lục B" giữa dòng không phải điểm dừng."""
    md = "# Phụ lục A\nSố hiệu:\nGhi kết quả vào Bảng A.2 của Phụ lục B;\nNgày kiểm định:\n"
    labels = [hit.label for hit in extract_appendix(md)]
    assert labels == ["Số hiệu", "Ngày kiểm định"]


def test_phuluc_a_k12_phu_luc_a_continuation_not_stop():
    """K12: "Phụ lục A (tiếp theo)" / "(kết thúc)" không phải điểm dừng."""
    md = (
        "# Phụ lục A\n"
        "Số hiệu:\n"
        "Phụ lục A (tiếp theo)\n"
        "Ngày kiểm định:\n"
        "Phụ lục A (kết thúc)\n"
        "Người kiểm định:\n"
    )
    labels = [hit.label for hit in extract_appendix(md)]
    assert labels == ["Số hiệu", "Ngày kiểm định", "Người kiểm định"]


def test_phuluc_a_k12_heading_continuation_not_stop():
    """K12: heading "Phụ lục A (tiếp theo)/(kết thúc)" KHÔNG phải điểm dừng."""
    md = (
        "# Phụ lục A\n"
        "Số hiệu:\n"
        "# Phụ lục A (tiếp theo)\n"
        "Ngày kiểm định:\n"
        "# Phụ lục A (kết thúc)\n"
        "Người kiểm định:\n"
    )
    labels = [hit.label for hit in extract_appendix(md)]
    assert labels == ["Số hiệu", "Ngày kiểm định", "Người kiểm định"]


def test_phuluc_a_k12_plain_line_phu_luc_nay_not_stop():
    """K12: "Phụ lục này áp dụng cho mẫu." không phải điểm dừng (nhãn phải là
    MỘT chữ cái đứng riêng, không phải chữ cái đầu của một từ)."""
    md = "# Phụ lục A\nSố hiệu:\nPhụ lục này áp dụng cho mẫu.\nNgày kiểm định:\n"
    labels = [hit.label for hit in extract_appendix(md)]
    assert labels == ["Số hiệu", "Ngày kiểm định"]


def test_phuluc_a_k12_plain_line_phu_luc_bang_not_stop():
    """K12: "Phụ lục Bảng ..." không phải điểm dừng (B là đầu từ "Bảng")."""
    md = "# Phụ lục A\nSố hiệu:\nPhụ lục Bảng A.2 liệt kê kết quả.\nNgày kiểm định:\n"
    labels = [hit.label for hit in extract_appendix(md)]
    assert labels == ["Số hiệu", "Ngày kiểm định"]


def test_phuluc_a_k12_071_layout_excludes_appendix_b_and_c():
    """K12: mô phỏng bố cục 1.071 (Phụ lục B/C là đoạn văn thường): chỉ trích
    Phụ lục A, không lặp nhãn header và không lọt bảng "Bảng B."/"Bảng C."."""
    md = (
        "# Phụ lục A\n"
        "Số hiệu:\n"
        "Phụ lục A (tiếp theo)\n"
        "Bảng A.1 - Kết quả đo\n"
        "| Giá trị đo | Sai số |\n"
        "| --- | --- |\n"
        "| 1 | 2 |\n"
        "Phụ lục B\n"
        "# (Quy định)\n"
        "Mẫu biên bản kiểm định (không đạt cấp cho đơn vị)\n"
        "Số hiệu: B\n"
        "Bảng B.1 - Kết quả đo\n"
        "| Giá trị đo | Sai số |\n"
        "| --- | --- |\n"
        "| 3 | 4 |\n"
        "Phụ lục C\n"
        "Bảng C.1 - Kết quả đo\n"
        "| Giá trị đo | Sai số |\n"
        "| --- | --- |\n"
        "| 5 | 6 |\n"
    )
    hits = extract_appendix(md)
    labels = [hit.label for hit in hits]
    assert labels.count("Số hiệu") == 1, "nhãn header bị lặp do chồng Phụ lục A/B"
    titles = [hit.label for hit in hits if hit.condition_text == "table"]
    assert titles == ["Bảng A.1 - Kết quả đo"]
    assert all(not title.startswith(("Bảng B.", "Bảng C.")) for title in titles)


def test_phuluc_a_k06_label_without_colon():
    """K06: dòng nhãn hồ sơ không có ':' vẫn là trường header; chữ mẫu bị bỏ."""
    md = "# Phụ lục A\nNgày kiểm định tháng năm 2026\nSố giấy chứng nhận\n"
    hits = {hit.label: hit for hit in extract_appendix(md)}
    assert "Ngày kiểm định" in hits
    assert hits["Ngày kiểm định"].condition_text == "header"
    assert hits["Ngày kiểm định"].value_text == "2026"
    assert "Số hiệu" not in hits
    assert "Số giấy chứng nhận" in hits
    assert hits["Số giấy chứng nhận"].value_text is None


def test_phuluc_a_k06_template_year_ellipsis_is_empty():
    """K06: dòng mẫu "Ngày kiểm định … tháng … năm 202…" chỉ còn chữ mẫu và mẩu
    năm dính dấu chấm lửng nên ``value_text`` rỗng, không phải "202"."""
    md = "# Phụ lục A\nNgày kiểm định … tháng … năm 202…\n"
    hits = {hit.label: hit for hit in extract_appendix(md)}
    assert "Ngày kiểm định" in hits
    assert hits["Ngày kiểm định"].value_text is None


def test_phuluc_a_k06_template_dots_variants_empty():
    """K06: biến thể "..." và ".." dính số cũng để giá trị rỗng (nguyên văn dòng
    thật của 1.061/1.062/1.063 là "Ngày kiểm định tháng năm 202…")."""
    for line in (
        "Ngày kiểm định tháng năm 202…",
        "Ngày kiểm định ... tháng ... năm 20..",
    ):
        md = f"# Phụ lục A\n{line}\n"
        hits = {hit.label: hit for hit in extract_appendix(md)}
        assert hits["Ngày kiểm định"].value_text is None, line
