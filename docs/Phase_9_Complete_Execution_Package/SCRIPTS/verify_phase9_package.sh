#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
required=(
  README.md MASTER_CONTEXT.md FINAL_DECISIONS.md TARGET_ARCHITECTURE.md
  TARGET_DATA_MODEL.md TARGET_RBAC_AND_CUSTOM_ROLES.md TARGET_UI_UX.md
  TARGET_DASHBOARDS.md MIGRATION_AND_COMPATIBILITY.md PHASE9_EXECUTION_MAP.md
)
for f in "${required[@]}"; do
  test -s "$ROOT/$f" || { echo "Missing: $f"; exit 1; }
done
count=$(find "$ROOT/PROMPTS" -type f -name '*.md' | wc -l)
test "$count" -eq 11 || { echo "Expected 11 prompts, found $count"; exit 1; }
if grep -RInE 'DATABASE_URL=.*postgresql|SECRET_KEY=.+|MINIO_ROOT_PASSWORD=.+|AWS_SECRET_ACCESS_KEY=.+' "$ROOT"; then
  echo "Potential secret found"
  exit 1
fi
echo "Package verification: PASS"
