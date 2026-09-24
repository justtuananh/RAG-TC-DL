# Sprint 9 — Chat lai văn bản và số liệu

Mục tiêu (spec §9): hoàn tất năng lực bắt buộc thứ ba — chat trả lời được cả câu
hỏi quy định (từ QTKĐ) lẫn câu hỏi số liệu (từ sổ cái hồ sơ đã duyệt), với hai
khối trích dẫn tách bạch. Đây là sprint cuối cùng của lộ trình.

## Đã triển khai

### 1. Danh mục intent + schema tham số (`query/intents.py`)

Bảy intent khởi đầu đúng theo bảng spec §8, mỗi intent một model pydantic:

| Intent | Tham số | Kiểm tra |
|---|---|---|
| `device_history` | `serial` | chuỗi khác rỗng |
| `latest_record` | `serial` | chuỗi khác rỗng |
| `records_by_period` | `date_from`, `date_to`, `verdict` | ít nhất một mốc; `from ≤ to`; verdict `dat`/`khong_dat` |
| `procedure_params` | `procedure_number` **hoặc** `device_type` | ít nhất một bộ chọn |
| `devices_by_range` | `quantity`, `min_value`, `max_value`, `unit` | `min ≤ max` |
| `standards_for` | `procedure_number` | chuỗi khác rỗng |
| `error_trend` | `serial`, `step_code` | serial khác rỗng |

- **LLM chỉ chọn intent + điền tham số.** Không có text-to-SQL tự do: mỗi intent
  ứng với đúng một truy vấn tham số hóa do người viết trong `query/records.py` /
  `query/approved.py`. Tham số luôn được bind, không bao giờ nối vào SQL.
- Đầu ra LLM được bóc JSON (`extract_json`, chấp nhận bọc ```json```), chuẩn hóa
  khoá tiếng Việt (`so_hieu`→`serial`, `tu_ngay`→`date_from`, `ket_luan`→`verdict`…),
  chuẩn hóa ngày `DD/MM/YYYY` và `YYYY-MM-DD`, chuẩn hóa `đạt`→`dat`.
- **Mặc định rơi về `text`**: JSON hỏng, intent lạ, tham số sai schema, độ tin cậy
  thấp, hoặc LLM không sẵn sàng đều trả `IntentDecision(branch="text")`.
- `OllamaIntentClassifier` gọi Ollama native `/api/chat` (JSON, không stream),
  **thất bại an toàn** (trả `None` → text). Cổng `looks_like_data_question` chỉ gọi
  LLM khi câu hỏi có tín hiệu số liệu rõ (số hiệu, hồ sơ, lịch sử, khoảng ngày,
  phạm vi đo, số QTKĐ…); câu hỏi quy định thuần đi thẳng pipeline văn bản, không
  thêm độ trễ. Cổng này **chỉ bao giờ trả về `text`** nên không thể định tuyến nhầm.
- Bật/tắt bằng `INTENT_ROUTER_ENABLED` (mặc định bật). Cấu hình LLM phân loại:
  `INTENT_LLM_MODEL` / `INTENT_OLLAMA_URL` / `INTENT_LLM_TIMEOUT`.

### 2. Tầng định tuyến ba nhánh (`query/router.py`)

- `plan_route(question, classifier)` → `IntentDecision` (`text` / `data` / `mixed`).
- `build_data_payload(session, request)` chạy intent đã kiểm tham số và trả
  `DataPayload` gồm các `DataTable` + danh sách trích dẫn sổ cái.
- Bộ dựng bảng cho từng intent, **chỉ đọc view đã duyệt** (P3):
  - `device_history` / `latest_record` / `error_trend` → `query.records.device_history`
  - `records_by_period` → `query.records.list_records`
  - `devices_by_range` → `query.records.list_records` (lọc phạm vi + đại lượng, gom theo thiết bị)
  - `procedure_params` → `query.approved.list_approved_facts`
  - `standards_for` → `query.approved.list_approved_standards`
- Phân giải tham số "số QTKĐ"/"loại thiết bị"/"đại lượng" qua **view tham chiếu**
  mới `v_procedure` / `v_device_type` / `v_quantity` (migration 008) — tầng `query/`
  vẫn không chạm bảng gốc.
- **P1 cho mọi con số**: `Cell.provenance` là `{kind, id, field}`; hàm `_num_cell`
  chỉ hiện số khi có tham chiếu xuất xứ, thiếu nguồn thì để trống. `untraceable_cells`
  là cổng kiểm: danh sách ô số thiếu nguồn phải rỗng.
- **Trích dẫn tách bạch**: bảng mang `citations` dựng từ `query.provenance.resolve`
  (tài liệu · mục · chunk · nguyên văn), khác hẳn khối nguồn QTKĐ của câu trả lời văn bản.

### 3. View tham chiếu (migration `008_reference_views`)

`db/views.py` thêm nhóm `REFERENCE_VIEWS` (`v_quantity`, `v_device_type`,
`v_procedure`) và `create_reference_views` / `drop_reference_views`. Migration 008
tạo chúng trên nền 007; `create_all_approved_views` (dùng cho test) tạo đủ cả nhóm.
Đây là dữ liệu nền (không gắn trạng thái duyệt, như `v_unit`), nhưng đi qua view để
giữ P3.

### 4. Tích hợp API (`api_server.py`)

`POST /api/chat/stream` nay định tuyến trước khi trả lời:

- Cổng `is_calculation_request` vẫn chặn **đầu tiên**, không đổi.
- `text`: pipeline RAG hiện tại (`retrieve(top_k=50, top_n=5)` → `filter_by_confidence`
  → `build_messages` → `stream_ollama`), **không đổi**.
- `data`: phát event `status` → `data` (khối bảng) → `done{branch:"data", sources:[]}`.
  Câu trả lời văn xuôi **không chứa số** ("Kết quả tra cứu từ sổ cái hồ sơ đã duyệt:");
  số nằm trong bảng.
- `mixed`: chạy cả hai; stream câu trả lời văn bản (trích dẫn QTKĐ trong `sources`)
  rồi ghép khối số liệu sổ cái (`data` + `citations`) — hai khối trích dẫn tách bạch.
- Nhánh số liệu lỗi (ví dụ số hiệu không có hồ sơ đã duyệt) **rơi về text**, không
  chặn câu trả lời văn bản.
- Event `done` thêm `branch` và `data`; event `data` mới cho khối số liệu.

### 5. Frontend

- `types.ts`: `DataCellPayload` / `DataTablePayload` / `LedgerCitation` /
  `ChatDataPayload`; `Message.branch` + `Message.data`; `AppState.pendingDeviceId`.
- `components/chat/DataResultTable.tsx`: bảng kết quả số liệu. Mỗi ô số là `<button>`
  mở `ProvenanceDrawer` (P1); ô số hiệu thiết bị mở trang thiết bị trong tab "Dữ liệu";
  khối "Trích dẫn sổ cái" hiển thị tách biệt. **Không nhét số vào văn xuôi.**
- `MessageBubble` render khối số liệu; `ChatColumn` giữ ngăn kéo xuất xứ dùng chung.
- `useAppStore`: xử lý event `data`, gắn `branch`/`data` vào tin nhắn cuối (được lưu
  cùng hội thoại), thêm action `openDevice` / `clearPendingDevice`.
- `DataTab`: nhận `pendingDeviceId` để mở thẳng trang thiết bị từ bảng chat.

### 6. Eval + cổng

- `eval/intent_eval.py` + `eval/intent_golden.jsonl` (29 câu): đo
  - **độ chính xác chọn intent** (nhánh + intent) ≥ 0,90;
  - **kiểm tham số**: mọi payload sai schema phải rơi về `text`;
  - **fallback text**: LLM không sẵn sàng / JSON hỏng → `text`;
  - **không số không nguồn**: chạy resolver trên SQLite in-memory, `untraceable_cells` rỗng;
  - **không hồi quy truy hồi**: mọi câu hỏi văn bản trong tập vàng đi đúng nhánh `text`
    (bổ sung cho `eval/run_eval.py` — cổng recall@5 hiện có, chạy khi có Qdrant).
  - Mặc định chạy **bộ phân loại kịch bản** (tất định, không cần Ollama); `--live` để đo model thật.
- `make check` thêm bước `intent-eval`.

## Cổng kiểm chứng

Backend (`.venv-dev`, không cần Docker):

- `tests/unit/backend/test_intent_router.py` — schema tham số, mặc định text, bảng
  dữ liệu + xuất xứ, P3 (hồ sơ `pending` không lộ).
- `tests/unit/backend/test_chat_router_routes.py` — ba nhánh qua `/api/chat/stream`,
  cổng tính toán vẫn chặn trước, nhánh text gọi đúng phễu `retrieve(top_k=50, top_n=5)`,
  nhánh số liệu lỗi rơi về text.
- `tests/unit/backend/test_migrations_sprint9.py` — migration 008 lên/xuống + view.
- `eval/intent_eval.py` — intent ≥ 0,90, 0 số không nguồn, text không lạc nhánh.

Frontend:

- `src/components/chat/DataResultTable.test.tsx` — caption/role, ô số là nút xuất xứ,
  số hiệu mở trang thiết bị, trích dẫn sổ cái tách biệt, trạng thái rỗng.
- `src/services/liveApi.test.ts` — phân tích event `data` của SSE.

## Bất biến

- **P1**: mọi ô số trong bảng chat kèm `{kind, id, field}`; `_num_cell` không hiện
  số khi thiếu nguồn; `untraceable_cells` là cổng.
- **P2**: không tính lại số liệu nguồn; resolver chỉ đọc và định dạng.
- **P3**: `query/` chỉ đọc `v_*`; guard `db.views.scan_query_source` quét chính thư mục
  này; hồ sơ `pending` không lộ qua chat số liệu.
- **Không hồi quy**: cổng tính toán và pipeline RAG văn bản giữ nguyên; mọi bất định
  định tuyến về `text`.

## Lệnh vận hành

```bash
make check                      # lint + fidelity + 3 eval + unit test (gồm intent-eval)
make db-upgrade                 # áp migration 008 (view tham chiếu)
make eval                       # recall@5 (cần Qdrant) — cổng truy hồi hiện có
python -m eval.intent_eval      # cổng định tuyến chat lai
cd frontend && npm run typecheck && npm run lint && npm run test && npm run build
```

## Số đo (SQLite in-memory, bộ dữ liệu vàng nhỏ)

| Chỉ số | Giá trị |
|---|---|
| Độ chính xác intent (kịch bản) | 29/29 = 1,000 |
| Câu hỏi văn bản đi đúng nhánh text | 15/15 |
| Ô số không truy được nguồn | 0 |
| Lỗi truy vấn dữ liệu | 0 |
| `make check` | 633 passed, 1 skipped |
| Frontend | typecheck + lint + 86 test + build đều xanh |
