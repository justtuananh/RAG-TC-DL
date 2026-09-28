# Mở rộng trên bảy DOCX nguồn — 28/09/2026

Đã thêm **21 bộ tính**, nâng từ 26 lên **47**, có bộ tính cho cả bảy DOCX gốc. Trong phần mới có 15 định nghĩa từ phương trình và 6 quy tắc định lượng chép từ lời văn. Không tạo thêm DOCX tổng hợp trong đợt này; 23 biến thể cũ chỉ tiếp tục dùng kiểm thử nguồn/ingestion.

Các định nghĩa mới được đối chiếu kỹ thuật bởi trợ lý, chưa có duyệt chuyên gia đo lường. [Review phương pháp](PHUONG_PHAP.md) giải thích phần tự động và phần thủ công. [Catalog](CATALOG.md) có câu hỏi và số liệu mẫu cho từng bộ tính.

## Độ phủ theo nguồn

| QTKĐ | Tổng bộ tính | Trong đó quy tắc lời văn | Phương trình hỗ trợ / lần xuất hiện trong danh mục |
|---|---:|---:|---:|
| 1.061 | 3 | 2 | 1/1 |
| 1.062 | 3 | 3 | 0/0 — không có phương trình nhúng trong danh mục |
| 1.063 | 2 | 1 | 1/1 |
| 1.071 | 5 | 0 | 7/12 |
| 1.159 | 1 | 0 | 1/67 |
| 1.160 | 8 | 0 | 8/46 |
| 1.190 | 25 | 0 | 25/47 |
| **Tổng** | **47** | **6** | **43/174 ≈ 24,7%** |

Trước đợt này: 29/174 ≈16,7%. Tăng 14 lần xuất hiện được hỗ trợ; bộ tính sai số tuyệt đối mới của 1.071 tái sử dụng ba phương trình đã có trong bộ tính sai số tương đối, nên không tăng độ phủ phương trình. Sáu quy tắc lời văn không được cộng vào mẫu số phương trình. Số họ đại số độc lập có thể ít hơn số bộ tính.

## Thay đổi kỹ thuật

- Tách nguồn theo quy trình trước khi chọn alias hoặc ID. Cùng F008: 1.160 là hệ số góc, 1.190 là trung bình Y. Thiết bị và mã quy trình xung đột sẽ yêu cầu làm rõ.
- Nạp registry v3 riêng, giữ nguyên định nghĩa/phê duyệt v2. Manifest mới pin cả nội dung điều kiện. Builder kiểm tra toàn bộ trước khi ghi.
- Truy hồi các card đã đối chiếu trong phạm vi quy trình trên cả bảy nguồn. Không đưa DOCX tổng hợp vào index.
- Thêm miền trên mở `mu < 10 Pa` cho phép tính áp suất tuyệt đối ở 1.159, kiểm tra sau khi đổi đơn vị.
- Giao diện có bộ lọc theo DOCX, số bộ tính từng nguồn và nhãn phân biệt quy tắc từ lời văn.
- Các điều kiện còn nghi vấn như F040/F044/F049 của 1.190 vẫn chưa mở. Không nối các bộ tính riêng thành toàn bộ chuỗi độ không đảm bảo.

## Kiểm chứng thực hiện

| Hạng mục | Kết quả | Phạm vi |
|---|---:|---|
| Pytest toàn bộ lab và nhóm ingestion/LLM liên quan | 427/427 | 107 ca mới + 320 ca cũ; một cảnh báo Starlette/httpx deprecated |
| Chọn đúng công thức mới qua truy hồi thật | 21/21 | 21 câu hỏi công khai |
| Tính số HTTP mới | 42/42 | 21 đáp án neo + 21 bản đổi đơn vị tương đương |
| Trình duyệt mới | 21/21 | Lọc DOCX, chọn ví dụ, KaTeX, nhập số, tính và vô hiệu kết quả khi sửa |
| Thiếu điều kiện bị chặn qua HTTP | 21/21 | Mỗi định nghĩa mới một ca |
| Mơ hồ/chưa hỗ trợ qua HTTP | 7/7 | Không mở bộ tính trong các câu thử |
| Hồi quy v2 qua HTTP | 200/200 | Tập dev đã xem, 20 câu hỏi × 10 bộ số |
| Hồi quy v2 trên trình duyệt | 20/20 | Bộ chọn/truy hồi mới vẫn mở đúng card cũ |
| Chặn đầu vào lỗi v2 | 144/144 | Hồi quy các lỗi đã biết |
| Sáu bộ tính ban đầu qua HTTP | 6/6 | Câu hỏi → chuẩn bị → tính |
| Kiểm tra ingestion corpus cũ | 30/30 | 7 bản gốc + 23 biến thể |
| Ràng buộc nguồn trên corpus cũ | 238/238 | Catalog hiện tại |

Trong lượt live mới không quan sát kết quả số sai vẫn trả ra hoặc lỗi hạ tầng. Không diễn giải thành độ chính xác 100% ngoài bộ thử. Chưa có bộ đánh giá độc lập/mù; số liệu mới không phải kết quả holdout.

Artifacts:

- [Lượt HTTP/trình duyệt mới](live/20260928T071533222845Z/summary.json), request/response chi tiết tại `results.jsonl` cùng thư mục; có bảy ảnh giao diện đại diện bảy nguồn.
- [Hồi quy v2](../registry-v2/dev-regression/20260928T071728Z/summary.json). Câu thử âm “1.160: độ phân giải tam giác” đã được thay bằng 1.159 vì 1.160 nay được hỗ trợ; đây không phải lặp nguyên trạng toàn bộ benchmark lịch sử.
- [Sáu bộ tính ban đầu](legacy-http.json).
- [Audit corpus và độ phủ từng nguồn](corpus-audit.json).
- [Hồ sơ nguồn và ảnh OLE đã đối chiếu](source-review/REVIEW.md).

## Giới hạn còn lại

Còn 131/174 lần xuất hiện phương trình chưa được hỗ trợ. 1.159 mới có một bộ tính; chưa chuyển đổi và đối chiếu toàn bộ OLE. Tập thử mới nhỏ, câu hỏi gần tên công thức, chưa đánh giá rộng cách nói tự nhiên hoặc nhiều lượt. Có đúng nguồn không đồng nghĩa đúng chuyên môn; hash chỉ phát hiện thay đổi. Chưa tích hợp React/chatbot chính hoặc triển khai nghiệp vụ.
