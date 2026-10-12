# Gỡ luồng trích xuất tri thức và nhánh số liệu

Ngày: 2026-10-12.
Nhánh: `refactor/remove-knowledge-flow` (tách từ `feat/procedure-profile`).
Người thực hiện code: opencode `deepseek-v4.1-flash`.
Người review và nghiệm thu: Claude.

## Mục tiêu

Hệ thống quay về chatbot RAG tra cứu QTKĐ thuần văn bản.
Gỡ toàn bộ luồng trích xuất tri thức (luật + LLM §6 + Phụ lục A), hàng duyệt, hồ sơ QTKĐ, sổ cái biên bản, danh mục NAS, nhánh `data`/`mixed` của chat cùng toàn bộ UI của chúng.
Bảng Postgres không còn dùng bị drop bằng migration mới `014`.

## Bất biến (KHÔNG được đổi)

Luồng RAG văn bản giữ nguyên hành vi:

- Stage 1 `ingestion/` (extract_docx, mtef, mtef_to_latex, omml, spike_a, extract_pdf*, extract_xlsx, convert_legacy, classify, docx_grid) giữ nguyên logic.
- Chiến thuật chunk cha-con `ingestion/chunker.py` giữ nguyên.
- `embedding/`, `vectorstore/`, `reranking/`, `retrieval/` (gồm `router.py`, context builder, `quote.py`, `hybrid_retriever.py`), `llm/` giữ nguyên.
- Các khóa `chunking`, `retrieval`, `reranking`, `llm.context`, `embedding`, `vectorstore` trong `config/settings.yaml` giữ nguyên.
- `retrieval/router.py` vẫn đọc alias thiết bị từ bảng `device_type` + `procedure` qua `knowledge.reference.device_alias_map`.
- Xử lý câu hỏi mơ hồ thiết bị (`query/device_ambiguity.py`) của nhánh văn bản giữ nguyên hành vi.
- Hợp đồng SSE của nhánh văn bản (`sources`, `token`, `done` với citations) giữ nguyên, chỉ bỏ các trường riêng của nhánh số liệu.
- Auth, tài liệu (upload, xem gốc, preview LibreOffice, xóa), lịch sử chat, Gradio UI giữ nguyên.

Kiểm chứng: `git diff feat/procedure-profile -- ingestion/chunker.py ingestion/extract_docx.py ingestion/mtef.py ingestion/mtef_to_latex.py ingestion/spike_a.py embedding vectorstore reranking retrieval llm` phải rỗng.

## Giữ lại (thu gọn)

| Thành phần | Lý do | Việc cần làm |
|---|---|---|
| Bảng `quantity`, `unit`, `device_type`, `procedure` (migration 003) | Router file + câu hỏi mơ hồ thiết bị đọc chúng | Giữ model ORM, bỏ quan hệ trỏ tới bảng bị drop |
| `knowledge/procedure.py`, `reference.py`, `seed_data.py`, `vnnum.py` | Sinh `procedure` khi upload QTKĐ, seed khung đo lường, alias thiết bị | Chuyển `ensure_procedure` từ `knowledge/extract.py` sang `knowledge/procedure.py`; xóa phần còn lại của `knowledge/` |
| `query/device_ambiguity.py` | Nhánh văn bản dùng | Chép hàm `tokens` (và regex nó cần) từ `query/record_fields.py` vào chính file này; xóa mọi file khác của `query/` |
| `records/xlsx_grid.py` | `ingestion/extract_xlsx.py` đọc Excel cho RAG | Dời sang `ingestion/xlsx_grid.py`, sửa import |
| `scripts/generate_procedures.py`, `scripts/seed_knowledge.py` | Dựng `procedure`/`device_type` cho kho cũ | Giữ, cùng target Makefile `generate-procedures`, `seed-knowledge` |

## Xóa

Backend:

- Package: `review/`, `records/` (sau khi dời `xlsx_grid`), `catalogs/`, phần còn lại của `knowledge/` (`extract.py`, `llm_extract.py`, `record_labels.py`, `units.py`, `rules/`), phần còn lại của `query/`.
- `api/routes/extractions.py`, `records.py`, `data.py`, `knowledge.py`, `api/errors.py`; bỏ khỏi `_ROUTERS` trong `api/main.py`.
- `api/services/chat_stream.py`: bỏ `query_router.plan_route`, `build_data_payload`, nhánh `data`/`mixed`, các trường `branch`/`data` của `done` (GIỮ `done.answer`: đó là câu trả lời cuối của nhánh văn bản).
  Câu hỏi đi thẳng: mơ hồ thiết bị → `retrieve` → `build_messages` → `stream_ollama`, đúng như nhánh `text` hiện tại.
- `ingestion/jobs.py`: bỏ `_run_record_job`, `_run_extraction`, `_run_catalog`, `_RECORD_DOC_TYPES`; mọi loại tài liệu đi `_run_markdown_job`.
  Sau khi nhúng một tài liệu `qtkd`, gọi `knowledge.procedure.ensure_procedure` (best-effort như cũ, lỗi ghi vào `ingest_error`) để QTKĐ mới vẫn có dòng `procedure` cho router.
- `db/models.py`: xóa `Extraction`, `ExtractionStatus`, `FACT_KINDS`, `ProcedureFact`, `ProcedureStandard`, `Term`, `Device`, `CalibrationRecord`, `MeasurementPoint`, `RecordField`, `LabStandard`, `Inspector`, `ProcedureCatalog`, `Capability` và mọi relationship trỏ tới chúng.
  Enum `DocumentType` giữ nguyên giá trị (Postgres enum, dòng cũ vẫn đọc được).
- `db/views.py`: chuyển nguyên văn sang `db/migrations/legacy_views.py` (chỉ migration dùng, đóng băng); sửa import trong migration 004, 006, 007, 008, 010, 011, 012, 013, không sửa logic.
- `config/settings.yaml` + schema settings: bỏ `models.llm_intent`, `models.llm_extraction`, `llm.intent`, `llm.extraction`, `query`, và mọi khóa chỉ code đã xóa đọc.
  Chứng minh bằng grep: không khóa bị xóa nào còn được đọc, không khóa còn lại nào mồ côi.
- `evaluation/`: xóa `extract_eval.py`, `extract_section6_eval.py`, `intent_eval.py`, `record_query_eval.py`, `arch_eval.py` cùng tệp vàng `extract_golden*.jsonl`, `intent_golden.jsonl`, `record_query_*.jsonl`.
- `scripts/`: xóa `extract_appendix.py`, `extract_section6.py`, `seed_synthetic_records.py`, `make_record_fixtures.py`, `knowledge_corpus/`, `pittong_records/`.
- `tests/`: xóa test của mã đã xóa; giữ và sửa test của phần còn lại.
  Thêm test: ingestion job gọi `ensure_procedure` cho tài liệu `qtkd` và không gọi cho loại khác; chat stream không còn gọi bộ phân loại intent và `done` không có `branch`/`data`.
  Cập nhật `tests/unit/qa/test_architecture.py` theo danh sách package mới.
- `Makefile`: `check: lint fidelity test-unit`; xóa target `extract-eval`, `extract-section6-eval`, `extract-section6`, `extract-appendix`, `intent-eval`, `record-eval`, `records-fixtures`, `seed-synthetic`, `knowledge-corpus`; sửa `LINT_PATHS`.
- `requirements*.txt`: bỏ thư viện chỉ code đã xóa dùng (chứng minh bằng grep).

Migration `014_drop_knowledge_flow.py`:

- `upgrade`: drop mọi view `v_*` của luồng tri thức/số liệu, rồi drop bảng theo thứ tự phụ thuộc: `record_field`, `measurement_point`, `calibration_record`, `device`, `capability`, `procedure_catalog`, `inspector`, `lab_standard`, `term`, `procedure_standard`, `procedure_fact`, `extraction`; drop enum Postgres chỉ các bảng đó dùng.
  Không đụng `document`, `app_user`, `audit_log`, `quantity`, `unit`, `device_type`, `procedure`.
- `downgrade`: dựng lại đúng lược đồ (rỗng) của revision 013 cho các đối tượng đã drop, dùng `legacy_views.py`.
- Cổng: trên Postgres nháp, `pg_dump --schema-only` sau `upgrade 013` phải trùng với sau `upgrade head` → `downgrade 013`.

Frontend:

- Xóa tab `procedures`, `knowledge`, `data` khỏi `Tab`, `Sidebar`, `App`, `TopBar`; xóa `components/{procedures,knowledge,data}/`, `components/chat/DataResultTable*`, `services/{dataApi,knowledgeApi,reviewApi}*`.
- `SourceExcerpt`, `QuoteTable`, `quoteRows`, `HighlightedMarkdown`, `rehypeHighlightRange`: chỉ xóa nếu không còn nơi dùng sau khi gỡ (kiểm bằng grep).
- `services/liveApi.ts` + store: bỏ xử lý SSE event `data`, `done.branch`/`done.data`; vẫn dùng `done.answer`.
- `store/persistence.ts`: tab đã lưu là `procedures`/`knowledge`/`data` rơi về `chat`; tin nhắn cũ có `data` vẫn hiển thị phần văn bản, không lỗi; có test.
- Modal upload: chỉ còn loại tài liệu RAG xử lý được (`qtkd`, `danh_muc`, `khac`).
- Tab Hướng dẫn và mọi chuỗi UI nhắc tới duyệt tri thức, sổ cái, biên bản phải sửa.

Tài liệu: cập nhật `CLAUDE.md`, `README.md`, `frontend/README.md`, `evaluation/README.md`.
Không sửa tài liệu lịch sử trong `docs/superpowers/` và `docs/experiments/`.

## Pha thực hiện

| Pha | Ai | Nội dung | Commit |
|---|---|---|---|
| 0 | Claude | Nhánh mới, baseline `make check` + gate frontend; khi Docker chạy: baseline `run_eval`, `answer_eval` | - |
| 1 | DeepSeek phiên A | Backend + migration + config + eval + scripts + Makefile + tài liệu | Claude commit sau review |
| 2 | DeepSeek phiên B (song song) | Frontend | Claude commit sau review |
| 3 | Claude | Review từng dòng, chạy cổng, E2E trình duyệt, so `run_eval`/`answer_eval` với baseline | `fix:` nếu có |

DeepSeek không commit, không chạy lệnh git đổi trạng thái (checkout, reset, stash, commit).
Lệnh dài chạy ở tiền cảnh với timeout lớn.

## Cổng nghiệm thu

1. `make check` xanh (lint, fidelity 351/351, unit).
2. `cd frontend && npm run typecheck && npm run lint && npm run test && npm run build` xanh.
3. Diff bất biến ở trên rỗng.
4. Code chạy (ngoài migration cũ và `legacy_views.py`) không còn: `Extraction`, `procedure_fact`, `record_field`, `calibration_record`, `review.queue`, `catalogs`, `plan_route`, `/api/data`, `/api/knowledge`, `/api/extractions`, `/api/records`.
5. Migration: upgrade head trên bản sao DB hiện tại thành công; downgrade trùng lược đồ 013.
6. Docker chạy: `run_eval` recall@5 và MRR trùng baseline; `answer_eval` không giảm.
7. E2E trình duyệt: câu QTKĐ có công thức (KaTeX, chip `[n]`, panel nguồn), câu mơ hồ "áp kế píttông", mở tài liệu gốc, upload `.docx` QTKĐ mới tạo dòng `procedure` và được router ghim đúng file; không còn tab đã gỡ; console sạch.
