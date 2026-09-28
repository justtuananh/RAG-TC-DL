# Registry v2 — 20 định nghĩa mới

Tăng catalog từ 6 lên 26 bộ tính. Các định nghĩa mới được đối chiếu kỹ thuật với Word Math gốc trong QTKĐ 1.190; xem `formula_lab/reports/registry-v2/source-review/REVIEW.md`. Chưa có phê duyệt chuyên gia đo lường và chưa tích hợp vào React/chatbot chính.

## Dùng demo

```bash
.venv-formula/bin/python -m uvicorn formula_lab.app:app --host 0.0.0.0 --port 8093
```

Mở `http://localhost:8093`. Chọn công thức mẫu hoặc hỏi rõ tài liệu/thiết bị, ví dụ:

- `DPI 610: hệ số góc hồi quy`
- `QTKĐ 1.190: độ phân giải tam giác`
- `DPI 610: độ không đảm bảo diện tích`
- `DPI 610: tổng hợp 10 thành phần`

Danh sách số đo: mỗi số một dòng hoặc ngăn bằng dấu `;`, dùng dấu chấm thập phân. Tất cả phần tử trong một trường dùng cùng đơn vị. Xác nhận điều kiện áp dụng trước khi tính. Câu hỏi chưa rõ nhánh hoặc khác quy trình sẽ yêu cầu làm rõ.

## Tái lập kiểm thử

```bash
.venv-formula/bin/python -m pytest formula_lab/tests tests/unit/llm tests/unit/ingestion/test_extract_docx.py -q
.venv-formula/bin/python -m formula_lab.v2.audit_corpus
.venv-formula/bin/python -m formula_lab.v2.benchmark --split dev
.venv-formula/bin/python -m formula_lab.v2.benchmark --split holdout
```

Sau khi đã xem lỗi của holdout và sửa mã, chạy lại bằng `--split holdout --regression`. Lượt này được lưu và báo cáo là hồi quy trên dữ liệu đã thấy, không phải holdout mới.

Hai lệnh benchmark cần server sẵn sàng. Chúng gọi HTTP và Chromium thật, không mock prepare, retrieval hay calculate. Retrieval dùng embedding OpenRouter + BM25 và Qdrant local; công thức/đáp án không do chat LLM sinh. Khóa đọc từ cấu hình ngoài Git đã có. Không chạy đồng thời một tiến trình index khác trên cùng thư mục Qdrant.

UC: `formula_lab/data/v2/{dev,holdout}-ucs.json`, mỗi tập 200 bộ số/20 câu hỏi khác nhau theo 20 định nghĩa. Oracle không import engine/registry; dùng math chuẩn, đáp án neo viết riêng, và thuật toán raw-moment cho hệ số góc so với centered covariance ở runtime. Sai số cho phép `max(1e-9, |gold|*1e-11)`. Holdout là số liệu/cách hỏi khác trong cùng 20 định nghĩa, không phải bộ công thức hoặc tài liệu độc lập mới; cùng một tác giả xây dựng bộ thử, chưa phải đánh giá mù bên ngoài.

Mỗi lượt được lưu vào thư mục timestamp; không ghi đè lượt có lỗi. Báo riêng tìm đúng công thức, trả đúng số, từ chối nhầm, kết quả sai không bị chặn, lỗi hạ tầng và UI. Bản corpus 30 file vẫn chỉ có 7 nguồn độc lập.

## Duy trì phê duyệt kỹ thuật

`catalog.py` là bản chép tay cấu trúc, biến, miền giá trị và điều kiện. `review_approvals.json` pin fingerprint nguồn/định nghĩa. Builder từ chối nguồn hay định nghĩa thay đổi, không tự duyệt lại. Khi sửa định nghĩa phải đối chiếu nguồn và cập nhật hồ sơ kỹ thuật có chủ đích trước khi build. Không dùng thay đổi approval để bỏ qua test sai.

Các công thức F004 (điều kiện số loạt đo), F014, F040, F044, F046, F049 còn nghi vấn không được tự động sửa hoặc ghép vào pipeline. F050 chỉ nhận u_c đã được xác định riêng; F033 nhận đúng 10 thành phần có dấu, không tự suy ra toàn bộ từ chứng nhận.
