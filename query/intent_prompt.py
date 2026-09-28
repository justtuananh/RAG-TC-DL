"""Prompt của bộ phân loại intent (spec §8): system prompt, quy tắc, ví dụ.

Tách khỏi ``query/intents.py`` để tệp đó gọn. Prompt chỉ dạy LLM chọn intent và
điền tham số JSON; không có text-to-SQL. Toàn bộ prompt đang ~4 000 token nên bộ
phân loại chạy với ``num_ctx`` 8192 (xem ``OllamaIntentConfig``).
"""

from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = (
    "Bạn là bộ định tuyến câu hỏi cho trợ lý kiểm định đo lường Việt Nam. "
    "Nhiệm vụ DUY NHẤT: chọn intent và điền tham số. Chỉ trả về JSON hợp lệ, "
    "không giải thích, không viết SQL. Nếu không chắc chắn, trả branch \"text\"."
)


CLASSIFIER_RULES = (
    "Quy tắc:\n"
    "1. Tham số CHỈ được lấy từ giá trị xuất hiện nguyên văn trong câu hỏi; không bịa, "
    "không lấy giá trị từ ví dụ.\n"
    "2. Số hiệu thiết bị: hỏi lần cuối/lần gần đây nhất/khi nào hết hạn -> "
    "latest_record; hỏi lịch sử/các lần/đã kiểm mấy lần -> device_history; hỏi "
    "diễn biến/xu hướng sai số -> error_trend. Câu hỏi KHÔNG nêu số hiệu thiết bị cụ "
    "thể thì KHÔNG dùng ba intent này. Câu hỏi CÓ số hiệu thiết bị cụ thể thì KHÔNG "
    "dùng records_by_period, kể cả khi có chữ đạt/không đạt (kết luận của lần mới "
    "nhất thuộc latest_record).\n"
    "3. Câu hỏi KHÔNG nêu số QTKĐ và cũng không nêu loại thiết bị cụ thể thì KHÔNG "
    "dùng procedure_params, standards_for.\n"
    "4. Câu hỏi về quy định, công thức, khái niệm, cách làm, sai số cho phép chung "
    'thì branch "text".\n'
    '5. branch "data" cho hầu hết câu hỏi số liệu/thông số QTKĐ. Dùng "mixed" khi câu '
    "hỏi hỏi ĐỒNG THỜI quy định/thông số/phương tiện của QTKĐ VÀ dữ liệu hồ sơ thực tế "
    "(các lần kiểm, sổ cái, hồ sơ thực tế).\n"
    "6. Số hiệu thiết bị (serial) dùng cho device_history/latest_record/error_trend; "
    "nó KHÔNG phải loại thiết bị (device_type).\n"
    "7. Câu hỏi nêu số hiệu thiết bị và hỏi các lần kiểm định/lịch sử -> "
    "device_history, ưu tiên hơn procedure_params; dùng branch mixed nếu đồng thời "
    "hỏi quy định/phạm vi đo của QTKĐ.\n"
    '8. "thông số", "phạm vi đo", "cấp chính xác", "chu kỳ" của QTKĐ -> procedure_params. '
    '"phương tiện kiểm định", "bảng 2" -> standards_for.\n'
    "9. Ngày dạng YYYY-MM-DD. 'từ năm A đến năm B' -> date_from A-01-01, date_to "
    "B-12-31, giữ ĐÚNG A/B kể cả khi A lớn hơn B (không tự đảo). 'năm 2024' -> "
    "date_from 2024-01-01, date_to 2024-12-31.\n"
    '10. Chỉ điền verdict "khong_dat"/"dat" khi câu hỏi nói đạt/không đạt.\n'
    "11. Phân biệt THIẾT BỊ cần kiểm (device_history/latest_record/error_trend) với "
    "CHUẨN MẪU dùng để kiểm (lab_standard_lookup). Câu nhắc 'chuẩn', 'chuẩn mẫu', "
    "'PTĐ', 'PTTN', chu kỳ hiệu chuẩn, hoặc số hiệu/ký hiệu của chuẩn thì dùng "
    "lab_standard_lookup, KHÔNG dùng ba intent thiết bị dù có chữ 'số hiệu'/'gần nhất'.\n"
    "12. Câu hỏi một tiêu chuẩn/quy trình 'là quy trình gì', 'cấp nào ban hành', "
    "'năm nào', hoặc liệt kê quy trình theo nhóm lĩnh vực/tên thiết bị -> "
    "procedure_catalog_lookup, KHÔNG dùng procedure_params/standards_for (hai intent "
    "đó chỉ tra thông số/bảng 2 của QTKĐ đã có trong kho tài liệu).\n"
    "13. Câu hỏi kiểm định viên, ai được chứng nhận, số thẻ -> inspector_lookup; hỏi "
    "lĩnh vực/phạm vi được công nhận của phòng, dải đo/CCX theo công nhận, số KĐV -> "
    "capability_lookup.\n"
    "14. Chuẩn mẫu có thể được nhắc bằng KÝ HIỆU/MODEL nhiều từ (ví dụ 'Fluke "
    "5624-20-B', 'Thunder 1200', 'TESON II') chứ không chỉ bằng 'chuẩn'/'số hiệu'. Câu "
    "hỏi chu kỳ/hạn/lần hiệu chuẩn gần nhất của ký hiệu đó -> lab_standard_lookup với "
    "query là ký hiệu, KHÔNG dùng ba intent thiết bị.\n"
    "15. Câu 'ai (trong phòng) được/có thể kiểm định hoặc hiệu chuẩn <loại thiết bị/"
    "đại lượng>' hay 'kiểm định viên nào ... <loại thiết bị/đại lượng>' -> "
    "inspector_lookup, field = loại thiết bị/đại lượng (ví dụ 'độ pH').\n"
    "16. Ranh giới Biểu 4 và Biểu 1: 'quy trình <thiết bị> là gì', 'mã quy trình X là "
    "gì', 'danh mục quy trình nhóm Y' -> procedure_catalog_lookup; 'lĩnh vực <thiết bị> "
    "được công nhận ra sao', 'áp dụng quy trình nào', 'dải đo nào', 'mấy KĐV' -> "
    "capability_lookup.\n"
    "17. Câu hỏi nêu SỐ BIÊN BẢN (dạng 011/2024) hoặc số hiệu thiết bị KÈM ngày kiểm "
    "định cụ thể -> record_lookup. Câu hỏi nêu số QTKĐ (dạng 1.061) KHÔNG phải "
    "record_lookup.\n"
    "18. Câu hỏi đếm/liệt kê trên TOÀN BỘ hồ sơ, theo kiểm định viên, theo đơn vị phạm vi "
    "đo, hoặc biên bản có giá trị nhỏ nhất/lớn nhất -> records_summary.\n"
    '19. Không chắc chắn -> {"branch": "text"}.'
)

CLASSIFIER_EXAMPLES = (
    "Ví dụ:\n"
    '- "Cho xem các lần kiểm của đồng hồ KX-8" -> '
    '{"branch":"data","intent":"device_history","params":{"serial":"KX-8"}}\n'
    '- "CXN-5 đã được kiểm tra bao nhiêu đợt rồi" -> '
    '{"branch":"data","intent":"device_history","params":{"serial":"CXN-5"}}\n'
    '- "Kết quả đợt kiểm mới nhất của KX-8 thế nào" -> '
    '{"branch":"data","intent":"latest_record","params":{"serial":"KX-8"}}\n'
    '- "Giấy chứng nhận của KX-8 hết hiệu lực ngày nào" -> '
    '{"branch":"data","intent":"latest_record","params":{"serial":"KX-8"}}\n'
    '- "KX-8 đợt mới nhất đạt hay không đạt" -> '
    '{"branch":"data","intent":"latest_record","params":{"serial":"KX-8"}}\n'
    '- "Có mấy biên bản được lập trong năm 2022" -> '
    '{"branch":"data","intent":"records_by_period","params":'
    '{"date_from":"2022-01-01","date_to":"2022-12-31"}}\n'
    '- "Liệt kê biên bản bị đánh giá không đạt thời điểm 2021" -> '
    '{"branch":"data","intent":"records_by_period","params":'
    '{"date_from":"2021-01-01","date_to":"2021-12-31","verdict":"khong_dat"}}\n'
    '- "Bảng kê biên bản từ năm 2020 đến năm 2019" -> '
    '{"branch":"data","intent":"records_by_period","params":'
    '{"date_from":"2020-01-01","date_to":"2019-12-31"}}\n'
    '- "Những đồng hồ áp suất nào có dải đo 0 tới 250 bar" -> '
    '{"branch":"data","intent":"devices_by_range","params":'
    '{"quantity":"áp suất","min_value":0,"max_value":250,"unit":"bar"}}\n'
    '- "Bộ dữ kiện tham chiếu của quy trình 3.204 gồm gì" -> '
    '{"branch":"data","intent":"procedure_params","params":{"procedure_number":"3.204"}}\n'
    '- "Đặc tính kỹ thuật của đồng hồ áp suất là gì" -> '
    '{"branch":"data","intent":"procedure_params","params":{"device_type":"đồng hồ áp suất"}}\n'
    '- "Danh sách chuẩn hiệu chuẩn kèm theo quy trình 3.204" -> '
    '{"branch":"data","intent":"standards_for","params":{"procedure_number":"3.204"}}\n'
    '- "Sai lệch của KX-8 biến thiên ra sao theo thời gian" -> '
    '{"branch":"data","intent":"error_trend","params":{"serial":"KX-8"}}\n'
    '- "Phạm vi đo quy định trong quy trình 3.204 và KX-8 đã kiểm những lần nào" -> '
    '{"branch":"mixed","intent":"device_history","params":{"serial":"KX-8"}}\n'
    '- "Chuẩn hiệu chuẩn của quy trình 3.204 và đối chiếu sổ cái" -> '
    '{"branch":"mixed","intent":"standards_for","params":{"procedure_number":"3.204"}}\n'
    '- "Làm sao bù nhiệt độ cho kết quả đo" -> {"branch":"text"}\n'
    '- "Mức sai số nào được chấp nhận cho phép đo áp suất" -> {"branch":"text"}\n'
    '- "Khái niệm độ không đảm bảo đo là gì" -> {"branch":"text"}\n'
    '- "Chuẩn mẫu hiệu MO-1226 có chu kỳ hiệu chuẩn bao lâu" -> '
    '{"branch":"data","intent":"lab_standard_lookup","params":{"query":"MO-1226"}}\n'
    '- "Chuẩn nào phục vụ mục IV.3 của Biểu 1" -> '
    '{"branch":"data","intent":"lab_standard_lookup","params":{"usage_ref":"IV.3"}}\n'
    '- "Ai được chứng nhận đo áp suất" -> '
    '{"branch":"data","intent":"inspector_lookup","params":{"field":"áp suất"}}\n'
    '- "Số thẻ của kiểm định viên Nguyễn Thị Hương" -> '
    '{"branch":"data","intent":"inspector_lookup","params":{"name":"Nguyễn Thị Hương"}}\n'
    '- "ĐLVN 213:2009 là gì, cơ quan nào ban hành" -> '
    '{"branch":"data","intent":"procedure_catalog_lookup","params":{"code":"ĐLVN 213:2009"}}\n'
    '- "Liệt kê quy trình nhóm tốc độ vòng quay" -> '
    '{"branch":"data","intent":"procedure_catalog_lookup","params":{"group":"tốc độ vòng quay"}}\n'
    '- "Phòng được công nhận hiệu chuẩn nhiệt kế điện trở không" -> '
    '{"branch":"data","intent":"capability_lookup","params":{"keyword":"nhiệt kế điện trở"}}\n'
    '- "Hạn hiệu chuẩn ghi trên chuẩn hiệu Thunder 1200 là khi nào" -> '
    '{"branch":"data","intent":"lab_standard_lookup","params":{"query":"Thunder 1200"}}\n'
    '- "Trong phòng ai có thể hiệu chuẩn thiết bị đo độ pH" -> '
    '{"branch":"data","intent":"inspector_lookup","params":{"field":"độ pH"}}\n'
    '- "Lĩnh vực đồng hồ tốc độ vòng quay áp dụng quy trình nào" -> '
    '{"branch":"data","intent":"capability_lookup","params":{"keyword":"đồng hồ tốc độ vòng quay"}}\n'
    '- "Quy trình kiểm định đồng hồ bấm giây là gì" -> '
    '{"branch":"data","intent":"procedure_catalog_lookup","params":{"keyword":"đồng hồ bấm giây"}}\n'
    '- "Biên bản 007/2021 của thiết bị KX-8 ghi phương tiện kiểm định gì" -> '
    '{"branch":"data","intent":"record_lookup","params":{"serial":"KX-8","cert_no":"007/2021"}}\n'
    '- "Kiểm định viên Lê Văn A lập bao nhiêu biên bản" -> '
    '{"branch":"data","intent":"records_summary","params":{"inspector":"Lê Văn A","measure":"count"}}'
)


def render_classifier_prompt(question: str, intent_catalog: dict[str, dict[str, Any]]) -> str:
    """Prompt phân loại: danh mục intent + quy tắc + ví dụ + câu hỏi."""
    catalog_lines = []
    for name, info in intent_catalog.items():
        params = ", ".join(f'"{k}": {v}' for k, v in info["params"].items())
        catalog_lines.append(f'- "{name}": {info["mo_ta"]} params: {{{params}}}')
    catalog = "\n".join(catalog_lines)
    return (
        "Danh mục intent:\n"
        f"{catalog}\n\n"
        f"{CLASSIFIER_RULES}\n\n"
        f"{CLASSIFIER_EXAMPLES}\n\n"
        "Định dạng JSON:\n"
        '{"branch": "data", "intent": "<tên intent>", "params": {...}, "confidence": 0.9}\n'
        'hoặc {"branch": "text", "intent": "text", "params": {}, "confidence": 0.9}\n\n'
        f"Câu hỏi: {question}"
    )
