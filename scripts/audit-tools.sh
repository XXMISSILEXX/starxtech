#!/usr/bin/env bash
# =============================================================================
#  Phase 10 - Bước 1: chạy toàn bộ tool tự động TRƯỚC khi cho Claude đọc code.
#  Tự phát hiện stack. Không cần bạn điền module hay đường dẫn.
#  Không bao giờ fail cứng: tool nào thiếu thì ghi "BỎ QUA" vào báo cáo.
#
#  Dùng:  bash scripts/audit-tools.sh
#  Kết quả: .audit/raw/*   (output thô)
#           .audit/01-tooling.md  (tổng hợp: cái gì chạy, cái gì bỏ qua)
# =============================================================================
set -uo pipefail

OUT=".audit/raw"
SUM=".audit/01-tooling.md"
mkdir -p "$OUT" ".audit/leads"

# Output của gitleaks/trufflehog CHỨA SECRET THẬT -> không được commit
cat > .audit/.gitignore <<'EOF'
raw/
leads/
poc/node_modules/
EOF

: > "$SUM"
log() { echo "$@" >> "$SUM"; }
have() { command -v "$1" >/dev/null 2>&1; }
ok()   { log "- [x] **$1** → \`raw/$2\`"; }
warn() { log "- [!] **$1** — chạy xong nhưng exit≠0 → \`raw/$2\`"; }
skip() { log "- [ ] **$1** — BỎ QUA: $2"; }

runf() { # runf <label> <outfile> <cmd...>   (redirect stdout+stderr vào outfile)
  local label="$1" f="$2"; shift 2
  if "$@" > "$OUT/$f" 2>&1; then ok "$label" "$f"; else warn "$label" "$f"; fi
}

log "# 01 — Kết quả tool tự động"
log ""
log "Chạy lúc: $(date -u '+%Y-%m-%d %H:%M UTC')"
_sha=$(git rev-parse --short HEAD 2>/dev/null); _br=$(git branch --show-current 2>/dev/null)
log "Commit: \`${_sha:-n/a}\` trên nhánh \`${_br:-n/a}\`"
log ""

# ---------------------------------------------------------------- 0. Repo stats
log "## 0. Quy mô repo"
log ""
if have cloc; then
  runf "cloc" "cloc.txt" cloc . --vcs=git --quiet
elif have tokei; then
  runf "tokei" "cloc.txt" tokei .
else
  git ls-files 2>/dev/null | awk -F. 'NF>1{print $NF}' | sort | uniq -c | sort -rn > "$OUT/cloc.txt" 2>/dev/null \
    && ok "đếm file theo đuôi (fallback)" "cloc.txt" || skip "cloc/tokei" "chưa cài, và không phải git repo"
fi
{ echo "== tracked files =="; git ls-files 2>/dev/null | wc -l;
  echo "== commits =="; git log --oneline 2>/dev/null | wc -l;
  echo "== top-level dirs =="; git ls-files 2>/dev/null | cut -d/ -f1 | sort -u; } > "$OUT/repo-stats.txt" 2>&1
ok "repo stats" "repo-stats.txt"
log ""

# ---------------------------------------------------------------- 1. Secrets
log "## 1. Secret scan (bao gồm cả git history)"
log ""
if have gitleaks; then
  gitleaks detect --source . --no-banner --redact \
      --report-format json --report-path "$OUT/gitleaks.json" > "$OUT/gitleaks.log" 2>&1
  ok "gitleaks (working tree)" "gitleaks.json"
  gitleaks detect --source . --no-banner --redact --log-opts="--all --full-history" \
      --report-format json --report-path "$OUT/gitleaks-history.json" > "$OUT/gitleaks-history.log" 2>&1
  ok "gitleaks (toàn bộ git history)" "gitleaks-history.json"
elif have docker; then
  runf "gitleaks (docker)" "gitleaks.log" \
    docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:latest detect --source /repo --redact --no-banner
else
  skip "gitleaks" "chưa cài (brew install gitleaks / apt / docker)"
fi
have trufflehog && runf "trufflehog" "trufflehog.json" trufflehog git file://. --json --no-update \
  || skip "trufflehog" "chưa cài (tùy chọn, gitleaks là đủ)"
log ""

# ---------------------------------------------------------------- 2. SAST
log "## 2. SAST"
log ""
if have semgrep; then
  semgrep --config auto --json -o "$OUT/semgrep.json" --metrics=off > "$OUT/semgrep.log" 2>&1
  ok "semgrep --config auto" "semgrep.json"
  if have jq; then
    jq -r '[.results[] | {sev:.extra.severity, rule:.check_id, file:.path, line:.start.line}]
           | group_by(.sev)[] | "\(.[0].sev): \(length)"' "$OUT/semgrep.json" \
      > "$OUT/semgrep-summary.txt" 2>/dev/null && ok "semgrep summary" "semgrep-summary.txt"
  fi
elif have pipx; then
  runf "semgrep (pipx)" "semgrep.log" pipx run semgrep --config auto --json -o "$OUT/semgrep.json" --metrics=off
elif have docker; then
  runf "semgrep (docker)" "semgrep.log" \
    docker run --rm -v "$PWD:/src" semgrep/semgrep semgrep --config auto --json -o /src/$OUT/semgrep.json --metrics=off
else
  skip "semgrep" "chưa cài (pip install semgrep)"
fi
log ""

# ---------------------------------------------------------------- 3. CVE / deps
log "## 3. Dependency & CVE"
log ""
if have trivy; then
  runf "trivy fs" "trivy-fs.json" trivy fs . --scanners vuln,secret,misconfig --format json
else
  skip "trivy" "chưa cài (brew install trivy)"
fi
have osv-scanner && runf "osv-scanner" "osv.json" osv-scanner --recursive --format json . \
  || skip "osv-scanner" "chưa cài (tùy chọn, trùng chức năng trivy)"

[ -f package.json ]     && { runf "npm audit"   "npm-audit.json"   npm audit --json; }
[ -f package.json ]     && have npx && runf "knip (dead code/deps)" "knip.txt" npx --yes knip --no-exit-code
[ -f package.json ]     && have npx && runf "depcheck"  "depcheck.txt"  npx --yes depcheck
[ -f requirements.txt ] || [ -f pyproject.toml ] && {
  have pip-audit && runf "pip-audit" "pip-audit.json" pip-audit -f json || skip "pip-audit" "chưa cài (pipx install pip-audit)"
  have bandit    && runf "bandit"    "bandit.json"    bandit -r . -f json -ll || skip "bandit" "chưa cài"
  have vulture   && runf "vulture (dead code)" "vulture.txt" vulture . || skip "vulture" "chưa cài"
}
[ -f go.mod ]      && { have govulncheck && runf "govulncheck" "govulncheck.txt" govulncheck ./... || skip "govulncheck" "chưa cài"; }
[ -f Cargo.toml ]  && { have cargo-audit && runf "cargo audit" "cargo-audit.txt" cargo audit || skip "cargo-audit" "chưa cài"; }
[ -f composer.json ] && { have composer && runf "composer audit" "composer-audit.txt" composer audit || skip "composer audit" "chưa cài"; }
log ""

# ------------------------------------------- 4. Package ảo (slopsquatting) — quan trọng với code AI sinh
log "## 4. Kiểm tra package ảo / mới tinh (slopsquatting)"
log ""
SLOP="$OUT/phantom-packages.txt"
: > "$SLOP"
if [ -f package.json ] && have jq && have npm; then
  jq -r '(.dependencies // {}) + (.devDependencies // {}) | keys[]' package.json 2>/dev/null | while read -r p; do
    created=$(npm view "$p" time.created 2>/dev/null | tr -d '\r')
    if [ -z "$created" ]; then echo "KHÔNG TỒN TẠI TRÊN NPM: $p" >> "$SLOP"
    else echo "ok  $p  (published: $created)" >> "$SLOP"; fi
  done
  ok "npm phantom check" "phantom-packages.txt"
elif [ -f requirements.txt ] && have curl; then
  grep -Eo '^[A-Za-z0-9_.\-]+' requirements.txt | while read -r p; do
    code=$(curl -s -o /dev/null -w '%{http_code}' "https://pypi.org/pypi/$p/json")
    [ "$code" = "200" ] && echo "ok  $p" >> "$SLOP" || echo "KHÔNG TỒN TẠI TRÊN PYPI: $p (http $code)" >> "$SLOP"
  done
  ok "pypi phantom check" "phantom-packages.txt"
else
  skip "phantom package check" "cần jq+npm (Node) hoặc curl (Python), hoặc stack khác"
fi
grep -c 'KHÔNG TỒN TẠI' "$SLOP" 2>/dev/null | while read -r n; do
  [ "$n" != "0" ] && log "  > ⚠️  **$n package không tồn tại upstream — xem \`raw/phantom-packages.txt\` NGAY**"
done
log ""

# ---------------------------------------------------------------- 5. Type / lint / build / test
log "## 5. Type check, lint, build, test"
log ""
[ -f tsconfig.json ] && have npx && runf "tsc --noEmit" "tsc.txt" npx --yes tsc --noEmit
[ -f package.json ]  && have npx && runf "eslint" "eslint.txt" npx --yes eslint . -f stylish
have ruff  && runf "ruff" "ruff.txt" ruff check .
have mypy  && runf "mypy" "mypy.txt" mypy . --ignore-missing-imports
have staticcheck && [ -f go.mod ] && runf "staticcheck" "staticcheck.txt" staticcheck ./...
if [ -f package.json ] && have jq; then
  jq -e '.scripts.build' package.json >/dev/null 2>&1 && runf "npm run build" "build.txt" npm run build
  jq -e '.scripts.test'  package.json >/dev/null 2>&1 && runf "npm test"      "test.txt"  npm test
fi
have pytest && runf "pytest" "test.txt" pytest -q
have npx && runf "jscpd (code trùng lặp)" "jscpd.txt" npx --yes jscpd . --reporters console --min-lines 15
have npx && runf "madge (circular import)" "madge.txt" npx --yes madge --circular --extensions ts,tsx,js,jsx .
log ""

# ---------------------------------------------------------------- 6. Docker / IaC
log "## 6. Docker & IaC (chuẩn bị cho Phase 11)"
log ""
if ls Dockerfile* */Dockerfile* >/dev/null 2>&1; then
  have hadolint && runf "hadolint" "hadolint.txt" bash -c 'for f in $(git ls-files | grep -i dockerfile); do echo "== $f"; hadolint "$f"; done' \
    || skip "hadolint" "chưa cài"
  have trivy && runf "trivy config" "trivy-config.json" trivy config . --format json
else
  skip "hadolint/trivy config" "chưa có Dockerfile trong repo"
fi
have checkov && runf "checkov" "checkov.txt" checkov -d . --compact || skip "checkov" "chưa cài (tùy chọn)"
log ""

# ---------------------------------------------------------------- 7. Dấu hiệu code chưa hoàn thiện
log "## 7. Grep nhanh dấu hiệu code chưa hoàn thiện"
log ""
{
  echo "===== TODO / FIXME / HACK / XXX ====="
  git grep -nI -E 'TODO|FIXME|HACK|XXX|WIP' -- . 2>/dev/null | head -400
  echo; echo "===== mock / stub / placeholder / dummy / fake ====="
  git grep -nI -iE '\b(mock|stub|placeholder|dummy|fake|sample|example)\b' -- . 2>/dev/null | grep -viE '(test|spec|__mocks__|\.md)' | head -300
  echo; echo "===== 'for now' / 'temporary' / 'simplified' / 'not implemented' ====="
  git grep -nI -iE 'for now|temporar|simplif|not implemented|implement later|chưa làm|tạm thời' -- . 2>/dev/null | head -200
  echo; echo "===== return true / return early trong hàm giống check quyền ====="
  git grep -nI -iE '(validate|verify|check|is[A-Z]|can[A-Z]|has[A-Z]|authorize|authenticate)[A-Za-z]*\s*\(' -- . 2>/dev/null | head -300
  echo; echo "===== catch rỗng / nuốt exception ====="
  git grep -nI -E 'catch\s*\([^)]*\)\s*\{\s*\}|except\s*:\s*pass|except Exception:\s*pass|catch\s*\{\s*\}' -- . 2>/dev/null | head -200
  echo; echo "===== nhánh dev/debug có thể chạy được ở production ====="
  git grep -nI -iE "NODE_ENV\s*[=!]==?\s*['\"]development|DEBUG\s*=\s*True|if\s*\(\s*debug" -- . 2>/dev/null | head -200
  echo; echo "===== chuỗi giống secret hardcode ====="
  git grep -nI -iE "(password|passwd|secret|api[_-]?key|token|private[_-]?key)\s*[:=]\s*['\"][^'\"]{6,}" -- . 2>/dev/null | grep -viE '(\.md|test|spec|example|\.env\.example)' | head -200
} > "$OUT/grep-signals.txt" 2>&1
ok "grep signals" "grep-signals.txt"
log ""

log "---"
log ""
log "**Bước tiếp theo:** mở Claude Code và chạy prompt ở Bước 2 của \`AUDIT_RUNBOOK.md\`."
log "Coi mọi kết quả ở trên là **nghi vấn cần xác minh**, KHÔNG phải finding."

echo
echo "==================================================================="
echo " Xong. Đọc tóm tắt tại: $SUM"
echo " Output thô tại:        $OUT/  (ĐÃ gitignore — chứa secret thật)"
echo "==================================================================="
grep -c 'BỎ QUA' "$SUM" 2>/dev/null | xargs -I{} echo " Số tool bị bỏ qua: {} (xem lý do trong $SUM)"
