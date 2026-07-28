#!/bin/sh
set -eu

read_secret_file() {
  var_name="$1"
  file_var_name="${var_name}_FILE"
  file_path="$(printenv "$file_var_name" 2>/dev/null || true)"

  if [ -n "$file_path" ]; then
    if [ ! -r "$file_path" ]; then
      echo "ERROR: Required secret file is not readable." >&2
      exit 1
    fi
    value="$(cat "$file_path")"
    if [ -z "$value" ]; then
      echo "ERROR: Required secret file is empty." >&2
      exit 1
    fi
    export "$var_name=$value"
  fi
}

for secret_name in SECRET_KEY DATABASE_URL STORAGE_ACCESS_KEY_ID STORAGE_SECRET_ACCESS_KEY REDIS_PASSWORD; do
  read_secret_file "$secret_name"
done

if [ "${APP_ENV:-}" = "production" ]; then
  for disabled_operation in RUN_MIGRATIONS RUN_SECURITY_AUDIT SEED_ADMIN; do
    if [ "$(printenv "$disabled_operation" 2>/dev/null || true)" = "true" ]; then
      echo "ERROR: Production startup does not run migrations, audits, or seed data." >&2
      exit 1
    fi
  done
fi

if [ -n "${REDIS_PASSWORD:-}" ]; then
  redis_password_encoded="$(REDIS_PASSWORD="$REDIS_PASSWORD" python -c 'import os, urllib.parse; print(urllib.parse.quote(os.environ["REDIS_PASSWORD"], safe=""))')"
  redis_host="${REDIS_HOST:-redis}"
  export RATELIMIT_STORAGE_URI="${RATELIMIT_STORAGE_URI:-redis://:${redis_password_encoded}@${redis_host}:6379/2}"
  export CELERY_BROKER_URL="${CELERY_BROKER_URL:-redis://:${redis_password_encoded}@${redis_host}:6379/0}"
  export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-redis://:${redis_password_encoded}@${redis_host}:6379/1}"
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is missing." >&2
  exit 1
fi

ensure_writable_directory() {
  directory="$1"
  mkdir -p "$directory"
  if [ ! -d "$directory" ] || [ ! -w "$directory" ]; then
    echo "ERROR: Required runtime directory is not writable." >&2
    exit 1
  fi
}

ensure_writable_directory "${TMP_ROOT:-/app/tmp}"

# Validate the exact same configuration used by Flask before waiting for
# dependencies or accepting traffic.  The database probe is bounded and does
# not mutate schema or seed data.
python -c 'from app import create_app; create_app()'

database_wait_seconds="${DATABASE_READY_TIMEOUT_SECONDS:-60}"
deadline=$(( $(date +%s) + database_wait_seconds ))
until python -c 'from sqlalchemy import create_engine, text; import os; engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True); connection = engine.connect(); connection.execute(text("SELECT 1")); connection.close(); engine.dispose()'; do
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "ERROR: Database was not ready before the startup timeout." >&2
    exit 1
  fi
  sleep 2
done

exec "$@"
