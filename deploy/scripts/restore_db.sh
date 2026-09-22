#!/usr/bin/env bash
# Restores a farmstore PostgreSQL backup created by backup_db.sh.
#
# Usage:
#   ./deploy/scripts/restore_db.sh /path/to/farmstore-farmstore_prod-20260101-020000.sql.gz
#
# WARNING: this drops and recreates the target database. Make sure you're
# pointing at the right one before running this.
#
# Reads DB credentials from .env via grep (not `source`) for the same
# reason as backup_db.sh -- unrelated values with spaces must not break
# variable parsing.

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup-file.sql.gz>" >&2
    exit 1
fi

BACKUP_FILE="$1"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"

read_env_var() {
    local key="$1"
    grep -E "^${key}=" "$ENV_FILE" | tail -1 | cut -d '=' -f2-
}

DB_NAME="$(read_env_var DB_NAME)"
DB_USER="$(read_env_var DB_USER)"
DB_PASSWORD="$(read_env_var DB_PASSWORD)"
DB_HOST="$(read_env_var DB_HOST)"
DB_PORT="$(read_env_var DB_PORT)"

read -r -p "This will DROP and recreate database '$DB_NAME'. Continue? [y/N] " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Aborted."
    exit 1
fi

export PGPASSWORD="$DB_PASSWORD"
dropdb -h "${DB_HOST:-127.0.0.1}" -p "${DB_PORT:-5432}" -U "$DB_USER" "$DB_NAME"
createdb -h "${DB_HOST:-127.0.0.1}" -p "${DB_PORT:-5432}" -U "$DB_USER" "$DB_NAME"
gunzip -c "$BACKUP_FILE" | psql -h "${DB_HOST:-127.0.0.1}" -p "${DB_PORT:-5432}" -U "$DB_USER" "$DB_NAME"

echo "Restore complete."
