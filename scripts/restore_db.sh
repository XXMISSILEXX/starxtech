#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /path/to/starx_report_db_YYYYmmdd_HHMMSS.sql.gz" >&2
  exit 1
fi

APP_DIR="${APP_DIR:-/opt/starx-report}"
BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file does not exist: $BACKUP_FILE" >&2
  exit 1
fi

cd "$APP_DIR"

set -a
source .env
set +a

gunzip -c "$BACKUP_FILE" | psql "$DATABASE_URL"

echo "DB restore done from: $BACKUP_FILE"
