# Sửa ba lỗi sau review mã

Ngày: 2026-09-28. Phạm vi: ba finding trong lượt review gần nhất.

- Backend bỏ sàn sai số tuyệt đối 1e-9 khi kiểm tra ca đối chứng. Sai số tương đối vẫn là 1e-9 theo đáp án; đáp án 0 yêu cầu kết quả 0. Ca lệch 100 lần ở 1e-12 bị chặn phê duyệt, trạng thái giữ pending_review.
- Frontend dùng ánh xạ không có prototype cho số liệu tính và xác nhận điều kiện, kể cả sau cập nhật. Tên constructor không lấy thuộc tính kế thừa và không làm sập form.
- Trạng thái chưa lưu được truyền tới điều hướng ứng dụng. Chuyển tab, mở hội thoại, bắt đầu hội thoại mới, đổi/đóng nguồn phải xác nhận. Hủy giữ nội dung và trạng thái; unmount xóa cờ cảnh báo. Nút quay lại dùng chung cơ chế để tránh hỏi hai lần.

## Kiểm tra

- Backend registry: 50/50 pass (100% trong bộ kiểm thử này), gồm 5 ca mới về giá trị nhỏ, số 0 và đáp án làm tròn.
- Frontend: 55/55 pass (100% trong bộ kiểm thử này), gồm 8 ca mới về prototype và điều hướng.
- TypeScript typecheck, ESLint, Vite production build: pass.
- Ruff lint/format cho registry và test registry, git diff --check: pass.
- Chromium chạy ứng dụng thật với phản hồi công thức giả: constructor cho cả biến và điều kiện; hủy chuyển Hướng dẫn/hội thoại mới giữ sửa; xác nhận chuyển rồi mở lại có dữ liệu gốc; điều hướng sạch không hỏi; không có pageerror. Không gửi phê duyệt hay thay đổi registry nguồn thật.

Các số 100% trên là tỷ lệ pass của kiểm thử hồi quy, không phải điểm chất lượng độc lập hay kết quả holdout mới. Không sửa các kết quả audit lịch sử. Docker build/runtime chưa chạy vì môi trường không có Docker; các giới hạn nghiệp vụ đã ghi nhận vẫn giữ nguyên.
