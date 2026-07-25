#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required for the media worker}"
: "${CELERY_BROKER_URL:?CELERY_BROKER_URL is required for the media worker}"
: "${STORAGE_PROVIDER:?STORAGE_PROVIDER is required for the media worker}"

case "${STORAGE_PROVIDER}" in
  s3|fake) ;;
  *) echo "Invalid STORAGE_PROVIDER." >&2; exit 2 ;;
esac

python -m flask worker-config-check
exec python -m celery \
  -A app.celery_worker:celery_app worker \
  -Q media_image,media_video,storage_cleanup,bulk_download \
  --hostname="starx-media@%h" \
  --loglevel=INFO \
  --concurrency=2
