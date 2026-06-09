.PHONY: up down logs pull-model index rebuild status eval

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

# Smoke test embedding service
test-embed:
	curl -s localhost:8010/v1/embeddings \
	  -H "Content-Type: application/json" \
	  -d '{"input":["test"],"model":"model"}' \
	  | python3 -c "import json,sys; d=json.load(sys.stdin); print('dims:', len(d['data'][0]['embedding']))"

# Smoke test Qdrant collection
test-qdrant:
	curl -s localhost:6333/collections/qtkd_rag | python3 -m json.tool | grep vectors_count

# ── Monitoring ────────────────────────────────────────────────────────────────

# Khởi động Elastic stack (ES + Kibana + Filebeat)
mon-up:
	docker compose -f docker-compose.monitoring.yml up -d

mon-down:
	docker compose -f docker-compose.monitoring.yml down

mon-logs:
	docker compose -f docker-compose.monitoring.yml logs -f

# Tạo Kibana data views + dashboard (chạy 1 lần sau khi Kibana sẵn sàng)
kibana-setup:
	python3 elastic/setup_kibana.py

# Xem 20 dòng log RAG cuối (pretty-print JSON)
tail-logs:
	python3 -c "import pathlib,json; f=pathlib.Path('logs/rag_app.jsonl'); lines=f.read_text(encoding='utf-8').splitlines()[-20:] if f.exists() else []; [print(json.dumps(json.loads(l),ensure_ascii=False,indent=2)) for l in lines]"
