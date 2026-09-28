# Đăng ký nháp, phê duyệt và tính công thức

Luồng trong ứng dụng chính: **Tài liệu → chọn tài liệu → Công thức và phê duyệt**.

1. Ingestion DOCX trích công thức, vị trí và ngữ cảnh; lưu bản nháp trước bước embedding. Tài liệu lỗi embedding vẫn mở được phần rà soát.
2. Người rà soát đối chiếu nguồn, sửa biểu thức, ý nghĩa biến, đơn vị, miền giá trị, điều kiện và thêm ít nhất một ca có đáp án đối chứng.
3. Lưu bản nháp, nhập tên và căn cứ quyết định, xác nhận đã đối chiếu rồi phê duyệt; có thể từ chối nếu chưa đủ căn cứ.
4. Công thức đã duyệt có form nhập số liệu/đơn vị và xác nhận điều kiện. Backend kiểm tra rồi tính bằng bộ máy số học giới hạn, trả giá trị, đơn vị, phiên bản và nguồn.
5. Sửa định nghĩa đã duyệt làm trở lại chờ duyệt; đổi hoặc xóa nguồn chặn tính. Xung đột phiên bản trả HTTP 409 để người dùng tải lại.

## API dùng chung với React

Router `formula_registry/api.py` được gắn vào `api_server.py`. Hợp đồng máy đọc được tại `/openapi.json`, giao diện tại `/docs` của API chính.

| Method | Đường dẫn (prefix `/api`) | Nội dung |
|---|---|---|
| GET | `/documents/{document_id}/formula-drafts` | Danh sách `drafts` và `units` |
| POST | `/documents/{document_id}/formula-drafts/generate` | Tạo bổ sung từ DOCX hiện có, không cần embedding |
| GET | `/formula-drafts/{id}` | Chi tiết và lỗi kiểm tra |
| PUT | `/formula-drafts/{id}` | `{revision, proposal}` |
| POST | `/formula-drafts/{id}/approve` | `{revision, reviewer, note, confirmed: true}` |
| POST | `/formula-drafts/{id}/reject` | `{revision, reviewer, note, confirmed: false}` |
| POST | `/formula-drafts/{id}/calculate` | `{revision, inputs, confirmations}` |

`proposal` gồm đúng `title`, `expression`, `unit`, `variables`, `conditions`, `test_cases`. Ví dụ một đầu vào: `"a": {"value": "2", "unit": "kPa"}`; chuỗi số đo dùng mảng chuỗi ở `value`. `confirmations` là ánh xạ mã điều kiện sang boolean. `revision` phải là số nguyên của bản ghi vừa đọc. Không được gửi trực tiếp trạng thái/phê duyệt/nguồn để ghi đè. Nháp có thể thiếu nội dung ngữ nghĩa nhưng phải đúng cấu trúc kiểu dữ liệu; sai cấu trúc trả 422 và giữ nguyên bản đã lưu. FE cũng kiểm cấu trúc phản hồi để báo lỗi thay vì trắng trang khi gặp bản ghi hỏng cũ.

Lỗi: 404 không tìm thấy; 409 sai phiên bản, nguồn hết hiệu lực hoặc chưa được phép tính; 422 dữ liệu/biểu thức/đơn vị/quyết định không hợp lệ. Chỉ phê duyệt khi bộ kiểm tra định nghĩa và ca đối chứng đều qua; phép thử tự động không thay thế việc đối chiếu chuyên môn.

## Phạm vi và giới hạn

- Tự gợi ý cú pháp cho biểu thức đơn giản; chưa tự hiểu ý nghĩa vật lý và đơn vị. Biểu thức phức tạp hoặc trích xuất OLE thất bại được giữ nháp thiếu thông tin để rà soát.
- Định nghĩa có sẵn trong lab chỉ dùng làm gợi ý khi hash DOCX trùng. Không kế thừa phê duyệt; ca đối chứng vẫn phải được bổ sung. Quy tắc lời văn chỉ lấy từ các mẫu đã định vị, chưa khai thác tự động mọi đoạn văn.
- Đã tạo 334 ứng viên trên bảy DOCX, tất cả chờ duyệt. Trong đó 57 bản có gợi ý biểu thức và 277 bản chưa có biểu thức; 232 bản thiếu LaTeX trích xuất. Đây là số ứng viên (có cả trích xuất lỗi), không phải 334 công thức chạy được hoặc số công thức duy nhất. Registry lab 47 bộ tính là bản thử nghiệm riêng.
- PDF chưa hỗ trợ tạo nháp công thức có định vị. Chat chính hướng dẫn đến form; chưa tự ánh xạ công thức trong câu trả lời sang ID đã duyệt.
- Tên người duyệt hiện do người dùng nhập; ứng dụng chưa có xác thực danh tính/phân quyền người duyệt. Nhật ký ghi quyết định và phiên bản, không phải chữ ký số.

## Phát hiện từ lượt audit giữ riêng

- Bộ tính kiểm tra đơn vị đầu vào và chuyển đổi đơn vị, nhưng chưa phân tích thứ nguyên toàn biểu thức: khai báo phép cộng Pa với m vẫn có thể qua duyệt nếu ca đối chứng số học khớp. Người rà soát cần kiểm ý nghĩa vật lý, không dựa riêng vào validation tự động.
- Một ca hồi quy với offset lớn1e28 sai khác khoảng1.43e−11 so với đáp án2, vượt ngưỡng stress1e−24 khóa trước chạy. Chưa có SLA sai số trên toàn miền.
- Điểm96% cũ không dùng làm bằng chứng nghiệm thu khách quan. [Audit](../build/formula-review/BIAS_AUDIT.md) giữ cả lỗi hệ thống và lỗi harness, không sửa kết quả để đạt95%.

## Lưu trữ và chạy

SQLite mặc định `.formula-registry/registry.sqlite3`, có thể đổi bằng `FORMULA_REGISTRY_DB`. Thư mục này được bỏ qua bởi Git, cần sao lưu cùng tài liệu nguồn. Docker Compose mount thư mục để giữ dữ liệu qua lần tạo lại container. Nguồn trong repository lưu đường dẫn tương đối để dùng được khi đổi thư mục gốc; nguồn ngoài repository cần giữ nguyên đường dẫn.

```bash
# Tạo nháp cho tài liệu có sẵn, không phê duyệt
.venv-formula/bin/python -m formula_registry TC_DL/*.docx --report build/formula-review/backfill-summary.json
# API chính và React (hai terminal)
.venv-formula/bin/python -m uvicorn api_server:app --host 127.0.0.1 --port 8080
cd frontend && npm run dev -- --host 127.0.0.1
```

Gọi tạo lại cùng tài liệu/hash còn hiệu lực không ghi đè chỉnh sửa hoặc quyết định. Đổi hash tạo bản nháp mới và làm bản cũ hết hiệu lực. Nếu xóa rồi tải lại đúng nguồn cũ, tạo nháp mở một lượt rà soát mới: giữ nội dung đã sửa và lịch sử nhưng không khôi phục phê duyệt. Bộ đếm `created` gồm cả lượt nháp được mở lại này.

Bằng chứng kiểm thử trong `build/formula-review/`: báo cáo backfill, kiểm thử trình duyệt với DOCX và SQLite tạm, ảnh form tính. Các phê duyệt kiểm thử chỉ dùng dữ liệu giả, không duyệt thay người dùng trên bảy nguồn thật.

### Hồi quy sau review mã

Ca đối chứng dùng sai số tương đối `1e-9` theo đáp án, không dùng ngưỡng tuyệt đối chung cho mọi đơn vị; đáp án bằng 0 yêu cầu kết quả bằng 0. Chuyển màn hình, mở hội thoại hoặc rời tài liệu khi còn chỉnh sửa công thức phải xác nhận bỏ thay đổi. Tên biến/điều kiện hợp lệ như `constructor` được xử lý như khóa dữ liệu. Các kiểm thử hồi quy này không thay thế đánh giá độc lập.
