# Sprint 8 — Bề mặt tra cứu và lịch sử thiết bị

## Đã triển khai

### View đã duyệt phục vụ tra cứu (P3)

`db/views.py` thêm nhóm `QUERY_VIEWS` (migration `007_query_views`):

- `v_unit` — bảng đơn vị tham chiếu, để tầng `query/` quy đổi phạm vi mà không
  chạm bảng gốc.
- `v_extraction` — extraction ĐÃ DUYỆT kèm `file_stem`/`display_name`, dùng dựng
  xuất xứ P1.
- `v_record_detail` — một dòng/hồ sơ đã duyệt đã nối sẵn thiết bị, loại, đại
  lượng, QTKĐ và phạm vi/cấp chính xác đã duyệt của QTKĐ đó (kèm mã đơn vị).
- `v_measurement_detail` — số liệu đo đã duyệt kèm đơn vị và ngữ cảnh hồ sơ.

Nhờ gộp sẵn ở tầng view, tầng `query/` chỉ quét vài view thay vì tự nối nhiều
bảng — vừa nhanh vừa giữ P3. Migration cũng thêm index `calibration_record
(calibrated_at)` và `(verdict)` phục vụ lọc/sắp xếp 10 nghìn hồ sơ.

### Truy vấn có tham số

- `query/records.py`:
  - `list_records` / `all_records` — phân trang, sắp xếp (whitelist cột), lọc theo
    loại thiết bị, đại lượng, QTKĐ, kết luận, khoảng thời gian, khoảng phạm vi đo
    (có quy đổi đơn vị), cấp chính xác, số hiệu và tìm kiếm tự do.
  - `get_record` — chi tiết hồ sơ + điểm đo, mỗi ô số kèm tham chiếu xuất xứ.
  - `list_devices` / `device_history` — thiết bị có ≥1 hồ sơ đã duyệt; lịch sử
    gồm định danh, dòng thời gian kiểm định và diễn biến sai số gom theo mốc đo.
  - `filter_options` — giá trị bộ lọc suy từ dữ liệu đã duyệt.
- `query/provenance.py` — `resolve`/`measurement_provenance`/`fact_provenance`/
  `record_provenance` dựng đoạn nguyên văn (tài liệu, mục, chunk, trích dẫn,
  vị trí tô sáng) cho từng ô số.
- `query/source.py` — hàm dựng nguồn tô sáng dùng chung; `review.queue` ủy nhiệm
  cho nó để bề mặt duyệt và bề mặt tra cứu có đúng một cài đặt P1.
- `query/export.py` — bộ ghi XLSX tối giản (zipfile + XML, không thêm phụ thuộc) và
  bảng hàng Excel có cột xuất xứ xen sau mỗi ô số.

### API (mọi vai trò đã đăng nhập — bề mặt đọc)

`api_server.py` thêm nhóm `/api/data`:

- `GET /api/data/filters`
- `GET /api/data/records` — phân trang/sắp xếp/lọc
- `GET /api/data/records/{id}` — chi tiết + điểm đo
- `GET /api/data/records/export.xlsx` — xuất Excel kết quả lọc, kèm cột xuất xứ
- `GET /api/data/devices` và `GET /api/data/devices/{id}/history`,
  `GET /api/data/devices/by-serial/{serial}`
- `GET /api/data/provenance` — mở nguồn một ô số

### Dữ liệu tổng hợp + hiệu năng

- `scripts/seed_synthetic_records.py` — seed N hồ sơ đã duyệt (mặc định 10.000)
  cùng điểm đo, QTKĐ tổng hợp riêng "SYN.8"; chạy lại gỡ và dựng lại (idempotent).
  Lệnh: `make seed-synthetic` (hoặc thêm `--apply`).
- `tests/unit/backend/test_data_perf.py` — cổng hiệu năng với 10.000 hồ sơ.

### Frontend — tab "Dữ liệu"

- `components/data/DataTab.tsx` — bảng dày, lọc ở đầu cột, phân trang, xuất Excel,
  ngăn kéo chi tiết, chuyển sang trang thiết bị.
- `components/data/RecordsTable.tsx` — mỗi ô số là `<button>` mở đúng nguồn; mọi
  điều khiển có `aria-label`, cột sắp xếp có `aria-sort`.
- `components/data/RecordDetailPanel.tsx` — trường đầu mục + bảng điểm đo, từng ô
  số bấm mở nguồn.
- `components/data/DeviceHistoryView.tsx` + `ErrorTrendChart.tsx` — định danh, dòng
  thời gian, biểu đồ diễn biến sai số (SVG `role="img"` + bảng số liệu truy cập
  được bằng bàn phím).
- `components/data/ProvenanceDrawer.tsx` — tài liệu · mục · chunk · trích dẫn tô
  sáng (dùng lại `QuoteHighlight`, không nhúng HTML).
- `services/dataApi.ts` + kiểu dữ liệu trong `types.ts`; tab thêm vào Sidebar/TopBar.

## Bất biến

- **P1**: mỗi ô số trả tham chiếu `{kind, id, field}`; `/api/data/provenance` mở
  đúng tài liệu/mục/chunk/trích dẫn. Excel có cột "Tài liệu nguồn", "Mục nguồn",
  "Chunk nguồn", "Trích dẫn nguồn" và cột nguồn xen sau từng ô số.
- **P2**: không có phép tính lại số liệu nguồn; `range_*` đọc từ dữ kiện QTKĐ đã
  chuẩn hóa sẵn, giá trị đo đọc nguyên trạng.
- **P3**: `query/` chỉ đọc `v_record_detail`/`v_measurement_detail`/`v_extraction`/
  `v_procedure_fact`/`v_unit`; guard `db.views.scan_query_source` quét chính thư mục
  này. Hồ sơ `pending` không lộ ra qua bất kỳ route `/api/data/*` nào.

Ghi chú P1: mỗi điểm đo có ``quote`` riêng nên ô số liệu mở ra đúng dòng nguồn. Các
ô đầu mục cấp hồ sơ (ngày kiểm định, nhiệt độ, độ ẩm) trỏ về extraction của hồ sơ —
đoạn nguyên văn toàn hồ sơ ``source_text`` (Sprint 7 chưa lưu quote riêng từng
trường); vẫn đủ tài liệu/mục/chunk/nguyên văn để đối chiếu, nhưng không tô sáng
được đúng một dòng như điểm đo.

## Cổng kiểm chứng

- `tests/unit/backend/test_data_records.py` — lọc/phân trang/sắp xếp + tham chiếu ô số.
- `tests/unit/backend/test_data_devices.py` — lịch sử, dòng thời gian, diễn biến sai số, P3.
- `tests/unit/backend/test_data_provenance.py` — xuất xứ từng loại, P3.
- `tests/unit/backend/test_data_export.py` — XLSX hợp lệ + cột xuất xứ + chỉ dữ liệu đã duyệt.
- `tests/unit/backend/test_data_routes.py` — ma trận quyền + luồng API + P3.
- `tests/unit/backend/test_data_perf.py` — 10.000 hồ sơ, mỗi truy vấn < 500 ms.
- `tests/unit/backend/test_migrations_sprint8.py` — migration 007 lên/xuống + view.
- Frontend: `contrast.test.ts`, `accessibility.test.ts` (tương phản WCAG AA),
  `RecordsTable.test.tsx` (aria/role/nút xuất xứ bàn phím), `dataApi.test.ts`.

### Số đo hiệu năng (SQLite in-memory, 10.000 hồ sơ + 10.000 điểm đo)

| Truy vấn | Thời gian (tốt nhất / 5 lần) |
|---|---|
| Seed 10k hồ sơ | ~242 ms |
| `list_records(limit=50)` | ~19 ms |
| `list_records(limit=200)` | ~22 ms |
| Lọc `verdict` + khoảng ngày | ~21 ms |
| Lọc phạm vi đo (quy đổi bar) | ~20 ms |
| Phân trang `offset=5000` | ~35 ms |
| `device_history` | ~1 ms |
| `filter_options` | ~12 ms |

Ngưỡng cổng: mỗi truy vấn bảng < 500 ms (spec §9 S8).

## Lệnh vận hành

```bash
make check                      # lint + fidelity + eval + unit test
make db-upgrade                 # áp migration 007 (view tra cứu + index)
make seed-synthetic             # 10.000 hồ sơ tổng hợp đã duyệt
cd frontend && npm run typecheck && npm run lint && npm run test && npm run build
```

Chưa mở Sprint 9 (chat lai văn bản + số liệu).
