# Tiêu chí đánh giá chất lượng và khả năng — phiên bản 1 (lịch sử)

> Bộ trọng số này đã được audit là có bias; không dùng ngưỡng96% để nghiệm thu khách quan. Giữ nguyên để truy vết; xem [audit](../build/formula-review/BIAS_AUDIT.md). Các test sửa lỗi là hồi quy, không phải holdout.

Phạm vi: ứng dụng chính React + API đăng ký nháp từ DOCX, người dùng phê duyệt và nhập số liệu tính. Chốt tiêu chí trước khi agent đánh giá độc lập chạy. Không dùng tỷ lệ test cũ làm bằng chứng duy nhất.

Kết quả từng mục: **Đạt / Đạt một phần / Chưa đạt / Chưa kiểm chứng**. Báo chính xác cách kiểm tra, bằng chứng, phạm vi mẫu và lỗi tìm thấy. Theo yêu cầu người dùng, chấm điểm chất lượng theo trọng số cố định bên dưới; báo riêng tỷ lệ ca test và độ phủ. Điểm chất lượng không tương đương độ phủ nghiệp vụ. Các mục trọng yếu C01–C09 phải đạt trước khi kết luận luồng chức năng đáp ứng; việc dùng nghiệp vụ còn cần duyệt chuyên môn và xác thực người dùng.

| Mã | Tiêu chí | Điều kiện đánh giá |
|---|---|---|
| C01 | Ingestion tạo nháp | DOCX mới tự có nháp trước embedding; không tự phê duyệt; lỗi embedding không làm mất nháp |
| C02 | FE và API khớp | Có API thật cho list/generate/detail/edit/approve/reject/calculate; thử luồng từ FE, không chỉ mock |
| C03 | Quyết định phê duyệt | Thiếu định nghĩa, đơn vị, điều kiện, ca đối chứng hoặc xác nhận phải bị chặn ở BE; từ chối lưu người/nhận xét |
| C04 | Chặn tính chưa duyệt | Pending/rejected/stale và giả mạo trạng thái không được tính, kể cả gọi API trực tiếp |
| C05 | Phiên bản và cạnh tranh | Revision cũ bị 409; chỉnh sửa thu hồi phê duyệt; không ghi đè âm thầm khi hai người thao tác |
| C06 | Ràng buộc nguồn | Có file/hash/định vị/ngữ cảnh; đổi hoặc xóa nguồn chặn tính; tạo lại cùng nguồn không mất quyết định |
| C07 | Độ đúng phép tính | Tạo ca độc lập mới, tự xác định đáp án trước khi chạy; có scalar, series, đổi đơn vị, số âm/0/biên và miền không hợp lệ; báo số ca trả đúng và chặn đúng riêng |
| C08 | Biểu thức và đầu vào | Chặn mã thực thi, biểu thức ngoài tập hỗ trợ, số không hữu hạn, đơn vị sai, thiếu biến/điều kiện; không trả kết quả cũ khi đầu vào đổi |
| C09 | Lưu trữ và truy vết | Khởi tạo lại Registry còn quyết định; lịch sử ghi sửa/duyệt; tính gắn phiên bản/hash; đường dẫn nguồn nội bộ dùng được khi đổi root |
| C10 | Chất lượng trải nghiệm | Làm được chọn nháp → đối chiếu → sửa → lưu → duyệt → tính; lỗi dễ hiểu; không âm thầm mất bản sửa; loading/empty/error có xử lý |
| C11 | Đồng bộ thiết kế | Đối chiếu trực quan với màn hình hiện có: font, palette, nút, field, card, spacing; kiểm tra desktop và viewport nhỏ, không tràn ngang toàn trang |
| C12 | Khả năng tiếp cận cơ bản | Nhãn input, thao tác bàn phím/focus, trạng thái không chỉ dựa vào màu; nêu rõ chưa phải audit WCAG đầy đủ |
| C13 | Độ phủ bảy nguồn | Đếm trạng thái trên bảy DOCX; phân biệt ứng viên/trích xuất lỗi/bộ tính được duyệt; không gọi số nháp là độ chính xác hoặc độ phủ thực thi |
| C14 | Giới hạn khai thác | Kiểm chứng/nêu rõ PDF, OLE lỗi, công thức phức tạp, quy tắc lời văn và gợi ý template; không suy diễn đã tự hiểu mọi công thức |
| C15 | Chất lượng triển khai | Test liên quan, TypeScript, lint và build qua; rà Docker mounts/import; phân biệt kiểm tra config và thực sự chạy container |
| C16 | Sẵn sàng nghiệp vụ | Có hay chưa chuyên gia duyệt nguồn thật, tập đánh giá nghiệp vụ độc lập, xác thực/phân quyền người duyệt; không lấy tên tự nhập làm danh tính xác thực |
| C17 | Tích hợp hội thoại | Xác định chat chỉ hướng dẫn mở form hay tự chọn đúng ID đã duyệt; đánh giá theo khả năng thực tế, không tuyên bố vượt quá |

## Quy tắc cho người/agent đánh giá

- Đọc mã, tự chạy kiểm tra và tự xây mẫu mới; dùng báo cáo nhà phát triển như đầu mối, không làm kết luận thay kiểm tra.
- Dùng DB/DOCX tạm; không phê duyệt bảy tài liệu thật. Không sửa mã triển khai trong lúc đánh giá; lưu phát hiện, mức độ và cách tái hiện.
- Ghi hash snapshot của file BE/FE đã đánh giá; nếu tác giả sửa lỗi sau đó, ghi kết quả ban đầu và kiểm tra lại riêng.
- Báo cáo độc lập lưu `build/formula-review/INDEPENDENT_REVIEW.md`, dữ liệu ca và log bằng chứng trong cùng thư mục con `independent/`.
- Agent độc lập về lượt đánh giá và ca thử, không phải chuyên gia đo lường hay bên chứng nhận ngoài dự án. Các tiêu chí không có bằng chứng phải ghi chưa kiểm chứng.

## Thang điểm cố định và vòng phản hồi

- C01–C09: mỗi mục 7 điểm (63 điểm), đều trọng yếu.
- C10–C15: mỗi mục 5 điểm (30 điểm).
- C16: 4 điểm; C17: 3 điểm. Tổng 100 điểm.
- Đạt = 100% trọng số; đạt một phần = 50%; chưa đạt hoặc chưa kiểm chứng = 0%. Phải giải thích bằng chứng cho mức đạt một phần.
- Mục tiêu nghiệm thu vòng này: **điểm >95/100 và toàn bộ C01–C09 đạt**. Báo riêng số ca trả đúng/tổng, chặn đúng/tổng, FE test đạt/tổng. Không dùng số lượng test để pha loãng lỗi.
- Khi điểm ≤95 hoặc còn lỗi trọng yếu: agent báo phát hiện cho dev, dev sửa, agent kiểm tra lại và ghi điểm vòng tiếp theo. Không thay tiêu chí/trọng số sau khi thấy kết quả. Lỗi phụ thuộc chuyên gia hoặc quyền hệ thống phải ghi rõ; không tự phê duyệt nguồn thật để tăng điểm.
- C16 đánh giá mức sẵn sàng nghiệp vụ đầy đủ; thiếu xác thực và duyệt chuyên gia không được chấm đạt chỉ vì đã ghi giới hạn. Điểm >95 cho triển khai không đồng nghĩa đã đủ điều kiện sử dụng nghiệp vụ.
