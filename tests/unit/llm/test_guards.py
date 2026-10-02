"""Guard sinh câu trả lời - llm.guards.

Yêu cầu tính toán với số liệu cho sẵn bị chặn tất định trước khi gọi LLM; câu
chứa câu từ chối chuẩn bị cắt mọi thứ phía sau.
"""

from llm import guards


def test_enforce_refusal_stop_truncates_after_canonical_sentence():
    # Q126 đo được: model ghi câu từ chối rồi vẫn thay số tính tiếp (Δ=2 bar).
    tail = guards.REFUSAL_SENTENCE + "\n\nTuy nhiên, thay số: 42 - 40 = 2 bar."
    assert guards.enforce_refusal_stop(tail) == guards.REFUSAL_SENTENCE
    # Không chứa câu từ chối → giữ nguyên.
    assert guards.enforce_refusal_stop("Trả lời bình thường [1].") == "Trả lời bình thường [1]."
    # Câu từ chối ở giữa văn bản: cắt từ sau câu đó.
    mid = "Mở đầu. " + guards.REFUSAL_SENTENCE + " Phần thừa."
    assert guards.enforce_refusal_stop(mid) == "Mở đầu. " + guards.REFUSAL_SENTENCE


def test_is_calculation_request_narrow_patterns():
    # Yêu cầu tính với số liệu cho sẵn (Q126) → chặn.
    assert guards.is_calculation_request(
        "Tính giúp tôi sai số áp suất chỉnh đặt nếu Pm = 42 bar và Pcd = 40 bar."
    )
    assert guards.is_calculation_request("Hãy tính sai số khi P = 100 bar")
    # TRA CỨU công thức/cách tính là hợp lệ - không được chặn.
    assert not guards.is_calculation_request("Công thức tính thời gian quay tự do pittông?")
    assert not guards.is_calculation_request("Cách tính sai số thiết bị đo áp suất số?")
    assert not guards.is_calculation_request("Sai số cho phép là bao nhiêu?")
    # Có '=' nhưng không có 'tính' → câu hỏi tra cứu về công thức, hợp lệ.
    assert not guards.is_calculation_request("Ý nghĩa của Pm trong ΔP = Pm - Pcd là gì?")
