"""Thêm tên gọi trong tài liệu vào câu hỏi dùng từ đồng nghĩa ("độ kín" → "độ kín (độ tụt áp)").

Người dùng hỏi "kiểm tra độ kín của bình phân ly" nhưng QTKĐ gọi phép này là "xác định độ tụt áp": tìm kiếm
và LLM không nối được hai cách gọi nên trả lời "không tìm thấy". Danh sách cặp từ nằm ở ``query_synonyms:``
trong settings; câu hỏi đã có sẵn tên trong tài liệu thì giữ nguyên.
"""

from __future__ import annotations

import re
import unicodedata

from core.settings_loader import get_settings


def expand(question: str) -> str:
    text = unicodedata.normalize("NFC", question)
    for synonym in get_settings().query_synonyms:
        term = unicodedata.normalize("NFC", synonym.term)
        adds = unicodedata.normalize("NFC", synonym.adds)
        if re.search(re.escape(adds), text, re.IGNORECASE):
            continue
        match = re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE)
        if match:
            text = f"{text[: match.end()]} ({adds}){text[match.end() :]}"
    return text
