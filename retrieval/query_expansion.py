"""Mở rộng truy vấn bằng cầu nối từ vựng cho cả embedding lẫn BM25.

Reranker vẫn nhận truy vấn GỐC - chèn thêm đồng nghĩa làm hỏng cross-encoder
(arXiv 2311.09175).
"""

from __future__ import annotations

LEXICON: dict[str, str] = {
    # Cầu nối từ vựng: trigger (substring, lowercase) → cụm đồng nghĩa nối thêm vào
    # truy vấn embed + BM25 (reranker vẫn nhận query gốc). Nhắm khẩu ngữ/paraphrase
    # và thuật ngữ song ngữ Việt–Anh trong các QTKĐ áp suất.
    "điều kiện môi trường": "điều kiện kiểm định nhiệt độ độ ẩm áp suất khí quyển",
    # Chiều ngược lại: hỏi bằng ĐÚNG tiêu đề mục 4.1/5.1 ("Điều kiện kiểm định") nhưng
    # body mục đó chỉ là bullet đơn vị (Nhiệt độ/Độ ẩm/…) không lặp lại tiêu đề -
    # Q18 dense=36/bm25=22 nên không lọt phễu top_k=20. Khung mục này có ở MỌI QTKĐ.
    "điều kiện kiểm định": "điều kiện môi trường nhiệt độ độ ẩm áp suất khí quyển",
    # Khẩu ngữ hỏi thẳng đại lượng môi trường (không nói "điều kiện") - kéo về mục
    # 4.1/5.1; "môi trường"/"tương đối" trong trigger giữ cho câu hỏi HIỆU CHỈNH
    # nhiệt độ ("nhiệt độ lệch", "hiệu chỉnh nhiệt độ") không bị kích nhầm.
    "nhiệt độ môi trường": "điều kiện kiểm định nhiệt độ môi trường độ ẩm",
    "độ ẩm tương đối": "điều kiện kiểm định độ ẩm tương đối nhiệt độ môi trường",
    "sai số cho phép": "sai số giới hạn dung sai độ chính xác cấp chính xác",
    "thời gian quay tự do": "thời gian quay tự do píttông kiểm tra kỹ thuật độ nhớt",
    "độ chênh áp": "độ chênh áp blowdown chênh lệch áp suất đóng áp suất chỉnh đặt",
    "áp suất chỉnh đặt": "áp suất chỉnh đặt set pressure áp suất mở van",
    "thử thủy tĩnh": "thử thủy tĩnh kiểm tra độ kín chịu tải thời gian tối thiểu",
    "kẹp chì": "kẹp chì niêm phong dấu niêm phong kiểm tra bên ngoài",
    "thiết bị chuẩn": "phương tiện kiểm định thiết bị chuẩn áp kế chuẩn",
    "số lần đo": "số lần đo số loạt đo số điểm đo chu trình kiểm định",
    "chu kỳ kiểm định": "chu kỳ kiểm định định kỳ thời hạn tháng xử lý chung",
    "diện tích hiệu dụng": "diện tích hiệu dụng píttông xác định đo lường",
    "van xả áp": "van an toàn van xả áp suất safety valve",
}


def expand_query(query: str) -> str:
    """Append domain synonyms to bridge vocabulary gaps in embed + BM25.

    Reranker still receives the original query - expanded text degrades
    cross-encoder performance (arXiv 2311.09175).
    """
    q_lower = query.lower()
    extras = [exp for trigger, exp in LEXICON.items() if trigger in q_lower]
    return (query + " " + " ".join(extras)) if extras else query
