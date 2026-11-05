#!/usr/bin/env bash
# Mở đường dẫn công khai tạm thời tới frontend (:3000) bằng Cloudflare Quick Tunnel.
# nginx của frontend đã proxy /api -> api:8080 nên chỉ cần một tunnel, không cần CORS.
# URL dạng https://<ngẫu-nhiên>.trycloudflare.com đổi mỗi lần chạy; Ctrl+C để đóng.
set -euo pipefail

cd "$(dirname "$0")/.."
PORT="${FRONTEND_PORT:-3000}"

command -v cloudflared >/dev/null || { echo "Thiếu cloudflared" >&2; exit 1; }

# Chưa có đăng nhập: ai có link cũng xoá/tải tài liệu được. Chỉ chia sẻ link cho người tin cậy.
echo "Cảnh báo: AUTH tắt - ai có link đều có quyền quản trị." >&2

curl -fsS "http://localhost:${PORT}/api/health" >/dev/null \
  || { echo "Frontend/API chưa chạy ở :${PORT} (docker compose up -d)" >&2; exit 1; }

exec cloudflared tunnel --no-autoupdate --url "http://localhost:${PORT}"
