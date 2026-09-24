#!/bin/bash
# Database backup script for PostgreSQL

set -e

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/qtkd_db_$TIMESTAMP.sql"

# Get database credentials from environment or use defaults
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-qtkd}"
DB_USER="${POSTGRES_USER:-qtkd_user}"

mkdir -p "$BACKUP_DIR"

echo "Backing up database $DB_NAME from $DB_HOST:$DB_PORT..."

PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-password \
    --format=plain \
    > "$BACKUP_FILE"

echo "Backup completed: $BACKUP_FILE"
echo "Size: $(du -h "$BACKUP_FILE" | cut -f1)"

# Keep only the last 10 backups
echo "Cleaning old backups (keeping last 10)..."
ls -t "$BACKUP_DIR"/qtkd_db_*.sql | tail -n +11 | xargs -r rm
