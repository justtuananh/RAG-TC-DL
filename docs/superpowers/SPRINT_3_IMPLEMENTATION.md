# Sprint 3 — Khung khái niệm và chuẩn hóa đơn vị

## Đã triển khai

- Migration `003_create_measurement_framework.py` tạo bốn bảng nền `quantity`,
  `unit`, `device_type`, `procedure` và seed sẵn khung khái niệm. Đi/lùi được
  trên DB sạch; `procedure.document_id` giữ truy nguyên về sổ tài liệu (P1).
- `db/models.py` thêm `Quantity`, `Unit`, `DeviceType`, `Procedure`. `aliases`
  lưu JSON list để router đọc thay cho hardcode.
- `knowledge/seed_data.py` là nguồn sự thật duy nhất cho dữ liệu seed: 6 đại
  lượng, 27 đơn vị (đủ nhóm áp suất, nhiệt độ, độ ẩm, độ dài; thêm khối lượng,
  thời gian), 7 loại thiết bị.
- `knowledge/vnnum.py`: phân tích số Việt (phẩy thập phân, cách phân nhóm hàng
  nghìn, kể cả NBSP U+00A0 và khoảng trắng hẹp không ngắt U+202F), khoảng
  (`÷`, `đến`, `tới`, `từ … đến`), sai số `±` (kèm giá trị trung tâm), tách đơn
  vị, hỗ trợ ký hiệu khoa học `×10-5`. Thuần hàm, không phụ thuộc DB.
- `knowledge/units.py`: quy đổi `si = factor * x + offset` hai chiều, tra cứu
  theo code/alias/tên đã chuẩn hóa, và **từ chối đơn vị lạ** (`resolved=False`,
  để trống `value_min`/`value_max`).
- `knowledge/reference.py`: truy vấn chỉ-đọc `device_alias_map` (alias thiết bị
  → số QTKĐ), dựng từ `device_type.aliases` + `procedure.number`.
- `knowledge/procedure.py`: đọc đầu mục QTKĐ (số, năm, tiêu đề, phiên bản) và
  suy luận loại thiết bị theo alias dài nhất.
- `retrieval/router.py`: `_DEVICE_ALIASES` được thay bằng bộ nhớ đệm đọc từ DB
  (`_ensure_device_aliases`), có hằng số dự phòng để không đổi hành vi truy hồi
  khi Postgres chưa lên/chưa seed. Một alias trỏ nhiều QTKĐ → coi là mơ hồ, rơi
  về tìm toàn kho.
- `scripts/seed_knowledge.py`: seed/upsert khung khái niệm, idempotent.
- `scripts/generate_procedures.py`: sinh `procedure` cho QTKĐ đang có; mặc định
  dry-run, `--apply` để ghi; dùng `--apply` qua `make generate-procedures`.
- Dockerfile copy thêm `knowledge/`; Makefile thêm `seed-knowledge`,
  `generate-procedures`.

## Cổng kiểm chứng

- `tests/unit/backend/test_vnnum.py` + `test_vnnum_corpus.py`: bảng biến thể số,
  quét toàn bộ khoảng `÷` và sai số `±` trong corpus QTKĐ thật.
- `tests/unit/backend/test_units.py`: quy đổi hai chiều cho từng đơn vị áp suất,
  offset nhiệt độ, và từ chối đơn vị lạ.
- `tests/unit/backend/test_reference.py` + `test_router_aliases.py`: alias DB
  phủ hết alias dự phòng của router cũ (bảo vệ eval không tụt), có cache, và
  xử lý mơ hồ.
- `tests/unit/backend/test_procedure.py`: đọc đầu mục 7 QTKĐ và sinh procedure
  idempotent.
- `tests/unit/backend/test_migrations_sprint3.py`: migration lên/xuống/lên trên
  SQLite sạch, không cần Docker.

## Lệnh vận hành

```bash
make db-upgrade
make seed-knowledge
make generate-procedures
make check
```
