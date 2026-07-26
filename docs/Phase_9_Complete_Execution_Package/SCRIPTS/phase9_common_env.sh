#!/usr/bin/env bash
set -Eeuo pipefail
cd "$HOME/Documents/Construction_Management"
source .venv/bin/activate
set -a
source .env.s3-local
set +a
export FLASK_APP=wsgi.py
export APP_ENV=local
export FLASK_DEBUG=true
export SESSION_COOKIE_SECURE=false
export DATABASE_URL="$(sudo cat /srv/construction_relation_management/secrets/database_url)"
export CELERY_BROKER_URL=redis://127.0.0.1:6379/0
export CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
export RATELIMIT_STORAGE_URI=redis://127.0.0.1:6379/2
printf 'Environment loaded for %s\n' "$PWD"
