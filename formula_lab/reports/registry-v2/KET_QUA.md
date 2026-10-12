# Kết quả mở rộng registry: 20 công thức mới

Đã triển khai 20 định nghĩa mới, nâng từ **6 lên 26 bộ tính** trong formula lab. Chúng có nguồn DOCX, biến/đơn vị, điều kiện áp dụng, hồ sơ đối chiếu và form nhập liệu. Chưa tích hợp vào React/chatbot chính; demo là luồng tra cứu–chọn công thức–tính số riêng của lab.

**Tập giữ riêng lần đầu đạt 90% trả kết quả hữu ích. Sau khi xem và sửa lỗi, tập đó đạt 100% khi chạy hồi quy. Không coi lượt hồi quy là bằng chứng giữ riêng mới.** Không quan sát kết quả tính sai được trả ra trong các lượt hợp lệ này; điều đó không bảo đảm không còn lỗi thực tế.

## Các bước đã hoàn thành

1. Đối chiếu 20 định nghĩa cuối với XML Word Math và ngữ cảnh QTKĐ 1.190, pin SHA-256 DOCX và fingerprint định nghĩa. Đây là đối chiếu kỹ thuật bởi trợ lý, **chưa phải phê duyệt chuyên gia đo lường**.
2. Bổ sung sqrt, abs, max, mean, căn tổng bình phương và hệ số góc hồi quy theo danh sách số đo trong bộ tính Decimal giới hạn. Không chạy eval hay mã do mô hình sinh. Chuyển đổi đơn vị chiều dài, diện tích, khối lượng, nghịch đảo áp suất và đại lượng không thứ nguyên.
3. Thêm trường danh sách vào UI, giữ đơn vị theo trường, xác nhận điều kiện riêng cho từng nhánh, kiểm tra số phần tử, ghép cặp, mẫu số, miền giá trị, khôi phục dữ liệu và vô hiệu kết quả cũ khi sửa.
4. Tạo 200 UC phát triển + 200 UC giữ riêng, có 20 đáp án neo viết riêng. Oracle không đọc/evaluate biểu thức registry; dùng math chuẩn và công thức raw-moment cho hồi quy, khác cách tính centered covariance trong runtime. Sai số chấp nhận `max(1e-9, |gold|*1e-11)`.
5. Chạy HTTP và Chromium thật: câu hỏi → embedding OpenRouter + BM25/Qdrant → registry → form → tính → trả nguồn/hash. Không mock prepare/retrieval/calculate. Không dùng chat LLM để sinh công thức hoặc chấm điểm.

## Kết quả theo đúng phạm vi

| Chỉ số | Dev, catalog cuối | Giữ riêng lần đầu | Hồi quy sau sửa trên tập đã xem |
|---|---:|---:|---:|
| Tìm/chọn đúng công thức | 20/20 | 18/20 | 20/20 |
| Trả đúng kết quả trong luồng API | 200/200 | 180/200 | 200/200 |
| Trình duyệt đầu cuối | 20/20 | 18/20 | 20/20 |
| Chặn đầu vào lỗi | 144/144 | 132/132 | 144/144 |
| Chặn câu hỏi mơ hồ/chưa hỗ trợ | 12/12 | 12/12 | 12/12 |
| Chặn sửa công thức nguồn, kiểm tra riêng | 20/20 | 18/18 | 20/20 |
| Ca số hợp lệ bị từ chối nhầm | 0 | 20 | 0 |
| Kết quả số sai vẫn trả ra | 0 | 0 | 0 |
| Lỗi hạ tầng ảnh hưởng ca thử | 0 | 0 | 0 |

Mỗi tập có 20 câu hỏi, mỗi câu gắn 10 bộ số. 200 ca không phải 200 cách hỏi độc lập. Khi giữ riêng lần đầu không mở được hai form, các kiểm tra đầu vào/nguồn tương ứng không chạy; vì vậy mẫu số cột đó thấp hơn, không tính các ca chưa chạy là đạt.

Unit/regression: **320 tests passed** (`pytest formula_lab/tests tests/unit/llm tests/unit/ingestion/test_extract_docx.py -q`). Sáu bộ tính cũ còn có kiểm tra HTTP trực tiếp **6/6 đạt**.

## Độ phủ và kiểm tra lại 30 DOCX

- 26 calculator; khớp **29/174 lần xuất hiện phương trình = 16,7%**, tăng từ 9/174 = 5,2%. Đây là tỷ lệ occurrence, không phải tỷ lệ họ công thức độc lập hay độ chính xác tổng quát.
- 145 occurrence còn lại chưa có calculator được duyệt. Không tự biến chúng thành executable từ LaTeX.
- 30 DOCX vẫn là **7 nguồn gốc + 23 bản tổng hợp**. Đọc cấu trúc: 30/30; kiểm tra ràng buộc nguồn với catalog mở rộng: 156/156.
- 20 định nghĩa mới đều từ QTKĐ 1.190. F016/F017 cùng dạng U/k nhưng khác ý nghĩa/phạm vi; không tuyên bố 20 dạng đại số hoàn toàn độc lập.
- Index tìm kiếm cho demo dùng 7 bản trích xuất gốc + 20 đoạn công thức đã đối chiếu. 23 bản tổng hợp được dùng ở kiểm tra ingestion/source binding, **không đưa vào index tìm kiếm** để tránh bản sao làm tăng điểm truy hồi.

## Các vấn đề đã phát hiện và xử lý

- **Truy hồi đúng tài liệu nhưng thiếu đoạn công thức:** lượt dev ban đầu chỉ tìm đủ 15/20. Đã tìm kiếm trong tập đoạn công thức được duyệt khi câu hỏi chỉ rõ QTKĐ 1.190/DPI 610; vẫn kiểm tra đúng ID nguồn, không hạ điều kiện xuống chỉ khớp tên file.
- **Nhầm f0 với mã công thức F000:** giữ riêng lần đầu tìm đúng nguồn nhưng router hiểu nhầm ký hiệu f0. Đã chỉ nhận ID có ba chữ số như F036; f0 giữ nghĩa đại lượng.
- **Nhầm đầu vào với mục tiêu:** câu “tính độ không đảm bảo do độ lệch điểm không từ f0” có cả tên đại lượng đích và tên đầu vào. Đã đối chiếu schema biến cho các nhắc đến sau “từ/với”. Hai yêu cầu riêng như “tính f0 và u_f0” vẫn được yêu cầu làm rõ.
- **Sai hiển thị khi chuyển OMML:** dấu trung bình U+0305 bị đổi thành hat, và ngoặc nhọn chưa escape đúng cho LaTeX. Đã sửa, có regression và kiểm tra render KaTeX thật.
- **Không thống nhất số loạt đo:** khi đọc toàn mục 5.3.2, Bảng 3 và đoạn mô tả M1–M4/M5–M6 không thống nhất. Đưa F004 về chờ kiểm tra điều kiện, thay bằng F037 có mẫu số 2*sqrt(3) rõ trong XML. Đổi catalog/UC trước khi chạy giữ riêng; bản trước đó được lưu nguyên trong `data/v2/pre-procedure-review`.
- **Lỗi chạy benchmark trước khi server sẵn sàng:** một lượt dev gặp lỗi kết nối nhưng harness cũ đếm nhầm là từ chối. Lượt này bị loại khỏi đánh giá, giữ artifact và `INVALID_RUN.md`; đã thêm health check và phân loại riêng lỗi hạ tầng.

## Giới hạn và bước tiếp theo

Kết quả 100% sau sửa là regression trên tập đã xem. Chưa có đánh giá mù bởi người khác, công thức mới ngoài catalog, 30 tài liệu thật độc lập, hay chứng nhận chuyên môn. Holdout dùng cách hỏi/số khác trong cùng 20 định nghĩa và do cùng tác giả xây dựng. Bộ chọn còn dựa vào từ khóa/schema; cách hỏi mới, viết tắt, hội thoại nhiều lượt có thể bị từ chối. Giá trị nhập nhầm nhưng vẫn hợp lệ theo đơn vị/miền có thể không bị phát hiện.

Các biểu thức còn thiếu hoặc mâu thuẫn như F014, F040/F044, F046, F049 vẫn không được tự sửa để chạy. F050 yêu cầu nhập u_c đã xác định riêng; chưa tự động tính toàn bộ chuỗi độ không đảm bảo từ chứng nhận. OLE/MathType chưa được chuyển đổi lại trong đợt này.

Bước tiếp theo có giá trị nhất là chuyên gia kiểm tra 20 định nghĩa và các điều kiện đã ghi, rồi tạo bộ câu hỏi/công thức mới do người khác soạn trước khi tích hợp vào chatbot chính. Giữ nguyên kết quả giữ riêng lần đầu 90% làm bằng chứng độc lập với các sửa phát sinh sau đó.

## Demo và bằng chứng

Demo chạy tại `http://localhost:8093`. Ví dụ: `DPI 610: hệ số góc hồi quy`, `QTKĐ 1.190: độ phân giải tam giác`, `DPI 610: u_f0 với f0`. Danh sách nhập mỗi số một dòng hoặc ngăn bằng dấu `;`.

- [Catalog 20 công thức](CATALOG.md), [đối chiếu XML và điều kiện](source-review/REVIEW.md).
- [Dev cuối](dev/20260928T043015Z/summary.json), [giữ riêng lần đầu](holdout/20260928T043112Z/summary.json), [hồi quy sau sửa](holdout-regression/20260928T043339Z/summary.json). Từng UC, kết quả và ảnh UI ở cùng thư mục.
- [Kiểm tra 30 DOCX và độ phủ](corpus-audit.json), [sáu bộ tính cũ](legacy-live-smoke.json).
- [Freeze trước giữ riêng](HOLDOUT-FREEZE.json); mã router/harness tại thời điểm đó lưu trong `first-holdout-runtime`.
- [Hướng dẫn tái lập](../../v2/README.md).
