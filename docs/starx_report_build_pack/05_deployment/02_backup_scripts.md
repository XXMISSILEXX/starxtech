# Backup Scripts

## scripts/backup_db.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/starx-report"
BACKUP_DIR="/opt/backups/starx-report/db"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"
cd "$APP_DIR"

set -a
source .env
set +a

pg_dump "$DATABASE_URL" | gzip > "$BACKUP_DIR/starx_report_db_${TIMESTAMP}.sql.gz"

# keep 30 latest backups
ls -1t "$BACKUP_DIR"/*.sql.gz | tail -n +31 | xargs -r rm --

echo "DB backup done: $BACKUP_DIR/starx_report_db_${TIMESTAMP}.sql.gz"
```

## scripts/backup_uploads.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/starx-report"
BACKUP_DIR="/opt/backups/starx-report/uploads"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"
cd "$APP_DIR"

set -a
source .env
set +a

tar -czf "$BACKUP_DIR/starx_report_uploads_${TIMESTAMP}.tar.gz" -C "$(dirname "$UPLOAD_ROOT")" "$(basename "$UPLOAD_ROOT")"

# keep 30 latest backups
ls -1t "$BACKUP_DIR"/*.tar.gz | tail -n +31 | xargs -r rm --

echo "Uploads backup done: $BACKUP_DIR/starx_report_uploads_${TIMESTAMP}.tar.gz"
```

## scripts/restore_db.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 /path/to/backup.sql.gz"
  exit 1
fi

APP_DIR="/opt/starx-report"
BACKUP_FILE="$1"

cd "$APP_DIR"
set -a
source .env
set +a

gunzip -c "$BACKUP_FILE" | psql "$DATABASE_URL"

echo "DB restore done from: $BACKUP_FILE"
```

## Permission

```bash
chmod +x scripts/backup_db.sh scripts/backup_uploads.sh scripts/restore_db.sh
```
