# RAG-TC-DL — Tra cứu QTKĐ và tính công thức đã phê duyệt

Ứng dụng React + FastAPI tra cứu tài liệu đo lường bằng RAG, trả lời tiếng Việt kèm nguồn và hiển thị công thức. Luồng tính riêng trong màn hình **Tài liệu → chọn DOCX → Công thức và phê duyệt**:

**Ingestion → bản nháp → người dùng đối chiếu và phê duyệt → nhập số liệu → backend tính.**

LLM không tự tạo phép tính được phép chạy. Ingestion chỉ gợi ý biểu thức/metadata; công thức chưa duyệt, sai phiên bản hoặc nguồn hết hiệu lực đều bị chặn. Chat hiện hướng dẫn mở form, chưa tự chọn ID công thức đã duyệt từ hội thoại. Các model chạy local; lần cài đặt/build đầu cần tải thư viện và model trước khi vận hành offline.

## Trạng thái và giới hạn

- BE/FE có tạo/lấy/sửa/duyệt/từ chối nháp, ca đối chứng, kiểm tra đơn vị/miền/điều kiện và form tính. Chỉnh định nghĩa thu hồi phê duyệt; xóa rồi tải lại nguồn cũ phải duyệt lại.
- Bảy DOCX hiện có **334 ứng viên chờ duyệt**, trong đó **57 có biểu thức gợi ý**, 277 chưa có biểu thức. Đây không phải 334 bộ tính hoạt động. Registry lab 47 bộ tính là thí nghiệm riêng.
- PDF có trích text để tra cứu nhưng chưa tạo được nháp công thức có định vị. OLE/MathType lỗi và biểu thức phức tạp cần đối chiếu thủ công.
- Chưa có xác thực/phân quyền người duyệt. Tên người duyệt tự nhập và nhật ký không chứng minh danh tính hay thay thế phê duyệt chuyên môn.
- Điểm **96% trước đây là điểm checklist sau sửa các ca đã biết**, không chứng minh độ chính xác nghiệp vụ hoặc khả năng tổng quát. Trọng số và tolerance hậu kiểm có rủi ro bias. Xem [audit đánh giá](build/formula-review/BIAS_AUDIT.md); giữ [báo cáo cũ](build/formula-review/INDEPENDENT_REVIEW.md) để truy vết.

## Thành phần

| Thành phần | Mã / cổng | Chức năng |
|---|---|---|
| React + TypeScript | `frontend/`, Docker `3000`, dev `5173` | Chat SSE, tài liệu gốc, duyệt công thức, nhập số liệu |
| FastAPI | `api_server.py`, `8080` | API tài liệu/chat và router `formula_registry/api.py` |
| Registry công thức | `formula_registry/` | SQLite, phiên bản, nguồn/hash, nhật ký và phê duyệt |
| Bộ tính | `formula_lab/engine.py` | Decimal, biểu thức giới hạn, scalar/series, đổi đơn vị |
| Ingestion | `ingestion/`, `ingestion_jobs.py` | DOCX OMML/OLE, PDF text, nháp trước embedding |
| Truy hồi | `retrieval/`, `index/` | Dense + BM25 + RRF + rerank, Qdrant `6333` |
| Model local | `docker/inference/`, Ollama | bge-m3 `8010`, reranker `8011`, LLM `11434` |

Gradio `app.py`, `frontend-legacy/` và adapter `kotaemon_ext/` được giữ để tương thích/tham khảo. Luồng phê duyệt mới nằm trong React/API chính; không mặc định có trên các UI cũ.

## Chạy local

Python **3.12** và Node **24** là môi trường được dùng để kiểm tra cập nhật này. Cần Ruby và gem `mathtype_to_mathml` + `pry` để chuyển MathType OLE; nếu thiếu, các công thức đó vẫn phải được ghi nhận là chưa trích xuất được.

```bash
python3.12 -m venv .venv-dev
.venv-dev/bin/python -m pip install -r requirements-app.lock -r requirements-dev.txt
# Khi cần chuyển MathType trên host:
gem install mathtype_to_mathml pry

cd frontend
npm ci
cd ..
./run.sh --no-docker
```

`run.sh` chọn venv trong dự án trước; có thể đặt `QTKD_PYTHON=/path/to/python`. Mở `http://localhost:5173`. RAG cần Qdrant, embedding, reranker và Ollama; riêng tạo nháp từ DOCX hiện có/phê duyệt/tính không cần các service model này.

Chạy từng phần nếu muốn:

```bash
.venv-dev/bin/python -m uvicorn api_server:app --host 127.0.0.1 --port 8080
# Terminal khác
cd frontend && npm run dev
```

## Docker

```bash
cp .env.example .env
mkdir -p .formula-registry build/spike_a
make up
make pull-model
# Mở http://localhost:3000
```

Compose đầy đủ hiện khai báo NVIDIA GPU cho embedding, reranker và Ollama; cần Docker Compose v2, NVIDIA driver và Container Toolkit. API/FE cùng registry không cần GPU. Để thử riêng giao diện và luồng duyệt/tính, không dựng model:

```bash
docker compose build api frontend
docker compose up -d --no-deps api
docker compose up -d --no-deps frontend
```

Lúc này RAG chưa hoạt động. Tạo nháp cho tài liệu có sẵn qua nút trong UI, hoặc:

```bash
make formula-drafts-docker
```

Lệnh chỉ tạo nháp, không phê duyệt. Upload rồi “Xử lý” trên UI tạo nháp trước embedding; nếu model/Qdrant chưa chạy, trạng thái xử lý tài liệu có thể báo lỗi nhưng vẫn mở được phần công thức.

| Dữ liệu | Nơi lưu bền |
|---|---|
| Tài liệu gốc | `TC_DL/` → `/app/TC_DL` |
| Markdown, báo cáo ingestion | `build/spike_a/` → `/app/build/spike_a` |
| Nháp, quyết định, lịch sử | `.formula-registry/` → `/app/.formula-registry` |
| Vector/model | volumes Qdrant, Ollama và cache Hugging Face |

Registry không commit vào Git. Sao lưu đồng thời nguồn và DB; giữ hash nguồn để quyết định duyệt còn hiệu lực. Xem [hướng dẫn vận hành](docs/FORMULA_DRAFT_APPROVAL.md). `docker compose down` giữ dữ liệu; `down -v` xóa named volumes, nhưng không xóa các thư mục bind-mount trên host.

## API công thức

API chính có OpenAPI tại `http://localhost:8080/docs` và `/openapi.json`.

| Method | Đường dẫn |
|---|---|
| GET | `/api/documents/{document_id}/formula-drafts` |
| POST | `/api/documents/{document_id}/formula-drafts/generate` |
| GET / PUT | `/api/formula-drafts/{id}` |
| POST | `/api/formula-drafts/{id}/approve` |
| POST | `/api/formula-drafts/{id}/reject` |
| POST | `/api/formula-drafts/{id}/calculate` |

Mọi thao tác sửa/quyết định/tính gửi `revision`; sai phiên bản trả409. Dữ liệu sai trả422, không ghi đè bản đã lưu. Payload và quy tắc duyệt: [hợp đồng API](docs/FORMULA_DRAFT_APPROVAL.md).

## Thư viện và kiểm thử

- `requirements-app.txt`: dải phụ thuộc runtime; `requirements-app.lock`: phiên bản trực tiếp và bắc cầu đã resolve cho Python 3.12, dùng chung local/Docker/CI. SQLite/Decimal/AST dùng thư viện chuẩn Python.
- `requirements-dev.txt`: pytest, HTTP mocks, lint; không ghim ngược runtime theo mã cũ.
- `requirements.txt`: phụ thuộc bổ sung cho QA ảnh ingestion.
- `formula_lab/requirements.lock`: môi trường thí nghiệm lab riêng, không dùng làm requirements cho API sản phẩm.
- `frontend/package-lock.json`: lock npm; Docker và local dùng `npm ci`.

```bash
make test-unit PY=.venv-dev/bin/python
make test-formula PY=.venv-dev/bin/python
make check-frontend
# Lint/fidelity gate cũ:
make check PY=.venv-dev/bin/python
```

Test hồi quy do dev viết, test giữ riêng có đáp án khóa trước, kiểm thử service/model thật và phê duyệt chuyên môn là các lớp bằng chứng khác nhau. Không cộng chúng thành một tỷ lệ “chính xác toàn hệ thống”. Bất kỳ ca giữ riêng nào đã lộ đều trở thành hồi quy cho lần sửa tiếp theo.

## Tài liệu

- [FE và hệ thiết kế](frontend/README.md)
- [Luồng phê duyệt, API, lưu trữ](docs/FORMULA_DRAFT_APPROVAL.md)
- [Thư viện và vận hành](docs/SYSTEM_DEPENDENCIES.md)
- [Harness kiểm thử](tests/README.md)
- [Audit bias và thử giữ riêng](build/formula-review/BIAS_AUDIT.md)
- [Tiến độ và số liệu lịch sử](TC_DL/TIEN_DO_NGHIEN_CUU_CONG_THUC.md)
- [Thí nghiệm công thức](formula_lab/README.md)
- [Retrieval/eval](eval/README.md)
