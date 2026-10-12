.PHONY: up down logs pull-model index rebuild status eval answer-eval lint lint-all fmt fidelity test-unit check test-int smoke test test-ruby db-upgrade db-downgrade db-backup migrate-documents db-check seed-knowledge generate-procedures

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

# Tải LLM model vào Ollama (~4.7GB cho qwen2.5:7b-instruct)
# Model chat mặc định của config/settings.yaml (models.llm_chat).
pull-model:
	docker compose exec ollama ollama pull $$($(PY) -m core.settings_loader get models.llm_chat)

# Index tất cả .md trong build/spike_a/ vào Qdrant — incremental (skip file đã có)
index:
	docker compose --profile tools run --rm indexer

# Re-index toàn bộ (xóa và tạo lại từ đầu)
reindex:
	docker compose --profile tools run --rm indexer python -m vectorstore.index --force

# ── Maintenance ───────────────────────────────────────────────────────────────

# Build lại toàn bộ images (khi sửa code hoặc Dockerfile)
rebuild:
	docker compose build --no-cache
	docker compose up -d

# Xoá toàn bộ data (cẩn thận: mất Qdrant collection + Ollama models đã tải)
clean-volumes:
	docker compose down -v

# ── Dev helpers ───────────────────────────────────────────────────────────────

# Chạy eval retrieval (chạy trên host, cần 4 service Docker đang chạy)
eval:
	$(PY) -m evaluation.run_eval --mode hybrid

# Eval CHẤT LƯỢNG CÂU TRẢ LỜI (coverage/citation/refusal/ảo giác) với models.llm_chat.
# Cần 4 service + đã pull model (make pull-model). So model khác: --model a,b.
answer-eval:
	$(PY) -m evaluation.answer_eval

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

# Các package nguồn + tests được lint/định dạng.
LINT_PATHS = tests scripts query evaluation core api embedding vectorstore reranking retrieval llm scoring ui formula_registry

# Lint + format-check CHỈ code harness (không định dạng lại source hiện có).
lint:
	$(PY) -m ruff check $(LINT_PATHS)
	$(PY) -m ruff format --check $(LINT_PATHS)

# Tuỳ chọn: quét toàn repo tìm lỗi đúng/sai (pyflakes) — có thể lộ vài lỗi sẵn có.
lint-all:
	$(PY) -m ruff check --select F .

# Tự sửa + định dạng code harness.
fmt:
	$(PY) -m ruff format $(LINT_PATHS)
	$(PY) -m ruff check --fix $(LINT_PATHS)

# Guard độ trung thực công thức (rủi ro #1) — đọc artifact đã commit, không cần service.
fidelity:
	$(PY) scripts/check_fidelity.py

# Unit test (mock toàn bộ I/O) — chạy mọi nơi, không cần Docker.
test-unit:
	$(PY) -m pytest -m unit tests/unit

# Cổng cloud-feasible = đúng những gì CI chạy ("xanh local ⇒ xanh CI").
check: lint fidelity test-unit

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
	docker compose run --rm --no-deps api python -m scripts.migrate upgrade head

# Downgrade all migrations
db-downgrade:
	docker compose run --rm --no-deps api python -m scripts.migrate downgrade base

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

# Test migrations up and down on clean database
db-check:
	@echo "Testing database migrations..."
	@docker compose up -d postgres
	@docker compose run --rm --no-deps api python -m scripts.migrate upgrade head
	@docker compose run --rm --no-deps api python -m scripts.migrate downgrade base
	@echo "✓ Database migrations verified"

# ── Công thức: tạo nháp chờ duyệt cho tài liệu đã có (không tự phê duyệt) ───────
.PHONY: formula-drafts formula-drafts-docker
formula-drafts:
	$(PY) -m formula_registry TC_DL/*.docx --report build/formula-review/backfill-latest.json

formula-drafts-docker:
	docker compose exec api sh -c 'python -m formula_registry TC_DL/*.docx --report build/spike_a/formula-review-backfill.json'
