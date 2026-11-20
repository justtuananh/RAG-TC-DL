"""Thêm tên gọi trong tài liệu vào câu hỏi - query.synonyms."""

from query import synonyms


def test_adds_the_document_term_once(settings_override):
    settings_override({"query_synonyms": [{"term": "độ kín", "adds": "độ tụt áp"}]})
    assert synonyms.expand("Các bước kiểm tra Độ kín của bình phân ly?") == (
        "Các bước kiểm tra Độ kín (độ tụt áp) của bình phân ly?"
    )
    assert synonyms.expand("độ kín hay độ tụt áp?") == "độ kín hay độ tụt áp?"
    assert synonyms.expand("độ kínx") == "độ kínx"  # chỉ khớp trọn từ


def test_no_synonyms_configured_keeps_the_question(settings_override):
    settings_override({"query_synonyms": []})
    assert synonyms.expand("độ kín") == "độ kín"
