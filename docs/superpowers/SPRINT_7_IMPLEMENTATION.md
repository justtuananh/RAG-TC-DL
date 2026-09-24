# Sprint 7 — Nạp hồ sơ kiểm định và phiếu đo

## Đã triển khai

### Cơ sở dữ liệu (spec §5.5)

- `db/models.py`: `Device`, `CalibrationRecord`, `MeasurementPoint` + hằng số
  `RECORD_MODES`/`VERDICTS`, thêm `appendix_field` vào `FACT_KINDS`.
  - `device` khóa nhận dạng `(device_type_id, serial_norm)`; `serial_no` giữ
    nguyên văn, `serial_norm` để đối sánh; thiếu serial → `needs_identification=1`.
  - `calibration_record.extraction_id` là cầu nối P1/P3 (mọi hồ sơ đi qua
    `extraction` `pending`); `expires_from_fact_id` trỏ dữ kiện chu kỳ đã dùng.
  - `measurement_point` giữ `quote` + `*_text` nguyên văn từng ô; `error_value`
    luôn đọc từ tài liệu (P2); `within_limit` chỉ điền khi có cả error lẫn limit.
- `db/migrations/versions/006_create_records.py`: ba bảng + index + view đã duyệt.
- `db/views.py`: `RECORD_VIEWS` (`v_calibration_record`, `v_measurement_point`),
  `create_record_views`/`drop_record_views`/`create_all_approved_views`; tách khỏi
  `APPROVED_VIEWS` để migration 004 vẫn chạy trên CSDL sạch. `RAW_TABLES` thêm ba
  bảng hồ sơ để guard `query/` chặn truy cập bảng gốc.

### Phụ lục A → cấu hình đọc hồ sơ

- `knowledge/rules/phuluc_a.py`: luật `rule:phuluc_a.v1` rút trường đầu mục và
  bảng kết quả đo thành dữ kiện `appendix_field`. KHÔNG nằm trong `extract_all`
  (giống §6) nên không đổi số dòng luật lõi; chỉ chạy qua
  `extract_appendix_and_store`/`scripts/extract_appendix.py`.
- `records/template.py`: `derive_mapping_config` dựng cấu hình ánh xạ trường CHỈ
  từ dữ kiện Phụ lục A **đã duyệt** (đọc `v_procedure_fact` — P3); mỗi trường giữ
  `fact_id` + `quote` (P1). `validate_mapping_config` chặn khóa trùng/cột rỗng.

### Bộ đọc hồ sơ

- `records/docx_reader.py`: đọc biên bản Word bằng OOXML thô (`zipfile` + `lxml`,
  không cần `python-docx`): trường đầu mục (kể cả nhiều trường trên một dòng) và
  bảng kết quả; giữ `quote` từng dòng.
- `records/xlsx_reader.py`: đọc phiếu đo Excel bằng OOXML thô (không cần
  `openpyxl`): nhận diện dải bảng + tiêu đề cột, trường đầu mục ô-nhãn/ô-giá-trị.
- Cả hai chỉ phân tích số từ chính ô nguồn; không bao giờ suy `error` từ
  `measured`/`nominal` (P2).

### Đối sánh thiết bị + hạn hiệu lực

- `records/matching.py`: `normalize_serial` (bỏ khoảng trắng thừa, hạ hoa/thường),
  `find_or_create_device` theo `(loại, serial)`; thiếu serial → thiết bị tạm mới
  cờ `needs_identification` (không gộp nhầm hai thiết bị khác nhau).
- `records/store.py`: `store_record_draft` tạo `extraction` `pending` + hồ sơ +
  số liệu đo; `derive_expiry` chỉ tính từ dữ kiện `calibration_interval` ĐÃ DUYỆT
  (đọc view), lưu `expires_from_fact_id`; nạp lại chuyển extraction cũ sang
  `superseded`.

### API (tối thiểu, P3)

- `POST /api/records/ingest/{file_stem}` (technician/admin): nạp hồ sơ → `pending`.
- `GET /api/records` (approver/admin): chỉ hồ sơ đã duyệt, đọc
  `v_calibration_record`.
- `query/approved.py`: `list_approved_records`/`list_approved_measurements`/
  `approved_record_counts` — chỉ chạm view.

### Mẫu test

- `scripts/make_record_fixtures.py` sinh `tests/data/record_bien_ban.docx` và
  `tests/data/record_phieu_do.xlsx` (đã làm sạch) vì repo chưa có hồ sơ thật.

## Bất biến

- **P1**: mỗi trường/số liệu giữ `quote`; hồ sơ giữ `source_text`; extraction giữ
  nguyên văn toàn hồ sơ.
- **P2**: không tính lại số liệu. Ngoại lệ duy nhất là `expires_at`, dẫn xuất từ
  dữ kiện chu kỳ đã duyệt và luôn kèm `expires_from_fact_id`. Guard
  `test_records_no_recalc_guard.py` quét mã `records/` chặn phép trừ
  measured/nominal và gán error từ hai giá trị đó.
- **P3**: hồ sơ/số liệu đo chỉ lộ qua view đã duyệt; cấu hình đọc hồ sơ chỉ dựng
  từ dữ kiện Phụ lục A đã duyệt.

## Cổng kiểm chứng

- `tests/unit/backend/test_migrations_sprint7.py` — migration 006 lên/xuống + view.
- `tests/unit/backend/test_records_template.py` — dựng/kiểm cấu hình; pending bị ẩn;
  luật Phụ lục A trên corpus thật; duyệt rồi mới dựng được cấu hình.
- `tests/unit/backend/test_records_matching.py` — gộp/tách serial, thiếu serial.
- `tests/unit/backend/test_records_readers.py` — hai bộ đọc trên tệp mẫu; P1 quote;
  P2 không tính lại error.
- `tests/unit/backend/test_records_store.py` — ghi pending, hạn hiệu lực có xuất xứ
  (chỉ dữ kiện đã duyệt), P3 ẩn tới khi duyệt, supersede khi nạp lại.
- `tests/unit/backend/test_records_routes.py` — ma trận quyền + luồng nạp + P3.
- `tests/unit/backend/test_records_no_recalc_guard.py` — guard P2 quét `records/`.

## Lệnh vận hành

```bash
make check            # lint + fidelity + eval + 542 unit test
make db-upgrade       # áp migration 006
make records-fixtures # sinh lại tệp mẫu docx/xlsx
make extract-appendix # trích xuất Phụ lục A (thêm --apply để ghi pending)
```

Chưa mở Sprint 8 (bề mặt tra cứu/lịch sử thiết bị).
