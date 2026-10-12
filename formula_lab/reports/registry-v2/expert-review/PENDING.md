# Các công thức cần làm rõ trước khi triển khai

Trạng thái ngày 28/09/2026: chưa phê duyệt. Danh sách tổng hợp từ [hồ sơ kỹ thuật](../source-review/REVIEW.md), không phải phát hiện mới hoặc kết luận chuyên môn.

| ID trong QTKĐ 1.190 | Điểm cần chuyên gia giải quyết | Bằng chứng cần bổ sung |
|---|---|---|
| F002 | Nhiều hệ số và phạm vi áp dụng | Định nghĩa từng hệ số, đơn vị, điều kiện và ví dụ tính theo nguồn |
| F003 | Hệ số và đơn vị chưa rõ | Ánh xạ ký hiệu sang đại lượng, phân tích đơn vị và căn cứ nguồn |
| F004 | Bảng 3 nêu 3 loạt tăng + 3 loạt giảm; đoạn sau nói M1–M4, thêm M5–M6 khi cần tái lặp | Xác nhận số loạt cho từng tình huống và cách lấy trung bình; xem [XML](../source-review/F004.xml) |
| F011–F015 | Các thành phần hồi quy chưa đối chiếu đủ; riêng F014 chưa thấy số mũ bình phương | Kiểm tra trực tiếp ký hiệu, chỉ số, mẫu số và bậc tự do trên DOCX; nêu căn cứ nếu nguồn cần đính chính |
| F040, F044 | `max` với một hiệu chưa rõ phạm vi | Xác định tập giá trị lấy max, trị tuyệt đối và chiều đo |
| F046 | Chỉ số và số chu kỳ chưa rõ | Ánh xạ từng số đo, số chu kỳ và điều kiện đủ dữ liệu |
| F049 | `u_c` xuất hiện cả hai vế, mâu thuẫn ký hiệu | Làm rõ từng thành phần và mô hình tổng hợp bằng căn cứ nguồn hoặc đính chính có thẩm quyền |

Cho mỗi ID, ghi riêng: người rà soát; ngày; phiên bản/hash DOCX; vị trí nguồn; biểu thức và biến đã xác nhận; đơn vị; điều kiện; ca đối chứng độc lập; kết luận **chấp nhận / cần sửa / không đủ căn cứ**; lý do. Với nhóm nhiều ID, không dùng một kết luận chung thay cho từng công thức.

Không thay ký hiệu nghi vấn bằng công thức quen thuộc khi chưa có căn cứ. Nếu chưa giải quyết được, tiếp tục giữ ngoài registry. F033 và F050 hiện nhận thành phần/`u_c` đã xác định riêng, nên việc chúng chạy được không giải quyết nghi vấn của F049.
