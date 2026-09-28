# Phạm vi và giới hạn phép thử

- 7 DOCX được đưa vào truy hồi; 6 bộ tính từ 3 DOCX được hỗ trợ. Đây không phải đánh giá tất cả 351 đối tượng toán học, cũng không phải 351 công thức tính độc lập.
- Tập cuối giữ lại câu hỏi/đầu vào và tổ hợp lỗi; không giữ lại một họ công thức hoàn toàn chưa biết. Vì vậy điểm số thể hiện độ ổn định trên danh mục đã chuẩn bị, chưa chứng minh khả năng mở rộng sang tài liệu mới.
- Cả ba hướng dùng danh mục công thức và trích đoạn nguồn đã được chọn, bộ định tuyến từ khóa, vocabulary biến, engine Decimal và lớp kiểm tra đơn vị chung. Worktree khác nhau ở cách tạo/xác nhận định nghĩa bộ tính; không phải ba hệ thống RAG độc lập được tối ưu riêng.
- Truy hồi dùng 141 cửa sổ văn bản trên 7 DOCX. Kiểm tra e2e yêu cầu tài liệu đúng xuất hiện trong top 5; vị trí/công thức cụ thể do bộ định tuyến chung chọn trong danh mục. Chưa đo toàn bộ khả năng trả lời tự do của chatbot React gốc.
- Không dùng LLM chấm điểm. Giá trị chuẩn tính bằng hàm Decimal riêng, không lấy từ engine được kiểm thử. Ba lượt lặp không tương đương ba lần số ca độc lập.
- Browser chạy Chromium thật và gọi API tính qua FastAPI TestClient; bước chuẩn bị form phát lại định nghĩa do phương án tạo trong chính lượt chạy đó. Lời gọi OpenRouter và truy hồi được đo riêng, tránh gọi LLM lại cho từng thao tác trình duyệt.
- Nguồn được Codex đối chiếu kỹ thuật qua XML/render DOCX. Chưa có người chuyên môn đo lường duyệt. Kho công thức đúng phụ thuộc chất lượng bước duyệt; hash chỉ phát hiện thay đổi sau khi duyệt, không chứng minh công thức đã duyệt là đúng.
- Các ca lỗi ingestion là dữ liệu lỗi được chèn có kiểm soát. Chưa đo tỷ lệ lỗi thực tế của bộ chuyển đổi MathType/OMML trên toàn bộ dữ liệu.
- Điều kiện vật lý một phần do người dùng xác nhận. Số gõ nhầm nhưng còn hợp lệ (ví dụ 15 thay vì 1.5) không thể luôn phát hiện.
- Chưa thực hiện đánh giá đạt/không đạt thiết bị, lan truyền độ không đảm bảo đo, hoặc kiểm thử trên công thức ngoài tập hỗ trợ.
- Giao diện thử chạy độc lập trong `formula_lab`, chưa thay đổi giao diện React/luồng từ chối tính toán của chatbot gốc. Bản được chọn trên dev là nguyên mẫu đã đo, không tuyên bố đã hoàn tất tích hợp sản phẩm.
- Kho công thức phải được bổ sung, đối chiếu và kiểm thử khi thêm quy trình hoặc thay phiên bản. LLM/parser có thể hỗ trợ tạo nháp nhưng không tự động nâng một công thức mới lên trạng thái đã kiểm chứng.
