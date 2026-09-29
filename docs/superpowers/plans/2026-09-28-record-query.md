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

- R1 (`42d6946`, `90df2a4`): sửa `vnnum` đọc `× 10-5` có khoảng trắng; bảng `record_field` + `measurement_point.cells` + `v_record_field`; `v_record_detail` lấy phạm vi đo của thiết bị (trước đây cả 20 biên bản hiện cùng khoảng "0,0015 đến 500 MPa" ghép từ ba dữ kiện QTKĐ).
  Chạy migration 012 trên Postgres local (sao lưu trước ở scratchpad) và `records.backfill`: 20 biên bản, mỗi biên bản 21 trường, 700 dòng có `cells`, không trường nào bị bỏ.
- R2 + R3 (`241ae42`): `record_lookup`, `records_summary`, danh mục trường, định tuyến tất định sau LLM.
  Phát hiện thêm: prompt phân loại ~4 000 token trong khi `num_ctx` 4096, không còn chỗ cho câu trả lời; nâng lên 8192 (bằng `generation.NUM_CTX` và `OLLAMA_CONTEXT_LENGTH` của container).
- Review (`a7c6c2b`): cực trị chỉ so trong một QTKĐ; số hiệu toàn chữ số cần chữ "số hiệu" hoặc từ chỉ thiết bị đứng trước; "áp kế"/"thiết bị" không còn mở nhánh số liệu từ `text`; lỗi DB của danh mục được ghi log.
- R4: `make record-eval` 34/34 (20 câu gốc + 14 câu diễn đạt khác), `intent_eval --live` 102/102, `make check` xanh (1591 test).
  E2E trên giao diện React (:5173) với API mới: câu 15 và câu 9 ra đúng bảng; cột được hỏi đưa lên đầu bảng.

Còn mở:

- Ngăn xuất xứ của tab chat đòi đăng nhập (`/api/data/provenance` cần token); đã kiểm xuất xứ ở backend, chưa bấm được trên giao diện khi chưa đăng nhập.
- 20 biên bản chưa được đưa vào Qdrant; câu hỏi rơi về nhánh văn bản vẫn không tìm được nội dung biên bản.
- `records_summary` đọc toàn bộ hồ sơ khớp bộ lọc vào Python rồi mới cắt 50 dòng; cần đẩy `COUNT`/`LIMIT` xuống SQL khi sổ cái lên hàng nghìn hồ sơ.

## Nhật ký G1 - bộ câu hỏi sinh tự động (2026-09-29)

- DeepSeek V4.1 Flash (opencode) sinh 60 câu mới vào `eval/record_query_generated.jsonl`, đáp án lấy nguyên văn từ view đã duyệt, chạy eval hai lần: 59/60 cả hai lần.
- Lỗi được báo: lọc theo đơn vị sử dụng ("Các biên bản kiểm định cho Công ty TNHH Khí công nghiệp Đông Phương") bị LLM đưa sang `lab_standard_lookup`, rơi về text.
- Kiểm chứng lại báo cáo tìm thêm: gen-40 "đạt" chỉ vì bảng liệt kê cả sổ cái (thước đo không kiểm "không thừa"); "biên bản nào không đạt" trả cả 20 biên bản; "liệt kê các biên bản không đạt" rơi về text; bảng `records_by_period` thiếu cột số biên bản.
- Sửa: `disambiguate_records` nhận đơn vị sử dụng (đủ tên hoặc phần đuôi riêng, bỏ qua đuôi chỉ gồm từ chung) và kết luận làm tiêu chí chọn (trừ khi câu đếm nhiều thứ); giữ `records_by_period` có khoảng ngày và bổ sung kết luận LLM bỏ sót; prompt nêu `owner_org`, `reviewer`; eval có `must_not` và `intents`; nhãn `cert_no` thống nhất "Số biên bản" (đọc từ dòng "Số:" của mẫu biên bản).
- Sau khi khởi động lại Ollama: LLM điền "mixed" vào ô intent (xác nhận xảy ra cả trên mã HEAD) và điền số QTKĐ "1.159" vào ô số biên bản; sửa tất định bằng luật suy intent theo quy tắc 8 và validator từ chối số QTKĐ ở `cert_no`.
- Review độc lập: câu "Có bao nhiêu biên bản không đạt?" mất bộ lọc kết luận; đã sửa kèm test.
- Kết quả: `record-eval` 40/40 + 60/60 (hai lần chạy), `intent_eval --live` 102/102, `make check` 1613 passed.
