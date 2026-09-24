# Sprint 6 — Hàng đợi duyệt

## Đã triển khai

- `review/queue.py` — nghiệp vụ hàng đợi duyệt, thuần DB (không phụ thuộc FastAPI):
  - **Liệt kê + lọc**: `list_queue` mặc định chỉ `pending` (spec §9 S6), lọc theo
    tài liệu, `fact_kind`, `extractor`, khoảng điểm tin cậy, phân trang; sắp xếp
    theo điểm tin cậy **tăng dần** để người duyệt gặp dòng khó trước (spec §12).
    Lọc `fact_kind` dùng subquery để một extraction §6 có hai dòng `procedure_fact`
    (giới hạn + sàn) không bị nhân đôi kết quả.
  - **Duyệt** `approve`, **từ chối kèm lý do** `reject` (lý do bắt buộc), **sửa
    giá trị rồi duyệt** `edit_and_approve`, **duyệt hàng loạt cùng luật**
    `bulk_approve` (theo `extractor`, thu hẹp được theo tài liệu/mục).
  - **Audit**: mọi thao tác ghi `audit_log` (`entity_type="extraction"`) kèm
    `before`/`after`; `audit_history` trả lịch sử kèm tên người thao tác. Duyệt
    hàng loạt ghi một dòng cho mỗi extraction để lịch sử từng dòng vẫn đầy đủ.
  - **Nguồn tô sáng an toàn**: `build_source_view` dựng `section_text` của mục
    kèm vị trí tương đối của `quote`; trả văn bản thuần, client render bằng text
    node nên không có đường chèn HTML.
- `query/approved.py` — bề mặt tra cứu đầu tiên, **chỉ** `SELECT` từ
  `v_procedure_fact`/`v_procedure_standard`/`v_term` (P3). Bộ guard
  `db.views.scan_query_source` từ Sprint 4 giờ bảo vệ code thật.
- `api_server.py` — nhóm route `/api/extractions` (vai trò **approver/admin**):
  - `GET /api/extractions` — lọc tài liệu / `fact_kind` / độ tin cậy / luật / trạng
    thái, phân trang;
  - `GET /api/extractions/{id}` — chi tiết + nguồn nguyên văn tô sáng;
  - `POST /api/extractions/{id}/approve`, `.../reject`, `.../edit`;
  - `POST /api/extractions/bulk-approve`;
  - `GET /api/extractions/{id}/audit`.
- `db/migrations/versions/005_review_indexes.py` + index trên `extraction.extractor`
  và `extraction.confidence` (phục vụ lọc/duyệt hàng loạt và thứ tự mặc định).
- Frontend:
  - `components/knowledge/KnowledgeTab.tsx` — tab **Tri thức**: danh sách chờ
    duyệt bên trái, giá trị đã trích (sửa được) bên phải, nguyên văn mục tô sáng
    ở dưới, lịch sử duyệt; phím tắt **A** duyệt, **R** từ chối, **J/K** (↑/↓) di
    chuyển; chặn theo vai trò approver/admin.
  - `components/knowledge/QuoteHighlight.tsx` + `highlight.ts` — tô sáng an toàn
    theo vị trí ký tự, dự phòng tìm nguyên văn; dùng lại ngôn ngữ thị giác của
    `SourcePanel`.
  - `services/reviewApi.ts` — client gọi route duyệt bằng bearer token.
  - Sidebar/TopBar/App thêm tab **Tri thức**.

## Bất biến

- **P1**: `edit_and_approve` chỉ đụng bảng dữ kiện; `quote`/`char_start`/`char_end`/
  `section_path`/`chunk_id` bất động và luôn được trả kèm để đối chiếu.
- **P2**: không tính lại số liệu; sửa giá trị là do người duyệt, có audit.
- **P3**: hàng đợi là bề mặt làm việc của người duyệt nên thấy `pending`; mọi bề
  mặt tra cứu chỉ đọc view đã duyệt. Duyệt → lộ qua view, từ chối → biến khỏi view.

## Cổng kiểm chứng

- `tests/unit/backend/test_review_queue.py` — lọc, duyệt/từ chối/sửa, duyệt hàng
  loạt, audit, P1 nguyên văn bất động, P3 view chỉ lộ dữ liệu đã duyệt.
- `tests/unit/backend/test_review_routes.py` — ma trận 401/403 cho mọi route,
  luồng duyệt/từ chối/sửa/hàng loạt qua API, audit, và "dữ liệu chưa duyệt không
  lộ ra bề mặt đã duyệt".
- `tests/unit/backend/test_query_view_guard.py` — guard quét `query/` sạch và
  module đã duyệt chỉ chạm view.
- `tests/unit/backend/test_migrations_sprint6.py` — migration index lên/xuống.

## Lệnh vận hành

```bash
make check            # backend: lint + fidelity + eval + unit test
make db-upgrade       # áp migration 005 (index hàng đợi)
cd frontend && npm run typecheck && npm run lint && npm run test && npm run build
```
