# Registry v3 — mở rộng trên bảy DOCX gốc

Bổ sung 21 bộ tính: 15 định nghĩa từ phương trình và 6 quy tắc định lượng từ lời văn. Tổng catalog là 47. Không tạo thêm DOCX tổng hợp trong đợt này. Mỗi tài liệu có ít nhất một bộ tính, nhưng chưa hỗ trợ toàn bộ công thức của tài liệu.

- [Kết quả và độ phủ](../reports/registry-v3/KET_QUA.md).
- [Bản chất phương pháp và giới hạn](../reports/registry-v3/PHUONG_PHAP.md).
- [Đối chiếu nguồn](../reports/registry-v3/source-review/REVIEW.md).
- [Danh mục mới và số liệu demo](../reports/registry-v3/CATALOG.md).

## Chạy và thử

Từ thư mục gốc repo, nếu chưa có tiến trình dùng cổng 8093:

```bash
.venv-formula/bin/python -m uvicorn formula_lab.app:app --host 127.0.0.1 --port 8093
```

Mở `http://localhost:8093`, dùng bộ lọc “Tài liệu nguồn”, chọn công thức mẫu, nhập số và xác nhận điều kiện. Có thể hỏi trực tiếp:

- `QTKĐ 1.061: giới hạn sai số van`
- `QTKĐ 1.062: mức áp suất bơm phụ`
- `QTKĐ 1.063: giới hạn độ tụt áp bình phân ly`
- `H3000: sai số tuyệt đối trung bình`
- `QTKĐ 1.159: áp suất tuyệt đối tại đáy`
- `QTKĐ 1.160: hệ số góc hồi quy`
- `DPI 610: độ lặp lại chiều tăng`

`Fxxx` là ID trích xuất theo từng DOCX, không nhất thiết là số phương trình in trên trang. `Pxxx` là ID lab cho quy tắc từ lời văn. Cùng `F008` ở 1.160 và 1.190 có ý nghĩa khác nhau. Câu hỏi phải chỉ rõ quy trình/thiết bị. UI chỉ lọc danh sách ví dụ, không tự thêm quy trình vào câu hỏi người dùng tự gõ.

## Kiểm chứng

```bash
.venv-formula/bin/python -m pytest formula_lab/tests tests/unit/llm tests/unit/ingestion/test_extract_docx.py -q
.venv-formula/bin/python -m formula_lab.v3.benchmark
```

Benchmark cần server đang chạy, khóa embedding ngoài Git và Chromium. Dùng HTTP/truy hồi/trình duyệt thật; kết quả ở `reports/registry-v3/live/<timestamp>`. 42 ca gồm 21 đáp án neo viết riêng, mỗi đáp án chạy thêm lần đổi đơn vị; đây là 21 câu hỏi, không phải 42 cách hỏi độc lập. Tất cả là dữ liệu phát triển công khai, không phải đánh giá mù. Sáu quy tắc từ lời văn không được cộng vào mẫu số 174 phương trình.

## Tái tạo catalog

```bash
.venv-formula/bin/python -m formula_lab.v3.catalog --draft
.venv-formula/bin/python -m formula_lab.v3.catalog
```

`--draft` chỉ in fingerprint; lệnh build không cập nhật `review_approvals.json`. Nguồn hoặc định nghĩa thay đổi sẽ bị chặn trước khi ghi. Manifest v3 pin cả nội dung điều kiện. Các định nghĩa mới chỉ được đối chiếu kỹ thuật, chưa có duyệt chuyên gia. Không lấy việc build/test thành công làm lý do tự thay approval.
