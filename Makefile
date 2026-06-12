.PHONY: up down logs pull-model index rebuild status eval answer-eval answer-eval-dev lint lint-all fmt fidelity test-unit check test-int smoke test test-ruby

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

pull-model-7b:
	docker compose exec ollama ollama pull qwen2.5:7b

# Index tất cả .md trong build/spike_a/ vào Qdrant (chạy 1 lần hoặc khi thêm doc)
index:
	docker compose --profile tools run --rm indexer

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
