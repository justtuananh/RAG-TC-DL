#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run.sh — Bật BACKEND (api_server.py :8080) + FRONTEND (React :5173) cho QTKĐ RAG.
#
# Tương đương run_all.bat (Windows) cho macOS/Linux, nhưng:
#   • tự chọn venv CÓ fastapi (ưu tiên ../kotaemon/.venv, fallback ./.venv)
#   • tự dựng dịch vụ phụ thuộc qua Docker nếu thiếu (qdrant/embedding/reranker)
#   • đảm bảo Ollama đang chạy
#   • dọn tiến trình con khi Ctrl-C
#
# Lưu ý: frontend hiện MOCK-ONLY (chưa gọi /api) — backend vẫn bật để test SSE
# trực tiếp và sẵn sàng khi nối UI. Xem frontend/README.md.
#
# Cách dùng:
#   ./run.sh                 # bật full: (docker services nếu cần) + api + frontend dev
#   ./run.sh --frontend-only # chỉ frontend dev :5173
#   ./run.sh --no-docker     # bỏ qua dựng docker services (api sẽ lỗi /chat nếu services down)
#   ./run.sh --index         # re-index vào Qdrant sau khi services sẵn sàng
#   ./run.sh --build         # frontend = build + vite preview (thay vì dev)
#   OLLAMA_MODEL=qwen2.5:7b ./run.sh    # đổi model
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ── Cấu hình (override qua env) ──────────────────────────────────────────────
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:1.5b}"
API_PORT="${API_PORT:-8080}"
FE_PORT="${FE_PORT:-5173}"
export EMBED_URL="${EMBED_URL:-http://localhost:8010/v1/embeddings}"
export RERANK_URL="${RERANK_URL:-http://localhost:8011/v1/rerank}"
export QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
export OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434/api/chat}"
export OLLAMA_MODEL API_PORT

FRONTEND_ONLY=0; USE_DOCKER=auto; DO_INDEX=0; FE_MODE=dev
for a in "$@"; do case "$a" in
  --frontend-only) FRONTEND_ONLY=1 ;;
  --no-docker)     USE_DOCKER=no ;;
  --with-docker)   USE_DOCKER=yes ;;
  --index)         DO_INDEX=1 ;;
  --build)         FE_MODE=build ;;
  -h|--help) awk 'NR==1{next} /^#/{print; next} {exit}' "$0"; exit 0 ;;
  *) echo "Tham số lạ: $a (—help để xem)"; exit 1 ;;
esac; done

LOGDIR="$ROOT/logs/run"; mkdir -p "$LOGDIR"
API_LOG="$LOGDIR/api.log"; FE_LOG="$LOGDIR/frontend.log"
PIDS=()

c() { printf "\033[%sm%s\033[0m\n" "$1" "$2"; }   # màu
info(){ c "1;36" "▶ $*"; }; ok(){ c "1;32" "✓ $*"; }; warn(){ c "1;33" "⚠ $*"; }; err(){ c "1;31" "✗ $*"; }

cleanup() {
  echo; info "Đang dừng tiến trình con…"
  for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null || true; done
  warn "Docker services (nếu đã bật) VẪN chạy — dừng bằng: docker compose down  (hoặc make down)"
}
trap cleanup EXIT INT TERM

up() { curl -s -o /dev/null --max-time 2 "$1" 2>/dev/null; }   # 0 = có phản hồi HTTP

# ── 1) Frontend deps ─────────────────────────────────────────────────────────
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  info "Cài deps frontend (npm install)…"; ( cd "$ROOT/frontend" && npm install ) || { err "npm install lỗi"; exit 1; }
fi

start_frontend() {
  if [ "$FE_MODE" = build ]; then
    info "Build frontend…"; ( cd "$ROOT/frontend" && npm run build ) || { err "build lỗi"; exit 1; }
    info "Serve (vite preview) :${FE_PORT}…"
    ( cd "$ROOT/frontend" && npm run preview -- --port "$FE_PORT" ) >"$FE_LOG" 2>&1 &
  else
    info "Frontend dev :${FE_PORT}…"
    ( cd "$ROOT/frontend" && npm run dev -- --port "$FE_PORT" ) >"$FE_LOG" 2>&1 &
  fi
  PIDS+=($!)
}

if [ "$FRONTEND_ONLY" = 1 ]; then
  start_frontend
  ok "Frontend: http://localhost:$FE_PORT   (log: $FE_LOG)"
  info "Ctrl-C để dừng."; wait; exit 0
fi

# ── 2) Chọn Python có fastapi (cho api_server.py) ────────────────────────────
PY=""
for cand in "$ROOT/../kotaemon/.venv/bin/python" "$ROOT/.venv/bin/python"; do
  if [ -x "$cand" ] && "$cand" -c 'import fastapi, uvicorn' >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
  err "Không tìm thấy venv có fastapi+uvicorn (thử ../kotaemon/.venv hoặc ./.venv)."
  err "Cài: <venv>/bin/pip install fastapi uvicorn"; exit 1
fi
ok "Python API: $PY"

# ── 3) Ollama ────────────────────────────────────────────────────────────────
if ! up "http://localhost:11434/"; then
  if command -v ollama >/dev/null 2>&1; then
    info "Khởi động Ollama (ollama serve)…"; nohup ollama serve >"$LOGDIR/ollama.log" 2>&1 & PIDS+=($!)
    for _ in $(seq 1 20); do up "http://localhost:11434/" && break; sleep 1; done
  fi
fi
if up "http://localhost:11434/"; then
  ok "Ollama :11434"
  if command -v ollama >/dev/null 2>&1 && ! ollama list 2>/dev/null | grep -q "${OLLAMA_MODEL%%:*}"; then
    warn "Model '$OLLAMA_MODEL' chưa có — kéo về (có thể lâu)…"; ollama pull "$OLLAMA_MODEL" || warn "pull lỗi (tiếp tục)"
  fi
else
  warn "Ollama :11434 không phản hồi — câu trả lời LLM sẽ lỗi tới khi Ollama chạy."
fi

# ── 4) Dịch vụ phụ thuộc: Qdrant :6333 + embedding :8010 + reranker :8011 ─────
services_up() { up "$QDRANT_URL/" && up "http://localhost:8010/" && up "http://localhost:8011/"; }
if services_up; then
  ok "Qdrant + embedding + reranker đã chạy."
else
  if [ "$USE_DOCKER" != no ] && command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    info "Dựng dịch vụ phụ thuộc qua Docker (lần đầu BUILD + tải model ~2.8GB, có thể 10–20')…"
    docker compose up -d --build qdrant embedding reranker || warn "docker compose lỗi"
    info "Chờ services sẵn sàng…"
    for _ in $(seq 1 120); do services_up && break; sleep 3; done
    services_up && ok "Services sẵn sàng." || warn "Services chưa sẵn sàng (xem 'docker compose logs')."
  else
    warn "Qdrant/embedding/reranker đang DOWN và không dựng được qua Docker"
    warn "(docker không chạy hoặc --no-docker). API sẽ bật nhưng /api/chat/stream lỗi 'Lỗi tìm kiếm' tới khi có services."
  fi
fi

# ── 5) (tuỳ chọn) Re-index ───────────────────────────────────────────────────
if [ "$DO_INDEX" = 1 ]; then
  if services_up; then
    info "Re-index build/spike_a/ vào Qdrant…"; "$PY" -m index.embed_store --force || warn "index lỗi"
  else
    warn "Bỏ qua --index: services chưa sẵn sàng."
  fi
fi

# ── 6) Backend api_server.py :$API_PORT ──────────────────────────────────────
info "Backend api_server.py :$API_PORT (model=$OLLAMA_MODEL)…"
"$PY" "$ROOT/api_server.py" >"$API_LOG" 2>&1 & PIDS+=($!)
for _ in $(seq 1 30); do up "http://localhost:$API_PORT/api/health" && break; sleep 1; done
up "http://localhost:$API_PORT/api/health" && ok "API: http://localhost:$API_PORT/api/health" \
  || warn "API chưa phản hồi (xem $API_LOG)."

# ── 7) Frontend ──────────────────────────────────────────────────────────────
start_frontend

echo
ok  "API:      http://localhost:$API_PORT   (log: $API_LOG)"
ok  "Frontend: http://localhost:$FE_PORT   (log: $FE_LOG)"
info "Ctrl-C để dừng cả hai. Log realtime: tail -f $API_LOG $FE_LOG"
wait
