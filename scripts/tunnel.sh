#!/usr/bin/env bash
# Mở đường dẫn công khai tạm thời tới frontend (:3000) bằng Cloudflare Quick Tunnel.
# nginx của frontend đã proxy /api -> api:8080 nên chỉ cần một tunnel, không cần CORS.
# URL dạng https://<ngẫu-nhiên>.trycloudflare.com đổi mỗi lần chạy; Ctrl+C để đóng.
set -euo pipefail

cd "$(dirname "$0")/.."
PORT="${FRONTEND_PORT:-3000}"

command -v cloudflared >/dev/null || { echo "Thiếu cloudflared" >&2; exit 1; }

# Đăng nhập bật mặc định (AUTH_ENABLED=true). Nếu ai đó tắt nó, ai có link cũng có quyền quản trị.
if [ "${AUTH_ENABLED:-true}" = "false" ]; then
  echo "Cảnh báo: AUTH_ENABLED=false - ai có link đều có quyền quản trị." >&2
fi

curl -fsS "http://localhost:${PORT}/api/health" >/dev/null \
  || { echo "Frontend/API chưa chạy ở :${PORT} (docker compose up -d)" >&2; exit 1; }

exec cloudflared tunnel --no-autoupdate --url "http://localhost:${PORT}"
