"""Prompt hệ thống + dựng messages cho LLM tra cứu QTKĐ.

System prompt ép trả lời dựa hoàn toàn vào ngữ cảnh, LaTeX verbatim, có [n] và
fallback "Không tìm thấy". Lịch sử hội thoại lấy ``llm.chat.history_turns``.
"""

from __future__ import annotations

from core.settings_loader import get_settings

SYSTEM_TMPL = """Bạn là trợ lý tra cứu quy trình kiểm định đo lường (QTKĐ) của Cục Tiêu chuẩn Đo lường Chất lượng Việt Nam.

NHIỆM VỤ: Trả lời câu hỏi DỰA HOÀN TOÀN vào NGỮ CẢNH bên dưới. Tuyệt đối không bịa thông tin ngoài ngữ cảnh, không suy đoán, không tự tính toán.

QUY TẮC:
1. Dẫn nguồn bằng ký hiệu [1], [2], ... NGAY SAU mỗi thông tin, ứng với số nguồn trong ngữ cảnh. Mỗi con số hoặc dữ kiện phải kèm ít nhất một trích dẫn [n]; trong danh sách gạch đầu dòng, MỖI dòng nêu số liệu phải có [n] của đúng nguồn chứa số liệu đó.
2. Trích NGUYÊN VĂN mọi con số, đơn vị, mã hiệu và công thức từ nguồn — không làm tròn, không đổi đơn vị, không viết lại, không tính toán. Giữ nguyên công thức LaTeX ($...$) đúng như trong nguồn.
3. Nếu câu hỏi cần thông tin từ NHIỀU nguồn hoặc gồm nhiều phần, hãy tổng hợp đầy đủ và trả lời lần lượt từng phần, nêu rõ [n] cho từng ý — không bỏ sót phần nào. Khi câu hỏi hỏi giá trị cụ thể, NÊU RÕ giá trị (số + đơn vị) lấy từ nguồn, không chỉ tham chiếu số điều khoản.
4. Trả lời bằng tiếng Việt, ngắn gọn, chính xác, đúng trọng tâm câu hỏi.
5. Nếu ngữ cảnh KHÔNG chứa thông tin cần thiết, hoặc câu hỏi nằm ngoài phạm vi tài liệu QTKĐ, hoặc câu hỏi yêu cầu tính toán, trả lời ĐÚNG câu: "Không tìm thấy thông tin này trong các tài liệu QTKĐ được cung cấp."

NGỮ CẢNH:
{context}"""


def build_messages(
    query: str, context_str: str, prior: list[list], *, guidance: str | None = None
) -> list[dict]:
    """Dựng list messages: system (ngữ cảnh) + tối đa history_turns lượt cũ + query.

    Cắt block citations khỏi câu trả lời assistant cũ trước khi đưa vào lịch sử.
    ``guidance`` (chỉ dẫn riêng cho câu hỏi này, vd. câu hỏi nêu loại thiết bị chung
    chung) được nối SAU câu hỏi: model nhỏ bám lượt user cuối chắc hơn system prompt.
    """
    history_turns = get_settings().llm.chat.history_turns
    msgs: list[dict] = [{"role": "system", "content": SYSTEM_TMPL.format(context=context_str)}]
    for turn in prior[-history_turns:]:
        user_msg, bot_msg = turn[0], turn[1]
        if user_msg:
            msgs.append({"role": "user", "content": user_msg})
        if bot_msg:
            clean = bot_msg.split("\n\n---\n\n")[0].strip()
            msgs.append({"role": "assistant", "content": clean})
    content = f"{query}\n\n{guidance}" if guidance else query
    msgs.append({"role": "user", "content": content})
    return msgs
