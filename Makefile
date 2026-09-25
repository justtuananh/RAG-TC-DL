.PHONY: up down logs pull-model index rebuild status eval answer-eval answer-eval-dev lint lint-all fmt fidelity test-unit check test-int smoke test test-ruby db-upgrade db-downgrade db-backup migrate-documents db-check seed-knowledge generate-procedures extract-eval extract-section6-eval extract-section6 extract-appendix records-fixtures seed-synthetic intent-eval knowledge-corpus

# ── Khởi động ────────────────────────────────────────────────────────────────
up:
	docker compose up -d --build

# Chỉ start (không rebuild image):
start:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

status:
	docker compose ps

# ── Setup lần đầu ────────────────────────────────────────────────────────────

# Tải LLM model vào Ollama (~940MB cho 1.5b, ~4.7GB cho 7b)
pull-model:
	docker compose exec ollama ollama pull qwen2.5:1.5b

pull-model-3b:
	docker compose exec ollama ollama pull qwen2.5:3b

pull-model-7b:
	docker compose exec ollama ollama pull qwen2.5:7b

# Index tất cả .md trong build/spike_a/ vào Qdrant — incremental (skip file đã có)
index:
	docker compose --profile tools run --rm indexer

# Re-index toàn bộ (xóa và tạo lại từ đầu)
reindex:
	docker compose --profile tools run --rm indexer python -m index.embed_store --force

# ── Maintenance ───────────────────────────────────────────────────────────────

# Build lại toàn bộ images (khi sửa code hoặc Dockerfile)
rebuild:
	docker compose build --no-cache
	docker compose up -d

# Xoá toàn bộ data (cẩn thận: mất Qdrant collection + Ollama models đã tải)
clean-volumes:
	docker compose down -v

# ── Dev helpers ───────────────────────────────────────────────────────────────

# Chạy eval retrieval (cần kotaemon/.venv — chạy trên host, không phải Docker)
eval:
	/Users/mac/Desktop/AI4TA/kotaemon/.venv/bin/python -m eval.run_eval --mode hybrid

# Eval CHẤT LƯỢNG CÂU TRẢ LỜI (coverage/citation/refusal/ảo giác) — so 1.5b vs 7b.
# Cần 4 service + đã pull cả 2 model (make pull-model && make pull-model-7b).
answer-eval:
	/Users/mac/Desktop/AI4TA/kotaemon/.venv/bin/python -m eval.answer_eval --model qwen2.5:1.5b,qwen2.5:7b

# Chỉ 1.5b (dev nhanh, không cần pull 7b).
answer-eval-dev:
	/Users/mac/Desktop/AI4TA/kotaemon/.venv/bin/python -m eval.answer_eval --model qwen2.5:1.5b

# Smoke test embedding service
test-embed:
	curl -s localhost:8010/v1/embeddings \
	  -H "Content-Type: application/json" \
	  -d '{"input":["test"],"model":"model"}' \
	  | python3 -c "import json,sys; d=json.load(sys.stdin); print('dims:', len(d['data'][0]['embedding']))"

# Smoke test Qdrant collection
test-qdrant:
	curl -s localhost:6333/collections/qtkd_rag | python3 -m json.tool | grep vectors_count

# ── Harness QA/Test (self-contained: dùng .venv-dev, KHÔNG cần kotaemon/.venv) ──
# PY override được:  make check PY=/đường/dẫn/python
PY ?= .venv-dev/bin/python

# Lint + format-check CHỈ code harness (không định dạng lại source hiện có).
lint:
	$(PY) -m ruff check tests scripts
	$(PY) -m ruff format --check tests scripts

# Tuỳ chọn: quét toàn repo tìm lỗi đúng/sai (pyflakes) — có thể lộ vài lỗi sẵn có.
lint-all:
	$(PY) -m ruff check --select F .

# Tự sửa + định dạng code harness.
fmt:
	$(PY) -m ruff format tests scripts
	$(PY) -m ruff check --fix tests scripts

# Guard độ trung thực công thức (rủi ro #1) — đọc artifact đã commit, không cần service.
fidelity:
	$(PY) scripts/check_fidelity.py

# Eval trích xuất bằng luật trên tập vàng (spec Sprint 4): precision ≥ 0,95, recall ≥ 0,80.
extract-eval:
	$(PY) -m eval.extract_eval

# Eval trích xuất §6 bằng LLM (spec Sprint 5): precision ≥ 0,90 + 0 bịa số.
# Mặc định chạy client kịch bản (tất định, không cần Ollama); --live để đo model thật.
extract-section6-eval:
	$(PY) -m eval.extract_section6_eval

# Eval định tuyến chat lai văn bản + số liệu (spec Sprint 9): intent ≥ 0,90,
# 0 ô số không nguồn, câu hỏi văn bản không lạc nhánh số liệu.
intent-eval:
	$(PY) -m eval.intent_eval

# Unit test (mock toàn bộ I/O) — chạy mọi nơi, không cần Docker.
test-unit:
	$(PY) -m pytest -m unit tests/unit

# Cổng cloud-feasible = đúng những gì CI chạy ("xanh local ⇒ xanh CI").
check: lint fidelity extract-eval extract-section6-eval intent-eval test-unit

# Tầng integration (cần `make up` trước): chờ service rồi chạy test thật.
test-int:
	$(PY) scripts/healthcheck.py --timeout 120
	$(PY) -m pytest -m integration tests/integration

# Smoke end-to-end: chờ service rồi hỏi 1 câu qua cả pipeline + LLM.
smoke:
	$(PY) scripts/healthcheck.py --timeout 120
	$(PY) -m pytest -m integration tests/integration/test_smoke_answer.py

# Tầng Ruby (cần Ruby + gem mathtype_to_mathml): OLE .bin → LaTeX. Tự skip nếu thiếu.
test-ruby:
	$(PY) -m pytest -m ruby tests/ruby

# Tất cả test chạy được trên máy (unit + integration). `make eval` vẫn là eval chuẩn.
test: test-unit test-int

# ── Database Management ───────────────────────────────────────────────────────

# Run pending migrations
db-upgrade:
	docker compose run --rm --no-deps api python scripts/migrate.py upgrade head

# Downgrade all migrations
db-downgrade:
	docker compose run --rm --no-deps api python scripts/migrate.py downgrade base

# Backup database
db-backup:
	@mkdir -p backups
	docker compose exec -T postgres pg_dump -U $${POSTGRES_USER:-qtkd_user} -d $${POSTGRES_DB:-qtkd} > backups/qtkd_db_$$(date +%Y%m%d_%H%M%S).sql

migrate-documents:
	docker compose run --rm --no-deps api python scripts/migrate_documents.py --apply

# Seed khung khái niệm đo lường (quantity/unit/device_type) — idempotent.
seed-knowledge:
	docker compose run --rm --no-deps api python scripts/seed_knowledge.py

# Sinh procedure cho QTKĐ đang có; mặc định dry-run, thêm --apply để ghi.
generate-procedures:
	docker compose run --rm --no-deps api python scripts/generate_procedures.py --apply

# Trích xuất §6 bằng LLM cho QTKĐ đang có (batch ngoài giờ); mặc định dry-run,
# thêm --apply để ghi pending. Cần Ollama + model đã pull; thất bại an toàn.
extract-section6:
	docker compose run --rm --no-deps api python scripts/extract_section6.py --apply

# Trích xuất Phụ lục A (sơ đồ trường biên bản) cho QTKĐ; mặc định dry-run,
# thêm --apply để ghi pending. Người duyệt xác nhận rồi records.template mới đọc.
extract-appendix:
	docker compose run --rm --no-deps api python scripts/extract_appendix.py --apply

# Sinh lại tệp mẫu hồ sơ (docx/xlsx) đã làm sạch cho test Sprint 7.
records-fixtures:
	$(PY) scripts/make_record_fixtures.py

knowledge-corpus: ; $(PY) -m scripts.knowledge_corpus.build

# Seed bộ dữ liệu kiểm định tổng hợp (đã duyệt) cho tab Dữ liệu/thử hiệu năng.
# Mặc định 10.000 hồ sơ / 1.000 thiết bị; chạy lại gỡ và dựng lại (idempotent).
seed-synthetic:
	docker compose run --rm --no-deps api python scripts/seed_synthetic_records.py --count 10000 --devices 1000 --apply

# Test migrations up and down on clean database
db-check:
	@echo "Testing database migrations..."
	@docker compose up -d postgres
	@docker compose run --rm --no-deps api python scripts/migrate.py upgrade head
	@docker compose run --rm --no-deps api python scripts/migrate.py downgrade base
	@echo "✓ Database migrations verified"
