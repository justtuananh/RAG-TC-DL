"""Nguồn gửi về panel - api.services.chat_stream._build_sources_payload.

Ngữ cảnh LLM dùng mọi đoạn con khớp của mục (``anchor_texts``); panel nguồn chỉ trích
``llm.context.quote_anchors`` đoạn khớp nhất để đoạn trích gọn.
"""

from api.services.chat_stream import _build_sources_payload


def test_quote_uses_only_the_top_anchors(settings_override):
    settings_override({"llm.context.quote_anchors": 2})
    anchors = ["Đoạn khớp một.", "Đoạn khớp hai.", "Đoạn khớp ba."]
    hit = {
        "payload": {"file_stem": "QTKD_1.159", "section_path": "6.3.2", "text": anchors[0]},
        "anchor_texts": anchors,
        "parent_payload": {"text": "\n\n".join(anchors)},
        "rerank_score": 0.9,
    }
    quote = _build_sources_payload([hit])[0]["quote"]
    assert anchors[0] in quote and anchors[1] in quote
    assert anchors[2] not in quote
