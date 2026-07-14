#!/bin/sh
set -eu

read_secret_file() {
  VAR_NAME="$1"
  FILE_VAR_NAME="${VAR_NAME}_FILE"

  FILE_PATH="$(printenv "$FILE_VAR_NAME" 2>/dev/null || true)"

  if [ -n "$FILE_PATH" ]; then
    if [ ! -r "$FILE_PATH" ]; then
      echo "ERROR: Required secret file is not readable." >&2
      exit 1
    fi

    VALUE="$(cat "$FILE_PATH")"
    if [ -z "$VALUE" ]; then
      echo "ERROR: Required secret file is empty." >&2
      exit 1
    fi
    export "$VAR_NAME=$VALUE"
  fi
}

read_secret_file SECRET_KEY
read_secret_file DATABASE_URL
read_secret_file ADMIN_PASSWORD

if [ -z "${SECRET_KEY:-}" ]; then
  echo "ERROR: SECRET_KEY is missing" >&2
  exit 1
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is missing" >&2
  exit 1
fi

ensure_writable_directory() {
  DIRECTORY="$1"
  mkdir -p "$DIRECTORY"
  if [ ! -d "$DIRECTORY" ] || [ ! -w "$DIRECTORY" ]; then
    echo "ERROR: Required runtime directory is not writable." >&2
    exit 1
  fi
}

ensure_writable_directory "${UPLOAD_ROOT:-/app/storage/uploads}"
ensure_writable_directory "${TMP_ROOT:-/app/tmp}"

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  echo "Running database migrations..."
  flask db upgrade
fi

if [ "${RUN_SECURITY_AUDIT:-false}" = "true" ]; then
  echo "Running security audit..."
  flask security-audit
fi

if [ "${SEED_ADMIN:-false}" = "true" ]; then
  if [ -z "${ADMIN_PASSWORD:-}" ]; then
    echo "ERROR: SEED_ADMIN=true but ADMIN_PASSWORD is missing" >&2
    exit 1
  fi

  echo "Creating/updating admin user..."
  flask seed-admin \
    --username "${ADMIN_USERNAME:-admin}" \
    --password "$ADMIN_PASSWORD" \
    --email "${ADMIN_EMAIL:-admin@example.com}" \
    --full-name "${ADMIN_FULL_NAME:-System Admin}"
fi

exec "$@"
