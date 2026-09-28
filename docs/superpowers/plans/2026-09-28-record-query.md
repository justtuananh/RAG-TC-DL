# Tra cứu biên bản có cấu trúc (Bo_20_cau)

Ngày: 2026-09-28.

## Vấn đề

Bộ 20 câu hỏi trích xuất số liệu áp kế pít tông (`Bo_20_cau.xlsx`) chỉ đi đúng 2/20 câu với qwen2.5:3b.
Nguyên nhân gốc không nằm ở model mà ở bốn chỗ:

1. Thiếu intent: 12 câu hỏi một trường của MỘT biên bản cụ thể, 5 câu cần tổng hợp trên sổ cái; 11 intent hiện có không phủ.
2. Sổ cái bỏ mất trường: bộ đọc đã tách đủ trường đầu mục (phạm vi đo, cấp chính xác, phương tiện kiểm định, A0, uCmax...) nhưng `records/store.py` chỉ ghi vài cột, phần còn lại chỉ nằm trong `source_text`.
3. `v_record_detail` lấy phạm vi đo của QTKĐ (không phải của thiết bị) và `MAX()` trộn cận dưới/cận trên của ba dữ kiện khác nhau.
4. Tham số không được kiểm với dữ liệu thật (số hiệu "biên bản", số QTKĐ "011/2024", loại thiết bị "pít tông" không khớp "píttông").

Thử text-to-SQL với qwen2.5:3b: 11/20 SQL lỗi, 2 câu ra số sai trông như đúng; loại bỏ.

## Hướng làm

LLM chỉ chọn intent và điền JSON có cấu trúc; code dịch sang SQL tham số hóa trên view đã duyệt.
Không có text-to-SQL.

### R1 - Dữ liệu

- Sửa `vnnum` đọc ký hiệu khoa học có khoảng trắng trước dấu nhân (`0,59878 × 10-5`).
- Bảng `record_field`: mọi trường đầu mục của biên bản, nguyên văn + trích dẫn + giá trị số phân tích từ chính chuỗi đó (SI) + đơn vị.
- Cột `measurement_point.cells`: nguyên văn từng ô của dòng kèm tên cột lấy từ chính biên bản (từng lượt đo, áp suất khí quyển...).
- View `v_record_field`; `v_record_detail` lấy phạm vi đo/cấp chính xác của CHÍNH thiết bị, chỉ rơi về một dữ kiện QTKĐ duy nhất khi biên bản không ghi.
- Bộ đọc Excel lấy thêm dòng nhãn tự do ngoài Phụ lục A (`U(p) =`, `Δ(p) =`).
- Lệnh bổ sung ngược cho biên bản đã duyệt: đọc lại tệp, chỉ ghi trường có trích dẫn nằm trong nguyên văn đã duyệt (giữ P3, không phải duyệt lại).

### R2 - Truy vấn

- `record_lookup`: lọc theo số hiệu / số biên bản / ngày / ký hiệu, trả các trường được hỏi hoặc cả phiếu, kèm xuất xứ từng ô.
- `records_summary`: đếm / liệt kê / cực trị trên sổ cái, lọc theo kiểm định viên, người kiểm soát, đơn vị sử dụng, kết luận, đơn vị phạm vi đo, khoảng ngày.
- Danh mục trường sinh từ nhãn Phụ lục A đã duyệt + bí danh ký hiệu (A0, uCmax, U(p)); nhận diện trường từ câu hỏi là tất định.
- Cực trị sắp theo giá trị quy đổi SI nhưng luôn hiển thị nguyên văn (P2).

### R3 - Định tuyến

- Thêm hai intent vào prompt phân loại kèm quy tắc và ví dụ.
- Lớp định tuyến tất định sau LLM: số hiệu/số biên bản khớp sổ cái + trường được hỏi thì `record_lookup`; tên người có trong sổ cái, từ cực trị, "toàn bộ hồ sơ", lọc đơn vị thì `records_summary`.
- Kiểm tham số: số hiệu phải có trong sổ cái, số QTKĐ đúng dạng, loại thiết bị so theo slug liền.

### R4 - Kiểm chứng

- `eval/record_query_set.jsonl` (20 câu) + `eval/record_query_eval.py --live`: intent đúng và bảng trả về chứa đủ "Số liệu bắt buộc phải khớp"; mục tiêu ≥ 18/20.
- Unit test cho từng lớp; `make check` xanh.

## Nhật ký

(điền khi xong từng phần)
