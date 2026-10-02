"""Guard hành vi lookup-only: chặn yêu cầu tính toán và cắt sau câu từ chối.

Hệ là tra cứu thuần, không tính toán; các guard ở đây chạy tất định trước khi gọi
LLM nên hành vi không phụ thuộc model.
"""

from __future__ import annotations

import re

# Câu từ chối chuẩn (khớp SYSTEM_TMPL quy tắc 5 + scoring.answer_scoring.REFUSAL_CORE).
REFUSAL_SENTENCE = "Không tìm thấy thông tin này trong các tài liệu QTKĐ được cung cấp."

# Yêu cầu TÍNH TOÁN tường minh với số liệu cho sẵn - hệ là lookup-only nên từ
# chối TẤT ĐỊNH trước khi gọi LLM (đo Q126: 7b lúc từ chối lúc thay số tính
# Δ=2 bar tuỳ phương sai prompt; quy tắc 5 không đủ chắc). Mẫu giữ HẸP:
#   - mệnh lệnh "tính giúp/hộ/dùm/thử/xem ..."  HOẶC
#   - có chữ "tính" đi cùng dữ kiện gán giá trị "X = <số>".
# "Công thức tính sai số?" / "Cách tính ĐKĐBĐ?" là TRA CỨU hợp lệ - không khớp.
_CALC_IMPERATIVE_RE = re.compile(r"\btính\s+(giúp|hộ|dùm|thử|xem)\b", re.IGNORECASE)
_CALC_WITH_VALUES_RE = re.compile(r"\btính\b", re.IGNORECASE)
_ASSIGNED_VALUE_RE = re.compile(r"=\s*\d")


def is_calculation_request(query: str) -> bool:
    """True nếu câu hỏi là yêu cầu tính toán với số liệu cho sẵn (ngoài phạm vi
    lookup-only). ui.gradio_app và api chặn trước khi retrieve; answer_eval mirror cùng hàm."""
    if _CALC_IMPERATIVE_RE.search(query):
        return True
    return bool(_CALC_WITH_VALUES_RE.search(query) and _ASSIGNED_VALUE_RE.search(query))


def enforce_refusal_stop(text: str) -> str:
    """Nếu câu trả lời chứa câu từ chối chuẩn → cắt MỌI THỨ sau câu đó.

    Đo trên 7b (Q126): model chịu ghi câu từ chối cho yêu cầu tính toán rồi…
    vẫn thay số tính tiếp (Δ=2 bar) - vi phạm lookup-only. Nhồi thêm prompt
    ("DỪNG LẠI") làm hành vi từ chối dao động ở câu khác (Q121/Q126 đổi chiều);
    cắt tất định sau câu chuẩn thì không có phương sai. Văn bản không chứa câu
    từ chối → trả nguyên vẹn.
    """
    idx = text.find(REFUSAL_SENTENCE)
    if idx < 0:
        return text
    return text[: idx + len(REFUSAL_SENTENCE)]
