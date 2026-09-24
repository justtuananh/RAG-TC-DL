#!/bin/bash
# Database restore script for PostgreSQL

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 backups/qtkd_db_20260922_210627.sql"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Get database credentials from environment or use defaults
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-qtkd}"
DB_USER="${POSTGRES_USER:-qtkd_user}"

echo "Restoring database $DB_NAME from $BACKUP_FILE..."
echo "WARNING: This will overwrite all data in $DB_NAME"
read -p "Are you sure? (type 'yes' to continue): " -r CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

# Create a temporary database to restore into, then swap
TEMP_DB="${DB_NAME}_restore_temp"

echo "Creating temporary database $TEMP_DB..."
PGPASSWORD="$POSTGRES_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "postgres" \
    --no-password \
    -c "CREATE DATABASE $TEMP_DB;"

echo "Restoring from $BACKUP_FILE into $TEMP_DB..."
PGPASSWORD="$POSTGRES_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$TEMP_DB" \
    --no-password \
    < "$BACKUP_FILE"

echo "Swapping databases..."
PGPASSWORD="$POSTGRES_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "postgres" \
    --no-password \
    -c "ALTER DATABASE $DB_NAME RENAME TO ${DB_NAME}_old; ALTER DATABASE $TEMP_DB RENAME TO $DB_NAME;"

echo "Removing old database ${DB_NAME}_old..."
PGPASSWORD="$POSTGRES_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "postgres" \
    --no-password \
    -c "DROP DATABASE ${DB_NAME}_old;"

echo "Restore completed successfully!"
