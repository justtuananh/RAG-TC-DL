"""Hỏi lại khi giới hạn tra bảng theo thông số chưa nêu - retrieval.doc_tables + query.limit_clarify."""

import pytest

from query import limit_clarify
from retrieval.doc_tables import captioned_tables

NHIET_KE = """QTKĐ 1.106 : 2018
Nhiệt kế thủy tinh chất lỏng
QUY TRÌNH KIỂM ĐỊNH
# 1 Phạm vi áp dụng
Quy trình này dùng để kiểm định nhiệt kế thủy tinh chất lỏng.
# Phụ lục C
Bảng C.1: Sai số cho phép của nhiệt kế thủy tinh chất lỏng nhúng toàn phần

| Phạm vi đo, oC | Loại nhiệt kế | Giá trị độ chia / nhỏ nhất, oC | Sai số / cho phép (±), oC |
| --- | --- | --- | --- |
| từ - 80 đến 0 | Chất lỏng hữu cơ | 1,0 | 2,0 |
| từ 0 đến 100 | Thủy ngân | 0,1 | 0,3 |
| từ 0 đến 300 | Thủy ngân | 0,5 hoặc 1,0 | 2,0 |

Bảng C.2: Sai số cho phép của nhiệt kế thủy tinh chất lỏng nhúng một phần

| Phạm vi đo, oC | Loại nhiệt kế | Giá trị độ chia nhỏ nhất, oC | Sai số cho phép (±), oC |
| --- | --- | --- | --- |
| từ 0 đến 100 | Thủy ngân | 1,0 | 1,5 |

Bảng C.3.1: Sai số cho phép của nhiệt kế thủy tinh chất lỏng theo ΓOCT 28498 - 90

| Phạm vi đo, oC | Sai số cho phép (±),oC / (Theo giá trị độ chia nhỏ nhất và cấp chính xác) |  |
| --- | --- | --- |
|  | 0,5 | 1 |
|  | cấp 1 | cấp 2 |
| từ 0 đến 100 | 1 | 1 |
"""


def test_captioned_tables_read_caption_header_subheaders_and_rows():
    tables = captioned_tables(NHIET_KE)
    assert [t.label for t in tables] == ["Bảng C.1", "Bảng C.2", "Bảng C.3.1"]
    first = tables[0]
    assert first.header == ("Phạm vi đo, oC", "Loại nhiệt kế", "Giá trị độ chia nhỏ nhất, oC", "Sai số cho phép (±), oC")
    assert first.column(1) == ["Chất lỏng hữu cơ", "Thủy ngân", "Thủy ngân"]
    assert tables[2].subheaders == (("", "0,5", "1"), ("", "cấp 1", "cấp 2")) and len(tables[2].rows) == 1
    assert first.text.startswith("Bảng C.1: Sai số cho phép")


@pytest.fixture
def doc(tmp_path, settings_override, monkeypatch):
    (tmp_path / "NK.md").write_text(NHIET_KE, encoding="utf-8")
    settings_override({"paths.markdown_dir": str(tmp_path)})
    monkeypatch.setattr(limit_clarify.router, "route_files", lambda q: frozenset({"NK"}))


def _asks(answer) -> list[str]:
    return answer.text.split("Vui lòng cho biết thêm:\n\n")[1].split("\n\n")[0].splitlines()


def test_asks_for_every_table_parameter_instead_of_concluding(doc):
    answer = limit_clarify.try_clarify("Nhiệt kế thủy tinh chất lỏng có sai số 0,5 °C thì có đạt không?")
    assert "Chưa đủ thông tin để kết luận đạt hay không đạt" in answer.text
    assert _asks(answer) == [
        "- Bảng áp dụng: nhúng toàn phần (Bảng C.1); nhúng một phần (Bảng C.2); theo ΓOCT 28498 - 90 (Bảng C.3.1)",
        "- Phạm vi đo",
        "- Loại nhiệt kế: Chất lỏng hữu cơ, Thủy ngân",  # "0,5 hoặc 1,0" không phải lựa chọn chữ
        "- Giá trị độ chia nhỏ nhất",
        "- Cấp chính xác",  # từ "(Theo ... và cấp chính xác)" của Bảng C.3.1
    ]
    assert [h["payload"]["section_path"] for h in answer.hits][0] == (
        "Bảng C.1: Sai số cho phép của nhiệt kế thủy tinh chất lỏng nhúng toàn phần"
    )


def test_named_table_narrows_the_questions(doc):
    answer = limit_clarify.try_clarify("Nhiệt kế nhúng một phần sai số 0,5 °C có đạt không?")
    assert len(answer.hits) == 1 and "Bảng C.2" in answer.text
    assert _asks(answer) == ["- Phạm vi đo", "- Loại nhiệt kế: Thủy ngân", "- Giá trị độ chia nhỏ nhất"]


def test_fully_specified_question_is_decided_from_exactly_one_row(doc):
    question = (
        "Nhiệt kế thủy ngân nhúng toàn phần, phạm vi đo từ 0 đến 100 oC, giá trị độ chia nhỏ nhất 0,1 oC, "
        "sai số 0,5 °C có đạt không?"
    )
    answer = limit_clarify.try_clarify(question)
    assert "Theo Bảng C.1: Sai số cho phép của nhiệt kế thủy tinh chất lỏng nhúng toàn phần [1]:" in answer.text
    assert "- Loại nhiệt kế: Thủy ngân\n- Giá trị độ chia nhỏ nhất: 0,1\n- Sai số cho phép: ± 0,3 oC" in answer.text
    assert answer.text.endswith("Sai số 0,5 > 0,3: **Không đạt**.")
    within = question.replace("sai số 0,5", "sai số 0,3")
    assert limit_clarify.try_clarify(within).text.endswith("Sai số 0,3 ≤ 0,3: **Đạt**.")


def test_values_matching_no_single_row_go_on_to_the_normal_pipeline(doc):
    question = "Nhiệt kế thủy ngân nhúng toàn phần, phạm vi đo từ 0 đến 50 oC, độ chia 0,1 oC, sai số 0,5 °C có đạt không?"
    assert limit_clarify.try_clarify(question) is None  # không có dòng 0-50: không đoán


def test_follow_up_with_the_missing_parameters_completes_the_first_question(doc):
    first = "Nhiệt kế thủy tinh chất lỏng có sai số 0,5 °C thì có đạt không?"
    asked = limit_clarify.try_clarify(first)
    follow_up = "Thủy ngân, nhúng toàn phần, phạm vi đo từ 0 đến 100 oC, độ chia nhỏ nhất 0,1 oC"
    assert limit_clarify.try_clarify(follow_up) is None  # một mình không phải câu hỏi đạt/không đạt
    answer = limit_clarify.try_clarify(follow_up, (first, asked.text))
    assert answer.text.endswith("Sai số 0,5 > 0,3: **Không đạt**.")
    assert limit_clarify.try_clarify(follow_up, (first, "Câu trả lời thường.")) is None


def test_not_a_compliance_question_or_no_limit_table(doc, settings_override):
    assert limit_clarify.try_clarify("Sai số cho phép của nhiệt kế thủy tinh chất lỏng là bao nhiêu?") is None
    settings_override({"limit_clarify.limit_pattern": r"\bkhong co bang nay\b"})
    assert limit_clarify.try_clarify("Nhiệt kế sai số 0,5 °C có đạt không?") is None
