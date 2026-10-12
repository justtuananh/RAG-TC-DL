Lượt này không dùng để kết luận chất lượng: benchmark chạy khi uvicorn đang khởi động. 20 yêu cầu chuẩn bị công thức và 12 câu hỏi ngoài phạm vi gặp lỗi kết nối; 200 ca tính số phụ thuộc vì vậy không chạy được. Đến khi chạy Chromium thì server đã sẵn sàng, 20/20 UI đạt.

`false_refusals: 200` trong summary là lỗi phân loại của harness phiên bản cũ: thực tế là lỗi hạ tầng, không phải registry từ chối. Đã thêm health check trước khi mở lượt benchmark và tách infrastructure_affected_cases trong các lượt sau. Giữ nguyên artifact gốc để không che giấu lần chạy lỗi.
