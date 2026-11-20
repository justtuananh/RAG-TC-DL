"""Trả lời nguyên văn theo mục cấu trúc - query.doc_sections."""

import pytest

from query import doc_sections

VAN = """QTKĐ 1.061 : 2021
VAN AN TOÀN CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar
QUY TRÌNH KIỂM ĐỊNH
Cơ quan biên soạn: Phòng Đo lường Nhiệt - Áp suất.
# 1 Phạm vi áp dụng
Quy trình này áp dụng cho van an toàn.
# 2 Thuật ngữ và định nghĩa
Áp suất chỉnh đặt (set pressure): là áp suất tại đó van bắt đầu mở ra.
# 3 Phương tiện kiểm định
| 1 | Áp kế chuẩn | (0 đến 1 400) bar | ± 0,1 % |
# 4 Điều kiện và chuẩn bị kiểm định
## 4.1 Điều kiện kiểm định
- Nhiệt độ môi trường: (23 ± 5) oC;
## 4.2 Chuẩn bị kiểm định
- Để van trong phòng ít nhất 2 h.
# 5 Xử lý chung
- Chu kỳ kiểm định của Van an toàn là 12 tháng.
"""
LUU = """QTKĐ 1.213 : 2025
LƯU LƯỢNG KẾ CHẤT LỎNG
QUY TRÌNH KIỂM ĐỊNH
# 1 Phạm vi áp dụng
Quy trình này áp dụng cho lưu lượng kế chất lỏng.
# 6 Xử lý chung
- Chu kỳ kiểm định của Lưu lượng kế chất lỏng là 01 năm (12 tháng).
"""
CU = """QTKĐ 1.044 : 2015
Takhomet hiện số
QUY TRÌNH KIỂM ĐỊNH
# 1 Phạm vi áp dụng
Quy trình này dùng để kiểm định takhomet hiện số.
"""


@pytest.fixture
def docs(tmp_path, settings_override, monkeypatch):
    files = {"VAN": VAN, "LUU": LUU, "CU": CU}
    for stem, text in files.items():
        (tmp_path / f"{stem}.md").write_text(text, encoding="utf-8")
    settings_override({"paths.markdown_dir": str(tmp_path)})
    routes: dict[str, frozenset[str]] = {}
    monkeypatch.setattr(doc_sections.router, "route_files", lambda q: routes.get(q, frozenset()))
    monkeypatch.setattr(doc_sections.router, "known_files", lambda: frozenset(files))
    return routes


@pytest.mark.parametrize(
    "question,intents",
    [
        ("Phương tiện kiểm định áp kế pít tông theo QTKĐ 1.159 gồm những gì?", ["equipment"]),
        ("Nhiệt kế chuẩn dùng để kiểm định lò nhiệt độ TCH-1200 là gì?", ["equipment"]),
        ("Cần chuẩn bị gì trước khi kiểm định H3000?", ["conditions"]),
        ("Điều kiện kiểm định và chu kỳ kiểm định van an toàn?", ["conditions", "cycle"]),
        ("Cơ quan biên soạn QTKĐ 1.085 là ai?", ["agency"]),
        ("Lượng cấp phát tối thiểu là lượng đảm bảo một chu kỳ làm việc của buồng lường?", []),
        ("Cách tính sai số theo điều kiện kiểm định?", []),  # cần suy luận: để RAG
    ],
)
def test_classify(question, intents):
    assert doc_sections.classify(question) == intents


def test_equipment_and_conditions_quote_the_whole_section(docs):
    question = "Điều kiện kiểm định van an toàn là gì?"
    docs[question] = frozenset({"VAN"})
    answer = doc_sections.try_section_answer(question)
    assert answer.text.startswith("**QTKĐ 1.061:2021 - VAN AN TOÀN")
    assert "Theo mục 4 Điều kiện và chuẩn bị kiểm định [1]:" in answer.text
    assert "(23 ± 5) oC" in answer.text and "ít nhất 2 h" in answer.text
    assert answer.hits[0]["payload"]["section_path"] == "4 Điều kiện và chuẩn bị kiểm định"


def test_cycle_comparison_answers_each_document(docs):
    question = "So sánh chu kỳ kiểm định của van an toàn và lưu lượng kế chất lỏng"
    docs[question] = frozenset({"VAN", "LUU"})
    answer = doc_sections.try_section_answer(question)
    assert answer.text.startswith("Có 2 tài liệu khớp")
    assert "Chu kỳ kiểm định của Van an toàn là 12 tháng. [1]" in answer.text
    assert "là 01 năm (12 tháng). [2]" in answer.text


def test_missing_cycle_is_stated_but_no_data_at_all_falls_back(docs):
    question = "Chu kỳ kiểm định van an toàn và takhomet"
    docs[question] = frozenset({"VAN", "CU"})
    answer = doc_sections.try_section_answer(question)
    assert "Tài liệu không quy định chu kỳ kiểm định." in answer.text and len(answer.hits) == 1
    only_old = "Chu kỳ kiểm định takhomet"
    docs[only_old] = frozenset({"CU"})
    assert doc_sections.try_section_answer(only_old) is None


def test_structural_question_without_a_named_document_goes_to_rag(docs):
    assert doc_sections.try_section_answer("Chu kỳ kiểm định là bao lâu?") is None


def test_definition_found_in_named_or_any_document(docs):
    answer = doc_sections.try_section_answer("Áp suất chỉnh đặt là gì?")
    assert "> Áp suất chỉnh đặt (set pressure): là áp suất tại đó van bắt đầu mở ra." in answer.text
    assert (
        doc_sections.try_section_answer("Áp suất mở van là gì?") is None
    )  # không có mục từ: để RAG


def test_device_name_without_definition_quotes_the_scope(docs):
    answer = doc_sections.try_section_answer("Takhomet là gì?")
    assert answer.text.startswith("Các tài liệu không có mục định nghĩa riêng cho «takhomet»")
    assert "> Quy trình này dùng để kiểm định takhomet hiện số." in answer.text
    assert doc_sections.try_section_answer("Van là gì?") is None  # quá ngắn để khớp tên thiết bị


def test_comparison_facts_give_each_document_scope_and_cycle(docs):
    question = "Van an toàn và lưu lượng kế khác nhau chỗ nào?"
    docs[question] = frozenset({"VAN", "LUU"})
    facts = doc_sections.comparison_facts(question)
    assert facts.startswith("THÔNG TIN CHÍNH CỦA TỪNG TÀI LIỆU")
    assert (
        "### QTKĐ 1.061:2021" in facts
        and "Chu kỳ kiểm định: Chu kỳ kiểm định của Van an toàn là 12 tháng." in facts
    )
    assert "Điều kiện kiểm định (mục 4.1):\n- Nhiệt độ môi trường: (23 ± 5) oC;" in facts
    assert facts.index("1.061") < facts.index("1.213")
    one = "Van an toàn khác gì?"
    docs[one] = frozenset({"VAN"})
    assert doc_sections.comparison_facts(one) is None  # một tài liệu: không phải so sánh


def test_disabled_in_settings(docs, settings_override):
    settings_override({"doc_sections.enabled": False})
    assert doc_sections.try_section_answer("Áp suất chỉnh đặt là gì?") is None


VIM = """TCVN 6165:1996
ĐO LƯỜNG HỌC - THUẬT NGỮ CHUNG VÀ CƠ BẢN

1. Phạm vi áp dụng

Tiêu chuẩn này qui định các thuật ngữ chung.

2. Thuật ngữ

| Thuật ngữ | Định nghĩa và giải thích |
| --- | --- |
| 3 Kết quả đo |  |
| 3.9. Độ không đảm bảo đo / A. uncertainty of measurement | Thông số gắn với kết quả của phép đo, đặc trưng cho sự phân tán của các giá trị. |
| A. uncertainty | Chú thích / 1) Thông số có thể là độ lệch chuẩn. |
| 5.21. Sai số cho phép lớn nhất (của phương tiện đo); giới hạn sai số cho phép (của phương tiện đo) / A. maximum permissible errors | Giá trị cực trị của sai số được quy định cho phương tiện đo. |
"""
LAB = """TCVN ISO/IEC 17025:2017

1 Phạm vi áp dụng

Tiêu chuẩn này quy định yêu cầu chung.

2 Tài liệu viện dẫn

Không có.

3 Thuật ngữ và định nghĩa

3.1 Tính khách quan

Sự thể hiện không có xung đột lợi ích.

3.2 Khiếu nại

Sự bày tỏ không hài lòng của cá nhân hay tổ chức với phòng thí nghiệm.

4 Yêu cầu chung
"""


@pytest.fixture
def glossary(docs, tmp_path, monkeypatch):
    files = {"VAN": VAN, "LUU": LUU, "CU": CU, "VIM": VIM, "LAB": LAB}
    for stem in ("VIM", "LAB"):
        (tmp_path / f"{stem}.md").write_text(files[stem], encoding="utf-8")
    monkeypatch.setattr(doc_sections.router, "known_files", lambda: frozenset(files))
    return docs


@pytest.mark.parametrize(
    "question",
    [
        "Độ không đảm bảo đo được định nghĩa thế nào?",
        "Độ không đảm bảo đo là gì?",
        "Theo TCVN 6165, độ không đảm bảo đo là gì?",
        "TCVN 6165:1996 định nghĩa độ không đảm bảo đo như thế nào?",
        "Định nghĩa độ không đảm bảo đo",
    ],
)
def test_definition_from_vocabulary_table_rows(glossary, question):
    # Bảng thuật ngữ TCVN 6165 (không có tiêu đề "#"): mỗi dòng bảng là một mục từ, kèm dòng chú thích sau nó.
    answer = doc_sections.try_section_answer(question)
    assert answer is not None
    assert "đặc trưng cho sự phân tán" in answer.text and "độ lệch chuẩn" in answer.text
    assert [h["payload"]["file_stem"] for h in answer.hits] == ["VIM"]


def test_definition_term_with_parenthetical_and_trailing_qualifier(glossary):
    answer = doc_sections.try_section_answer(
        "Sai số cho phép lớn nhất của phương tiện đo nghĩa là gì?"
    )
    assert answer is not None and "Giá trị cực trị của sai số" in answer.text


def test_definition_from_promoted_numbered_term_sections(glossary):
    answer = doc_sections.try_section_answer("Khiếu nại được định nghĩa như thế nào?")
    assert answer is not None and "không hài lòng" in answer.text
    assert [h["payload"]["file_stem"] for h in answer.hits] == ["LAB"]
