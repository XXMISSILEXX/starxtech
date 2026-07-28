#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/starx-report}"
BACKUP_DIR="${BACKUP_DIR:-/opt/backups/starx-report/db}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RETENTION_COUNT="${RETENTION_COUNT:-30}"

mkdir -p "$BACKUP_DIR"
cd "$APP_DIR"

if [ -z "${DATABASE_URL:-}" ] && [ -n "${DATABASE_URL_FILE:-}" ]; then
  DATABASE_URL="$(cat "$DATABASE_URL_FILE")"
  export DATABASE_URL
fi

: "${DATABASE_URL:?DATABASE_URL or DATABASE_URL_FILE is required}"

OUTPUT_FILE="$BACKUP_DIR/starx_report_db_${TIMESTAMP}.sql.gz"
pg_dump "$DATABASE_URL" | gzip > "$OUTPUT_FILE"

ls -1t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | tail -n +"$((RETENTION_COUNT + 1))" | xargs -r rm --

echo "DB backup done: $OUTPUT_FILE"
