# Sprint 2 — Sổ tài liệu chuyển về cơ sở dữ liệu

## Đã triển khai

- Migration `002_create_document.py` tạo bảng `document` với hash SHA-256, loại tài liệu, trạng thái nạp, lỗi và người tải.
- `scripts/migrate_documents.py` quét `TC_DL/`, hỗ trợ `--apply` và mặc định dry-run; tài liệu đã có Markdown được đánh dấu `ready`.
- `ingestion/classify.py` phân loại xác định theo tên/nội dung: `qtkd`, `ho_so_kiem_dinh`, `phieu_do`, `danh_muc`, `khac` và trả điểm tin cậy.
- `ingestion_jobs.py` đọc danh sách từ PostgreSQL, chống upload trùng theo SHA-256, ghi trạng thái xử lý và đổi tên/xóa trong ledger.
- Payload Qdrant có thêm `document_id` để truy ngược về Postgres.
- API giữ nguyên hình dạng JSON hiện có cho frontend; các route ghi đã yêu cầu vai trò technician/admin.
- Docker image API đã được mở rộng để chứa `db/`, `auth/`, migrations và dependencies.
- Đã bỏ `build/spike_a/doc_meta.json` cùng code `_load_meta/_save_meta` không còn dùng trong `ingestion_jobs.py`; `document` là nguồn sự thật duy nhất.

## Hoàn thiện Sprint 1 còn thiếu (auth + audit)

- `save_upload(..., uploaded_by=...)` lưu chủ thể tải lên vào `document.uploaded_by`.
- Route ghi (`upload`, `process`, `delete`, `rename`) gọi `create_audit_log` qua helper `_audit`:
  - `upload`: `after` là snapshot tài liệu; `delete`: `before` là snapshot; `rename`: `before`/`after` là `display_name`.
  - Chế độ dev không xác thực trả về mock không có hàng trong `app_user` → bỏ qua audit để không vi phạm khóa ngoại `actor_id`.
- Endpoint `POST /api/auth/logout` (204, client xóa token) và `POST /api/auth/refresh` (cấp token mới).
- `requirements-dev.txt` bổ sung `sqlalchemy`, `psycopg2-binary`, `bcrypt`, `pyjwt`, `alembic` để CI (requirements-app + requirements-dev) collect được `test_auth`/`test_auth_routes`.
- Test đơn mới `tests/unit/backend/test_auth_routes.py`: FastAPI TestClient + SQLite in-memory, không cần Docker/Postgres — ma trận 401/403, ghi audit đúng chủ thể, login/me/logout/refresh, và chế độ dev bỏ xác thực.

## Lệnh vận hành

```bash
make db-upgrade
make migrate-documents
make db-backup
make db-check
```

Phân loại có thể kiểm tra trước khi ghi:

```bash
docker compose run --rm --no-deps api python scripts/migrate_documents.py
```
