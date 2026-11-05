#!/usr/bin/env bash
# Mở đường dẫn công khai tạm thời tới frontend (:3000) bằng Cloudflare Quick Tunnel.
# nginx của frontend đã proxy /api -> api:8080 nên chỉ cần một tunnel, không cần CORS.
# URL dạng https://<ngẫu-nhiên>.trycloudflare.com đổi mỗi lần chạy; Ctrl+C để đóng.
set -euo pipefail

cd "$(dirname "$0")/.."
PORT="${FRONTEND_PORT:-3000}"

command -v cloudflared >/dev/null || { echo "Thiếu cloudflared" >&2; exit 1; }

# Công khai ra internet mà không đăng nhập = ai cũng xoá/tải tài liệu được.
auth="$(grep -E '^AUTH_ENABLED=' .env 2>/dev/null | tail -1 | cut -d= -f2 || true)"
if [ "${auth:-false}" != "true" ] && [ "${ALLOW_OPEN_TUNNEL:-0}" != "1" ]; then
  echo "AUTH_ENABLED chưa bật trong .env - từ chối mở tunnel công khai." >&2
  echo "Đặt AUTH_ENABLED=true + JWT_SECRET_KEY, chạy 'docker compose up -d api', rồi" >&2
  echo "'python -m scripts.create_admin'. (Bỏ qua kiểm tra: ALLOW_OPEN_TUNNEL=1)" >&2
  exit 1
fi

curl -fsS "http://localhost:${PORT}/api/health" >/dev/null \
  || { echo "Frontend/API chưa chạy ở :${PORT} (docker compose up -d)" >&2; exit 1; }

exec cloudflared tunnel --no-autoupdate --url "http://localhost:${PORT}"
