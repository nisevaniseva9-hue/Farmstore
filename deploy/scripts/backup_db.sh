#!/usr/bin/env bash
# Simple PostgreSQL backup script for farmstore.
#
# Usage:
#   ./deploy/scripts/backup_db.sh
#
# Suggested cron entry (daily at 2am, keeping backups in /home/deploy/backups):
#   0 2 * * * /home/deploy/farmstore/deploy/scripts/backup_db.sh >> /home/deploy/backups/backup.log 2>&1
#
# Reads DB credentials from .env in the project root. Only the DB_* keys
# are read (via grep, not `source`) so unrelated values in .env that
# contain spaces (e.g. FARM_NAME=Farm Fresh) can't break this script.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

if [ ! -f "$ENV_FILE" ]; then
    echo "Could not find .env at $ENV_FILE" >&2
    exit 1
fi

read_env_var() {
    local key="$1"
    grep -E "^${key}=" "$ENV_FILE" | tail -1 | cut -d '=' -f2-
}

DB_NAME="$(read_env_var DB_NAME)"
DB_USER="$(read_env_var DB_USER)"
DB_PASSWORD="$(read_env_var DB_PASSWORD)"
DB_HOST="$(read_env_var DB_HOST)"
DB_PORT="$(read_env_var DB_PORT)"

if [ -z "$DB_NAME" ] || [ -z "$DB_USER" ]; then
    echo "DB_NAME or DB_USER missing from $ENV_FILE" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"
OUTPUT_FILE="$BACKUP_DIR/farmstore-${DB_NAME}-${TIMESTAMP}.sql.gz"

PGPASSWORD="$DB_PASSWORD" pg_dump \
    -h "${DB_HOST:-127.0.0.1}" \
    -p "${DB_PORT:-5432}" \
    -U "$DB_USER" \
    "$DB_NAME" | gzip > "$OUTPUT_FILE"

echo "Backup written to $OUTPUT_FILE"

# Keep the last 14 daily backups, delete anything older.
find "$BACKUP_DIR" -name "farmstore-${DB_NAME}-*.sql.gz" -mtime +14 -delete
