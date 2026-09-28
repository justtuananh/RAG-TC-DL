# Quy trình chuẩn bị đánh giá độc lập

Trạng thái ngày 28/09/2026: **chưa có tập độc lập mới, chưa chạy đánh giá**. Đây là kế hoạch và biểu mẫu bàn giao. [BASELINE.json](BASELINE.json) ghi hash tham chiếu để rà soát, chưa phải biên bản đóng băng một lượt đánh giá.

## Phân công và tính độc lập

- Người biên soạn: người không xây registry hoặc bộ UC cũ; ghi tên và vai trò trước khi bắt đầu.
- Người kiểm tra đáp án: chuyên gia đối chiếu DOCX, đơn vị và điều kiện; tính riêng bằng tay hoặc công cụ độc lập, lưu bước tính.
- Người vận hành: chạy phiên bản đã đóng băng, giữ nguyên đầu ra và lỗi.
- Người phát triển: chỉ nhận đề và đáp án sau lượt đánh giá đầu đã được lưu. Không dùng `gold.py`, engine hoặc kết quả runtime làm đáp án.

Người biên soạn nhận DOCX gốc, phạm vi nghiệp vụ và hợp đồng API cần thiết; tránh lấy aliases, câu hỏi trong UC cũ hoặc đáp án do hệ thống tạo làm mẫu. Phiếu rà soát biểu thức dành cho chuyên gia; không dùng biểu thức runtime làm nguồn duy nhất cho đáp án. Nếu không thể tách người, công bố giới hạn và gọi kết quả là đánh giá nội bộ.

## Ma trận đề xuất để người đánh giá chốt trước khi chạy

| Nhóm | Quy mô đề xuất | Yêu cầu |
|---|---:|---|
| Công thức đã hỗ trợ | 60 câu hỏi × 3 bộ số = 180 ca | 3 cách diễn đạt mới cho mỗi định nghĩa trong 20 định nghĩa; số thông thường, biên hợp lệ và đổi đơn vị |
| Dữ liệu hoặc điều kiện không hợp lệ | 40 ca | Bao phủ mẫu số 0, đơn vị sai, thiếu điều kiện, danh sách sai cặp/số lượng và giới hạn chênh cao |
| Mơ hồ, sai quy trình, chưa hỗ trợ | 30 câu hỏi | Ghi rõ phải làm rõ hay phải chặn; không gộp hai kỳ vọng nếu nghiệp vụ phân biệt được |
| Sáu bộ tính cũ | 12 ca | 2 câu hỏi mới/bộ tính; báo thành nhóm riêng |

Đây là kích thước đề xuất, chưa phải số ca đã được tạo. Báo số câu hỏi độc lập và số bộ số riêng. Tài liệu ngoài bảy nguồn gốc, hội thoại nhiều lượt và toàn bộ chuỗi độ không đảm bảo nằm ngoài kết luận của đợt này trừ khi bổ sung nhóm riêng trước khi đóng băng.

## Nội dung bắt buộc của mỗi ca

Lưu dưới dạng JSON/CSV do người biên soạn quản lý ngoài thư mục người phát triển đang đọc:

- `case_id`, nhóm, người biên soạn, ngày và mã câu hỏi gốc (để nhận biết các bộ số cùng câu hỏi).
- Câu hỏi nguyên văn; tài liệu/hash, vị trí công thức và ID kỳ vọng nếu xác định được.
- Đầu vào, đơn vị, thứ tự danh sách và điều kiện xác nhận cụ thể.
- Kỳ vọng: mở đúng bộ tính / yêu cầu làm rõ / chặn / từ chối dữ liệu.
- Với ca tính hợp lệ: kết quả dạng chuỗi thập phân, đơn vị, dung sai tuyệt đối và tương đối có căn cứ.
- Bước tính độc lập, nguồn tham chiếu, người kiểm tra đáp án và ngày kiểm tra.
- Với ca từ chối: lý do nghiệp vụ cụ thể. Không để trống đáp án rồi dùng kết quả hệ thống điền lại.

## Đóng băng và chạy

1. Chốt phạm vi và tiêu chí trước khi mở đề; giải quyết các phiếu chuyên gia liên quan hoặc ghi rõ đây vẫn là thử nghiệm kỹ thuật.
2. Người giữ đề lưu bản đề/đáp án bất biến và SHA-256, thời điểm đóng băng, tên người giữ. Không đưa đáp án bí mật vào cùng workspace với tác giả sửa mã.
3. Ghi commit, thay đổi chưa commit, hash nguồn/registry/mã, phiên bản Python và thư viện, cấu hình không chứa khóa, embedding model, corpus/index truy hồi và trình duyệt. Có thể dùng baseline hiện tại làm tham chiếu nhưng phải cập nhật snapshot cho lượt thực tế.
4. Kiểm tra server và dịch vụ trước khi chạy. Lưu request/response, lỗi hạ tầng, thời điểm, hash phiên bản và kết quả so sánh từng ca. Không loại ca lỗi khỏi mẫu số âm thầm.
5. Chạy câu hỏi qua retrieval → prepare → calculate và chọn ca kiểm tra trình duyệt theo danh sách chốt trước. Không bỏ qua prepare để chỉ kiểm engine. Kiểm tra nguồn bị sửa phải ở bản sao cô lập.
6. Lưu lượt đầu trước khi mở lỗi cho người phát triển. Sau khi sửa, mọi lần chạy lại tập này đều là hồi quy; cần tập mới để có đánh giá mù mới.

Benchmark hiện tại chỉ đọc `dev`/`holdout` cũ và có giả định 10 bộ số/câu hỏi; **không đưa tập mới vào hai file cũ hoặc dùng lệnh hiện tại để tuyên bố đánh giá độc lập**. Khi có hợp đồng dữ liệu do người đánh giá chốt, cần bổ sung runner đọc tập ngoài, giữ hash, nhóm câu hỏi và kỳ vọng của từng ca; kiểm thử runner bằng tập giả công khai trước khi mở đề thật.

## Báo cáo kết quả và điều kiện kết thúc

| Chỉ số | Cách báo |
|---|---|
| Chọn đúng công thức | Số câu hỏi chọn đúng / tổng câu hỏi có công thức hỗ trợ; kèm số ca ảnh hưởng hạ tầng |
| Trả kết quả hữu ích | Ca đúng công thức + đúng số trong dung sai + đúng đơn vị + đúng nguồn / toàn bộ ca hợp lệ |
| Từ chối nhầm | Số ca hợp lệ bị chặn/làm rõ/từ chối dữ liệu, tách lỗi hạ tầng |
| Sai nhưng vẫn trả | Số ca trả số sai, sai công thức/nguồn/đơn vị hoặc trả số khi phải chặn; liệt kê từng ca |
| Chặn/làm rõ đúng | Báo riêng từng nhóm âm; không cộng vào tỷ lệ trả kết quả hữu ích |
| Hạ tầng và trình duyệt | Số ca không thực hiện được, lý do; số ca UI đạt / số ca UI đã lên kế hoạch |
| Độ phủ | Số công thức, nguồn độc lập và lần xuất hiện phương trình; không suy rộng từ số biến thể DOCX |

Hoàn tất bước đánh giá khi có đề đóng băng, xác nhận người biên soạn/kiểm đáp án, snapshot phiên bản, artifact lượt đầu và báo cáo đầy đủ. Chưa đặt ngưỡng chấp nhận nghiệp vụ thay cho chuyên gia; mọi kết quả sai không bị chặn phải được ghi và xử lý trước quyết định sử dụng.
