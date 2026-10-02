"""Builder messages cho LLM - llm.prompt.build_messages.

System prompt ép trả lời theo ngữ cảnh + LaTeX verbatim + fallback "Không tìm thấy".
Giữ history_turns lượt cuối; cắt block citations khỏi assistant cũ; chốt bằng query.
"""

from core.settings_loader import get_settings
from llm import prompt


def test_system_prompt_carries_contract():
    msgs = prompt.build_messages("hỏi", "NGỮ CẢNH XYZ", [])
    sys_msg = msgs[0]
    assert sys_msg["role"] == "system"
    assert (
        "Không tìm thấy thông tin này trong các tài liệu QTKĐ được cung cấp." in sys_msg["content"]
    )
    assert "Giữ nguyên công thức LaTeX" in sys_msg["content"]
    assert "NGỮ CẢNH XYZ" in sys_msg["content"]


def test_last_message_is_current_query():
    msgs = prompt.build_messages("câu hỏi cuối", "ctx", [])
    assert msgs[-1] == {"role": "user", "content": "câu hỏi cuối"}


def test_guidance_follows_the_query_in_the_last_user_turn():
    msgs = prompt.build_messages("câu hỏi", "ctx", [], guidance="LƯU Ý: trả lời từng loại.")
    assert msgs[-1] == {"role": "user", "content": "câu hỏi\n\nLƯU Ý: trả lời từng loại."}
    assert "LƯU Ý" not in msgs[0]["content"]


def test_history_limited_to_history_turns():
    prior = [[f"u{i}", f"b{i}"] for i in range(10)]
    msgs = prompt.build_messages("q", "ctx", prior)
    contents = [m["content"] for m in msgs]
    users = [m for m in msgs if m["role"] == "user"]
    assert len(users) == get_settings().llm.chat.history_turns + 1  # lượt cũ + query
    assert {"u7", "u8", "u9"} <= set(contents)
    assert "u6" not in contents


def test_assistant_citations_block_stripped():
    bot = "Câu trả lời chính.\n\n---\n\n**📎 Nguồn tham khảo:**\n\n**[1]** `QTKD` • 6"
    msgs = prompt.build_messages("q", "ctx", [["u1", bot]])
    asst = [m for m in msgs if m["role"] == "assistant"]
    assert len(asst) == 1
    assert asst[0]["content"] == "Câu trả lời chính."


def test_empty_turn_slots_skipped():
    # turn có user nhưng bot None → chỉ thêm user.
    msgs = prompt.build_messages("q", "ctx", [["chỉ user", None]])
    roles = [m["role"] for m in msgs]
    assert roles.count("assistant") == 0
    assert any(m["content"] == "chỉ user" for m in msgs)
