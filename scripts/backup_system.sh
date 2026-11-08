#!/usr/bin/env bash
set -euo pipefail
umask 077
cd /home/hiennt/projects/RAG-TC-DL
set -a
. ./.env
set +a
stamp=$(date +%Y%m%d_%H%M%S)
base=backups/system-$stamp
mkdir -p "$base"
trap 'rm -rf "$base"' ERR
# Consistent PostgreSQL export while services remain available.
docker exec qtkd-postgres pg_dump -U "${POSTGRES_USER:-qtkd_user}" -d "${POSTGRES_DB:-qtkd}" -Fc --no-owner > "$base/postgres.dump"
# SQLite online backup preserves a transactionally consistent formula registry.
python3 - "$base/formula_registry.sqlite3" <<'PY'
import sqlite3, sys
src=sqlite3.connect('file:.formula-registry/registry.sqlite3?mode=ro',uri=True)
dst=sqlite3.connect(sys.argv[1]);src.backup(dst);dst.close();src.close()
PY
# Source documents and extracted assets are kept together.
tar -czf "$base/documents.tar.gz" TC_DL build/spike_a
# Qdrant's own snapshot API yields a consistent copy of each collection.
collections=$(curl -fsS -H "api-key: $QDRANT_API_KEY" http://127.0.0.1:6333/collections | python3 -c 'import json,sys; print(" ".join(x["name"] for x in json.load(sys.stdin)["result"]["collections"]))')
for collection in $collections; do
  snap=$(curl -fsS -X POST -H "api-key: $QDRANT_API_KEY" "http://127.0.0.1:6333/collections/$collection/snapshots" | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["name"])')
  curl -fsS -H "api-key: $QDRANT_API_KEY" "http://127.0.0.1:6333/collections/$collection/snapshots/$snap" -o "$base/qdrant-$collection.snapshot"
  curl -fsS -X DELETE -H "api-key: $QDRANT_API_KEY" "http://127.0.0.1:6333/collections/$collection/snapshots/$snap" >/dev/null
done
(cd "$base" && sha256sum postgres.dump formula_registry.sqlite3 documents.tar.gz qdrant-*.snapshot > SHA256SUMS)
chmod -R go-rwx "$base"
# Keep the newest 14 complete system backups.
find backups -maxdepth 1 -type d -name 'system-*' | sort -r | tail -n +15 | while IFS= read -r old; do rm -rf -- "$old"; done
printf 'Complete backup: %s\n' "$base"
