"""Builder messages cho LLM — generation.build_messages.

System prompt ép trả lời theo ngữ cảnh + LaTeX verbatim + fallback "Không tìm thấy".
Giữ HISTORY_TURNS lượt cuối; cắt block citations khỏi assistant cũ; chốt bằng query.
"""

import generation


def test_system_prompt_carries_contract():
    msgs = generation.build_messages("hỏi", "NGỮ CẢNH XYZ", [])
    sys_msg = msgs[0]
    assert sys_msg["role"] == "system"
    assert (
        "Không tìm thấy thông tin này trong các tài liệu QTKĐ được cung cấp." in sys_msg["content"]
    )
    # G2 đổi câu chữ quy tắc công thức — pin theo lõi bất biến của contract.
    assert "Công thức LaTeX" in sys_msg["content"]
    assert "chép đúng dạng inline" in sys_msg["content"]
    assert "NGỮ CẢNH XYZ" in sys_msg["content"]


def test_last_message_is_current_query():
    msgs = generation.build_messages("câu hỏi cuối", "ctx", [])
    assert msgs[-1] == {"role": "user", "content": "câu hỏi cuối"}


def test_history_limited_to_history_turns():
    prior = [[f"u{i}", f"b{i}"] for i in range(10)]
    msgs = generation.build_messages("q", "ctx", prior)
    contents = [m["content"] for m in msgs]
    users = [m for m in msgs if m["role"] == "user"]
    assert len(users) == generation.HISTORY_TURNS + 1  # 3 lượt cũ + query
    assert {"u7", "u8", "u9"} <= set(contents)
    assert "u6" not in contents


def test_assistant_citations_block_stripped():
    bot = "Câu trả lời chính.\n\n---\n\n**📎 Nguồn tham khảo:**\n\n**[1]** `QTKD` • 6"
    msgs = generation.build_messages("q", "ctx", [["u1", bot]])
    asst = [m for m in msgs if m["role"] == "assistant"]
    assert len(asst) == 1
    assert asst[0]["content"] == "Câu trả lời chính."


def test_empty_turn_slots_skipped():
    # turn có user nhưng bot None → chỉ thêm user.
    msgs = generation.build_messages("q", "ctx", [["chỉ user", None]])
    roles = [m["role"] for m in msgs]
    assert roles.count("assistant") == 0
    assert any(m["content"] == "chỉ user" for m in msgs)


def test_enforce_refusal_stop_truncates_after_canonical_sentence():
    # Q126 đo được: model ghi câu từ chối rồi vẫn thay số tính tiếp (Δ=2 bar).
    tail = generation.REFUSAL_SENTENCE + "\n\nTuy nhiên, thay số: 42 - 40 = 2 bar."
    assert generation.enforce_refusal_stop(tail) == generation.REFUSAL_SENTENCE
    # Không chứa câu từ chối → giữ nguyên.
    assert generation.enforce_refusal_stop("Trả lời bình thường [1].") == "Trả lời bình thường [1]."
    # Câu từ chối ở giữa văn bản: cắt từ sau câu đó.
    mid = "Mở đầu. " + generation.REFUSAL_SENTENCE + " Phần thừa."
    assert generation.enforce_refusal_stop(mid) == "Mở đầu. " + generation.REFUSAL_SENTENCE
