#!/usr/bin/env bash
set -Eeuo pipefail
cd "$HOME/Documents/Construction_Management"
source .venv/bin/activate
set -a; source .env.s3-local; set +a
export FLASK_APP=wsgi.py APP_ENV=local FLASK_DEBUG=true SESSION_COOKIE_SECURE=false
export DATABASE_URL="$(sudo cat /srv/construction_relation_management/secrets/database_url)"
export CELERY_BROKER_URL=redis://127.0.0.1:6379/0
export CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
export RATELIMIT_STORAGE_URI=redis://127.0.0.1:6379/2

step(){ printf '\n==== %s ====\n' "$1"; }
step git
git status --short
git diff --check
step compile
python -m compileall -q app tests migrations
step javascript
if grep -q '"build:heic-preview"' package.json; then npm run build:heic-preview; fi
npm test
find app/static/js -type f -name '*.js' -print0 | xargs -0 -n1 node --check
step pytest
PYTHONWARNINGS=error pytest -q -ra
step dependencies
pip check
step database
flask db current
flask db heads
step security
flask security-audit
step runtime
redis-cli -n 0 ping
curl -fsS "${MINIO_HEALTH_URL:-http://192.168.1.159:9000/minio/health/live}" >/dev/null
python -m celery -A app.celery_worker:celery_app inspect ping --timeout=5
printf '\nPHASE 9 FULL GATE: PASS\n'
