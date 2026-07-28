# 01 — Kết quả tool tự động

Chạy lúc: 2026-07-27 09:54 UTC
Commit: `ca60d36` trên nhánh `phase10/audit`

## 0. Quy mô repo

- [x] **đếm file theo đuôi (fallback)** → `raw/cloc.txt`
- [x] **repo stats** → `raw/repo-stats.txt`

## 1. Secret scan (bao gồm cả git history)

- [x] **gitleaks (working tree)** → `raw/gitleaks.json`
- [x] **gitleaks (toàn bộ git history)** → `raw/gitleaks-history.json`
- [ ] **trufflehog** — BỎ QUA: chưa cài (tùy chọn, gitleaks là đủ)

## 2. SAST

- [x] **semgrep --config auto** → `raw/semgrep.json`

## 3. Dependency & CVE

- [x] **trivy fs** → `raw/trivy-fs.json`
- [ ] **osv-scanner** — BỎ QUA: chưa cài (tùy chọn, trùng chức năng trivy)
- [x] **npm audit** → `raw/npm-audit.json`
- [x] **knip (dead code/deps)** → `raw/knip.txt`
- [x] **depcheck** → `raw/depcheck.txt`
- [ ] **pip-audit** — BỎ QUA: chưa cài (pipx install pip-audit)
- [ ] **bandit** — BỎ QUA: chưa cài
- [ ] **vulture** — BỎ QUA: chưa cài

## 4. Kiểm tra package ảo / mới tinh (slopsquatting)

- [x] **npm phantom check** → `raw/phantom-packages.txt`

## 5. Type check, lint, build, test

- [!] **eslint** — chạy xong nhưng exit≠0 → `raw/eslint.txt`
- [x] **npm test** → `raw/test.txt`
- [x] **pytest** → `raw/test.txt`
- [x] **jscpd (code trùng lặp)** → `raw/jscpd.txt`
- [x] **madge (circular import)** → `raw/madge.txt`

## 6. Docker & IaC (chuẩn bị cho Phase 11)

- [ ] **hadolint** — BỎ QUA: chưa cài
- [x] **trivy config** → `raw/trivy-config.json`
- [ ] **checkov** — BỎ QUA: chưa cài (tùy chọn)

## 7. Grep nhanh dấu hiệu code chưa hoàn thiện

- [x] **grep signals** → `raw/grep-signals.txt`

---

**Bước tiếp theo:** mở Claude Code và chạy prompt ở Bước 2 của `AUDIT_RUNBOOK.md`.
Coi mọi kết quả ở trên là **nghi vấn cần xác minh**, KHÔNG phải finding.
