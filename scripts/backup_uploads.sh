#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/starx-report}"
BACKUP_DIR="${BACKUP_DIR:-/opt/backups/starx-report/uploads}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RETENTION_COUNT="${RETENTION_COUNT:-30}"

mkdir -p "$BACKUP_DIR"
cd "$APP_DIR"

set -a
source .env
set +a

UPLOAD_ROOT="${UPLOAD_ROOT:-$APP_DIR/storage/uploads}"
OUTPUT_FILE="$BACKUP_DIR/starx_report_uploads_${TIMESTAMP}.tar.gz"

if [ ! -d "$UPLOAD_ROOT" ]; then
  echo "Upload folder does not exist: $UPLOAD_ROOT" >&2
  exit 1
fi

tar -czf "$OUTPUT_FILE" -C "$(dirname "$UPLOAD_ROOT")" "$(basename "$UPLOAD_ROOT")"

ls -1t "$BACKUP_DIR"/*.tar.gz 2>/dev/null | tail -n +"$((RETENTION_COUNT + 1))" | xargs -r rm --

echo "Uploads backup done: $OUTPUT_FILE"
