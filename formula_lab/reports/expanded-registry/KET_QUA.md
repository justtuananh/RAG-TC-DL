# Kiểm thử mở rộng registry — 30 DOCX

Registry hiện tại xử lý an toàn các tình huống đã kiểm tra sau khi sửa hai lỗi, nhưng **chưa đủ độ phủ để tính nhiều công thức trong toàn bộ tài liệu**. Không thể diễn giải kết quả đạt của các ca từ chối thành khả năng trả lời đầy đủ.

## Dữ liệu và cách thử

- 30 DOCX: 7 bản gốc nguyên byte + 23 bản tổng hợp dựa trên mẫu. Chỉ có **7 nguồn tài liệu độc lập**.
- 7 bản thay đổi bố cục; 7 bản mất đối tượng công thức; 7 bản chèn nội dung/công thức không đáng tin; 2 tuyển tập đưa toàn bộ OMML vào đoạn văn/bảng.
- 1.298 đối tượng công thức trong corpus 30 file, bao gồm ký hiệu đơn và nhiều bản sao. Không phải 1.298 công thức độc lập.
- Trong artifact của 7 tài liệu gốc: 174 lần xuất hiện phương trình có dấu `=`, 127 chuỗi LaTeX khác nhau sau chuẩn hóa khoảng trắng. Chưa khử tương đương toán học, chưa xác nhận tất cả đều đúng/đầy đủ.
- 6 calculator hiện hữu; khớp 9/174 lần xuất hiện phương trình. Đây là chỉ số độ phủ thô theo occurrence, không phải 9 công thức độc lập. **165/174 occurrence chưa có calculator được duyệt.**
- Kiểm tra trực tiếp parser DOCX, source guard, registry, bộ tính và Chromium. Không gọi OpenRouter, không xây index retrieval mới trên 30 DOCX; không phải phép đo chatbot đầu cuối cho bộ dữ liệu mới.
- OMML được đọc lại từ file DOCX. MathType/OLE chỉ được kiểm tra đối tượng; danh mục LaTeX OLE lấy từ artifact trích xuất sẵn. Chưa kiểm tra lại khả năng chuyển đổi OLE.

## Kết quả sau sửa

| Nhóm | Đạt/tổng | Ý nghĩa |
|---|---:|---|
| Cấu trúc ingestion | 30/30 | Bảo toàn OMML qua đổi bố cục/đưa vào bảng, nhận biết xóa/chèn đối tượng theo fixture |
| Ràng buộc tài liệu | 42/42 | Nguồn gốc đúng hash được dùng; tài liệu thay đổi/chưa duyệt bị chặn |
| Lookup công thức | 174/174 | 9 occurrence có định nghĩa được mở; 165 occurrence chưa đăng ký bị chặn; **không phải độ phủ 100%** |
| Tính số | 600/600 | Sáu calculator × 100 bộ số, có đổi đơn vị; oracle Decimal riêng, seed 20260928 |
| Đầu vào không hợp lệ | 96/96 | Thiếu/thừa biến, giá trị rỗng/sai kiểu, dấu phẩy, vô hạn, số lớn, sai đơn vị, biên miền, thiếu xác nhận |
| Định tuyến ngoài phạm vi | 12/12 | Không mở bộ tính khác quy trình khi câu hỏi chỉ rõ quy trình/thiết bị không phù hợp |
| UC cũ, ngoài UI | 100/100 | Số hợp lệ, lỗi đầu vào, biên, chọn công thức, lỗi nguồn |
| Giao diện Chromium | 20/20 | Form, kết quả, phiên bản, sửa dữ liệu, khôi phục, kết quả trả về muộn, gắn nguồn |
| Tổng kiểm tra benchmark | 1.074/1.074 | Bao gồm nhiều kiểm tra từ chối đúng, không dùng làm tỷ lệ trả lời hữu ích |

Bộ unit/regression bổ sung: **70 tests passed**, chạy `pytest formula_lab/tests tests/unit/llm -q`.

## Hai lỗi phát hiện và đã sửa

1. **Chọn nhầm quy trình.** Ví dụ hỏi “Công thức sai số tương đối theo QTKĐ 1.190 của DPI 610?” trước đây mở calculator H3000 thuộc QTKĐ 1.071. Sáu trong 12 ca ngoài phạm vi mở nhầm form. Đã thêm kiểm tra mã QTKĐ và tên thiết bị trước khi chọn calculator. Sau sửa 12/12 ca được từ chối/làm rõ đúng. Đây là chặn nhầm phạm vi đã nêu, chưa thay thế một bộ hiểu ngữ cảnh đầy đủ; tên viết tắt khác và hội thoại nhiều lượt vẫn cần nghiên cứu.
2. **Đơn vị sai kiểu gây exception.** Payload `"unit": {}` gây `TypeError`, có thể làm API trả 500. Đã kiểm tra kiểu chuỗi và trả lỗi dữ liệu `invalid`. Sáu ca lỗi kiểu trong benchmark đã hết lỗi. Regression kiểm tra thêm object/list/null/boolean/number qua API thật.

Kết quả trước sửa lưu trong [before-fixes](before-fixes/summary.json): 858/870 đạt, 12 ca lỗi thuộc hai nhóm trên. Sau đó bổ sung 204 ca ingestion/coverage; chỉ so sánh trước/sau trực tiếp trên các nhóm chung, không coi thay đổi mẫu số là cải thiện chất lượng.

## Lỗi/rủi ro còn lại

- **Trích xuất mất công thức:** heuristic đánh dấu ít nhất 12 occurrence cần xem lại trong QTKĐ 1.159. Ví dụ F056: `u_A =` thiếu vế phải; F076: phân số `U(t)/{}` thiếu mẫu số; F131: `delta = {}/p` thiếu tử số. Đây là lỗi/thiếu trong artifact trích xuất, chưa kết luận bản DOCX gốc sai. Heuristic không phát hiện hết lỗi, đặc biệt biểu thức lồng nhau và sai dấu.
- **Độ phủ thấp:** chỉ 6 bộ tính; các nhóm độ không đảm bảo, hồi quy, căn bậc hai, tổng chuỗi, lượng giác chưa được đăng ký. `sqrt`, `abs`, `max`, `sin` chưa được engine hỗ trợ.
- **Thay đổi bố cục cũng mất phê duyệt:** cả 7 bản đổi bố cục bị chặn vì hash toàn file thay đổi. Đúng chính sách hiện tại nhưng làm tăng công đối chiếu và giảm tính sẵn sàng. Cần quy trình duyệt phiên bản hoặc fingerprint theo công thức + ngữ cảnh, kèm kiểm tra không làm lỏng ràng buộc nguồn.
- **Dữ liệu sai nhưng hợp lệ về kiểu/miền:** ví dụ nhập nhầm áp suất 100000 thành 10000 Pa vẫn có thể cho kết quả. Chưa có biên theo thiết bị, đối chiếu nhiều lần đo hay cảnh báo bất thường đủ rộng.
- **Registry duyệt sai vẫn tính sai:** source hash chỉ phát hiện thay đổi so với bản đã duyệt. Nó không chứng minh nội dung nguồn hay biểu thức do người duyệt nhập là đúng. Cần đối chiếu biểu thức, ý nghĩa biến, đơn vị và ví dụ tính độc lập; công thức quan trọng nên có người duyệt thứ hai.
- **Trùng ký hiệu/nhánh điều kiện:** cùng `u_r` có nhánh chia căn 3/căn 6; cùng `u_c` có thể chỉ các đại lượng khác nhau. Phải gắn ID theo tài liệu–mục–phiên bản–điều kiện, không chỉ tên biến.
- Chưa đo retrieval/LLM đầu cuối trên 30 DOCX mới, chưa có 30 tài liệu thật độc lập, chưa có tập formula family mới đã được chuyên gia duyệt.

## Kết luận lựa chọn

Tiếp tục chọn registry cho tính toán cần độ tin cậy cao, với điều kiện **chỉ mở form cho công thức đã duyệt**. Bước mở rộng giá trị nhất là duyệt thêm công thức từ 1.160/1.190 và tạo oracle số riêng cho từng họ công thức, sau đó đo cả độ phủ và độ đúng. Không nên tự duyệt hàng loạt các LaTeX trích xuất hiện có để tăng số công thức hỗ trợ.

Đề xuất thứ tự mở rộng: `U/k`, `U=k*u_c`, hiệu chỉnh cột áp `rho*g*h`, hàm tuyến tính `a+b*x`, trung bình nhiều lần đo; tiếp đến căn tổng bình phương, độ phân giải và độ trễ; sau đó hồi quy/covariance và công thức áp suất nhiều hệ số. Đây là lộ trình đề xuất, **chưa được triển khai hoặc tính là đã kiểm thử tính số** trong đợt này.

## Artifact và tái lập

- [30 DOCX](../../expanded/corpus/) và [hướng dẫn chạy](../../expanded/README.md).
- [Manifest nguồn, lineage, SHA-256](corpus-manifest.json).
- [Danh mục toàn bộ 174 phương trình](FORMULAS.md).
- [Tổng hợp máy đọc được](summary.json), [từng UC và kết quả](results.json), [ảnh UI](ui.png).
- Mã trên nhánh `dev`. Report ghi commit nền và hash nội dung runtime đã chạy; các sửa mới chưa nằm trong commit nền đó.
