# PRE-FINDINGS.md

Recorded before the deep pass so they are not lost and not re-discovered as
if new. Each entry states what's confirmed now vs. what the assigned unit
must still verify. Read-only — nothing here has been fixed.

---

## PRE-001 — Audit-log IP address is client-spoofable

`app/audit.py:33` reads `request.headers.get("X-Forwarded-For",
request.remote_addr)` directly, bypassing the `ProxyFix` middleware that
`app/__init__.py:73-75` sets up specifically to normalize `X-Forwarded-For`
according to `TRUST_PROXY_HOPS`. Not privilege escalation, but it undermines
the audit trail's evidentiary value — if `TRUST_PROXY_HOPS` is 0 (the
default) or the edge proxy doesn't strip the header, a client can put
whatever it wants in `AuditLog.ip_address`. **Status: OPEN, confirmed by
reading both files.** Owner: Foundation-A2 / unit 1.

---

## PRE-002 — Structural: dead authorization decorators, hand-rolled inline checks everywhere else

`role_required`, `viewer_or_admin_required`, `super_admin_required`,
`admin_read_required`, `project_manage_required` (`app/auth/permissions.py`)
and the "compatibility adapter" functions `can_write_project`,
`can_manage_project`, `can_delete_report_for_project`,
`can_delete_issue_for_project`, `can_manage_persistent_issues` have **zero
call sites** anywhere in `app/` (confirmed by repo-wide grep, re-confirmed
this pass). `project_read_required`/`project_write_required` have exactly
one call site each — a synthetic test-only route in
`tests/conftest.py:30-38` — no real application route uses them.

Consequence: every real route hand-rolls its own inline check
(`current_user.can(...)`, `can_view_report(...)`, etc.) rather than going
through a shared decorator. Every route is therefore an **independent
chance to forget a check** — there is no single choke point that, if
correct, guarantees correctness everywhere. This is the primary reason the
blueprint→unit completeness table in `MODULES.md` had to be built by reading
`app/__init__.py` line by line rather than assumed, and the primary reason
unit 13 (Test suite integrity) exists — a decorator with a passing test
proves the decorator works, not that any endpoint uses it correctly.
**Status: OPEN, structural.** Owner: unit 13 (enumerate), all units
(individually verify their own routes).

---

## PRE-003 — `deploy_backup_2026-07-14_142253/` is a runnable compose file that silently disables protections

Tracked in git, added by commit `2d70dee` ("Stable non-RBAC version 1").
Confirmed by direct diff against the live `docker-compose.yml`:

| Setting | Live `docker-compose.yml` | `deploy_backup_2026-07-14_142253/docker-compose.yml` |
|---|---|---|
| `RATELIMIT_STORAGE_URI` | `redis://redis:6379/2` | `memory://` |
| `DAILY_REPORT_*` (8 vars) | all 8 set explicitly (lines 30-37) | **absent entirely** |
| `TRUSTED_HOSTS` | `smart-home.starxvietnam.com` (hardcoded) | `${TRUSTED_HOSTS:-}` (parameterized, defaults empty) |
| `PUBLIC_HOSTNAME` | `smart-home.starxvietnam.com` | *(key doesn't exist in the backup file at all — not just unhardcoded, added later)* |

Gitleaks found no secrets in the backup file. The real risk is deploying the
wrong compose file by accident: it is a complete, runnable file that
silently removes upload limits and weakens rate limiting, with no error at
startup (unlike, say, `production_configuration_errors()` in
`app/security.py`, which *does* hard-fail on an unsafe `STORAGE_PROVIDER` or
`SECRET_KEY` but has no equivalent check for `DAILY_REPORT_*` or
`RATELIMIT_STORAGE_URI`).

**Deliverable for Unit 12** — default value of each `DAILY_REPORT_*` var when
unset, cited to `app/config.py`:

| Variable | Default when unset | `app/config.py` line |
|---|---|---|
| `DAILY_REPORT_DIRECT_UPLOAD_ENABLED` | `true` | 49 |
| `DAILY_REPORT_MAX_FILES` | `30` | 50 |
| `DAILY_REPORT_MAX_FILES_PER_SECTION` | `3` | 51 |
| `DAILY_REPORT_MAX_FILE_BYTES` | `26214400` (25 MB) | 52 |
| `DAILY_REPORT_MAX_TOTAL_BYTES` | `314572800` (300 MB) | 53 |
| `DAILY_REPORT_UPLOAD_CONCURRENCY` | `3` | 54 |
| `DAILY_REPORT_PRESIGN_TTL_SECONDS` | `900` | 55 |
| `DAILY_REPORT_SESSION_TTL_SECONDS` | `86400` | 56 |

**None of these defaults are permissive/unbounded** — every one of the 8 has
a finite, sane fallback baked into `Config` itself (this also matches the
`app.config.setdefault(...)` block in `app/__init__.py:15-45`, which sets
the same values again as a second line of defense if `Config` somehow didn't
apply). So the specific "silently removes upload limits" framing in the
original hypothesis does **not** hold for these 8 variables — deploying the
backup compose file would fall back to sane defaults, not to unbounded
uploads. This downgrades this specific piece from Critical to **Info** — but
the `RATELIMIT_STORAGE_URI` divergence (below) is real and does matter.

**Gunicorn worker count & rate-limit multiplier under the backup file**:
`gunicorn.conf.py` reads `WEB_CONCURRENCY` (default `"2"`) — both the live
and backup compose files explicitly set `WEB_CONCURRENCY: "2"`,
`GUNICORN_THREADS: "2"`. With `RATELIMIT_STORAGE_URI=memory://` (the backup
file's value), each of the 2 gunicorn worker **processes** holds its own
independent in-memory limiter counter — `gthread` worker class means the 2
threads *within* one process share that process's counter, but the 2
processes do not share with each other. Effective result: any configured
rate limit (e.g. `RATELIMIT_LOGIN_LIMIT` = "5 per minute") is enforced as
**up to ~2x its configured value in practice** (a client's requests round-robin
across both independent worker processes). This is a real, live-vs-backup
functional difference, not just a style difference. **Status: OPEN** — the
`DAILY_REPORT_*` piece is resolved (Info, sane defaults); the rate-limit
storage piece remains a live finding for Unit 12 to size (how many login/
export/upload attempts would actually get through per minute under the
backup file vs. the live one).

---

## PRE-004 — No supervised Celery worker or Redis service found in `docker-compose.yml`

Confirmed by reading both the live and backup compose files fully: **the
only two services defined in either file are `web` and `cloudflared`.**
There is no `redis:` service, no Celery worker service, in either file.

The live file's only reference to Redis at all is
`RATELIMIT_STORAGE_URI: redis://redis:6379/2` (`docker-compose.yml:43`) — a
hostname (`redis`) that resolves only if some other, uncommitted mechanism
provides a reachable host named `redis` on the `appnet` network (no
`extra_hosts`, no external network reference, no second compose file
found in this repo). Neither `CELERY_BROKER_URL` nor `CELERY_RESULT_BACKEND`
is set anywhere in either compose file, so Celery would fall back to the
application defaults in `app/config.py` (`redis://localhost:6379/0` and
`.../1`) — inside the `web` container's own network namespace, `localhost`
means the container itself, which almost certainly has no Redis process
running in it (nothing in `Dockerfile` suggests one).

Media derivative generation (`app/media_processing/`), bulk ZIP downloads
(`app/bulk_downloads/`), and expired-session cleanup all depend on Celery
being reachable. If this compose file is the actual deployment mechanism (see
PRE-009), **all three of those features are non-functional in production as
currently defined** — uploads would succeed (they go straight to S3 via
presigned URLs) but thumbnails/previews/video posters would never generate,
bulk ZIP downloads would never complete, and expired upload sessions would
never get cleaned up. This reads as "looks complete in the code, silently
inert in the deployed environment" — a Phase 11 blocker, not a code bug.
**Status: OPEN, strong circumstantial evidence, Unit 12 must confirm by
checking for a Redis/worker process running some other way** (systemd unit
on the host, a separate compose override file not in this repo, manual
`scripts/start-media-worker.sh` invocation) **before treating this as
confirmed**.

---

## PRE-005 — Tool status: all three scanners now have real output

Re-ran since the first pass (file timestamps in `.audit/raw/` confirm this).
Treat every entry below as a **lead to verify manually in source**, never as
a finding on its own — see `TOOL-LEAD-MAP.md` for the full assignment.

- `semgrep`: 11 findings (3 ERROR — all `avoid-sqlalchemy-text`, all
  confirmed not reachable from untrusted input, see below; 8 WARNING —
  template/JS injection-shaped patterns) — `.audit/raw/semgrep.json`.
- `pip-audit`: 28 raw vulnerability entries (21 distinct after de-duplicating
  overlapping PyPA/OSV IDs) across 5 packages: `flask` (1), `python-dotenv`
  (1), `pillow` (17 distinct), `pillow-heif` (1), `pytest` (1) —
  `.audit/raw/pip-audit.json`.
- `trivy fs`: 13 HIGH-severity findings (0 CRITICAL), all in `Pillow`
  10.4.0 via `requirements.txt`, overlapping the pip-audit Pillow set; 0
  secrets found — `.audit/raw/trivy-fs.json`.
- `trivy config`: only ran cleanly after stripping a log preamble the
  audit-tooling script left mixed into the JSON output file (fixed locally
  for reading, not a repo change) — 1 misconfiguration type, `DS-0026` /
  LOW / "No HEALTHCHECK defined", repeated across the live `Dockerfile` and
  both backup-directory copies. Not HIGH/CRITICAL.

Full per-finding assignment, reachability analysis, and file:line citations
are in `TOOL-LEAD-MAP.md`.

---

## PRE-006 — `docker-compose.yml` hardcodes `TRUSTED_HOSTS`/`PUBLIC_HOSTNAME` to a production hostname

Confirmed: live file sets `TRUSTED_HOSTS: smart-home.starxvietnam.com` and
`PUBLIC_HOSTNAME: smart-home.starxvietnam.com` (`docker-compose.yml:51-52`).
The backup file (`deploy_backup_2026-07-14_142253/`) has `TRUSTED_HOSTS:
${TRUSTED_HOSTS:-}` (parameterized, empty default) at the same location and
**no `PUBLIC_HOSTNAME` key at all** — so this isn't just "a value got
hardcoded that used to be a variable," it's also a newer setting added after
that snapshot was taken. The tracked file cannot currently be reused
for staging/another environment without editing a tracked file directly.
**Deliverable for Unit 12**: inventory every hardcoded environment-specific
value in `docker-compose.yml` and produce the `.env.example` needed to
externalize all of them. **Status: OPEN.**

---

## PRE-007 — CLOSED, not a blocker

`master` (`2d70dee`) is confirmed to be a strict ancestor of `phase10/audit`:
`git merge-base master HEAD` returns `2d70dee3411e5d19db3d4927ee487d7f25cdd113`
(= `master`'s own tip), `git log --oneline master..HEAD` returns 47 commits,
`git log --oneline HEAD..master` returns 0. `master` is a stale label 47
commits behind with zero commits of its own — not a parallel production
line. Recorded only so it is not re-raised.

---

## PRE-008 — Gitleaks `generic-api-key` at `app/cli.py:199` (in commit `2d70dee`'s tree) — verdict: FALSE POSITIVE

Both `gitleaks.json` (working tree) and `gitleaks-history.json` (full
history) report the identical single hit: `RuleID: generic-api-key`,
`File: app/cli.py`, `StartLine: 199`, commit `2d70dee3411e5d19db3d4927ee487d7f25cdd113`.

Verified directly: `git show 2d70dee:app/cli.py` at that line is
`check(not weak_secret, "secret-key", "strong non-default key configured",
"missing/default/short SECRET_KEY")` — part of the `security-audit` CLI
command's own self-description strings. The identical line (now at line 406)
still exists verbatim in current HEAD. Gitleaks' own redaction feature
replaced the actual matched substring with the literal placeholder
`REDACTED` in its `Secret`/`Match` output fields — the tool was not hiding a
real credential, it was redacting its own (incorrect) match against the
descriptive string `"strong non-default key configured"` combined with the
neighboring literal `"missing/default/short SECRET_KEY"`, which contains the
substring `SECRET_KEY` and enough entropy to trip the generic-API-key
heuristic. **No real secret exists at this location, in this commit or any
other.** Verdict pasted here per your request, before Foundation-A1 starts.

Two consequences stand regardless of this specific verdict:
1. `app/cli.py` belongs to unit 1. Unit 1 must still audit every *actual*
   hardcoded credential, default password, and seeded account in that file
   (e.g. `flask seed-partner-demo`'s synthetic emails/passwords, the
   `admin-seeding` path's behavior when `--password` is weak) — this false
   positive does not substitute for that review.
2. Removing a secret from current code would not remove it from git
   history — noted for general awareness; not applicable here since there
   was never a real secret to begin with.

**Status: CLOSED.**

---

## PRE-009 — No git remote configured; repository exists on one machine only

Confirmed: `git remote -v` returns nothing. `git branch -a -v` lists only
local branches, no `remotes/*` refs.

**Unit 12 deliverables**:
a) Read `DEPLOY_UBUNTU.md`, `DOCKER_DEPLOY.md`, and `docker-entrypoint.sh`
   and state exactly how source code reaches the server, quoting the
   relevant lines. If the answer is a manual copy or a local `docker build`,
   say so plainly — do not infer a CI/CD pipeline that isn't there.
b) State what happens to this project if the machine holding this repo is
   lost today: source (no remote — total loss unless a separate backup
   exists outside this repo), `.env`/`secrets/` (same), database (depends on
   `scripts/backup_db.sh` actually running somewhere and that backup living
   outside this machine — confirm), object storage (depends on the S3/MinIO
   provider's own durability, external to this repo either way).
c) File this under Phase 11 blockers, not security findings — it's an
   operational continuity gap, not a vulnerability.

**Status: OPEN**, assigned to Unit 12.

---

## PRE-010 — Semgrep template coverage: real number is 61/66, not 53, and there is no `.semgrepignore`

Verified: no `.semgrepignore` file exists anywhere in the repository (search
from repo root, no matches). `semgrep.json`'s `paths.skipped` array is empty
— semgrep did not report a formal "skipped" list at all in this run's
output.

What *is* real, found in `semgrep.json`'s `errors` array: **61 of the 66**
Jinja templates under `app/templates/` produced a parsing error (mostly
`PartialParsing`/"Syntax error" against Jinja's `{% extends %}` and similar
tag syntax, which semgrep's generic HTML analyzer does not fully understand).
Only 5 templates parsed clean: `app/templates/admin/branding.html`,
`app/templates/admin/roles/permissions.html`, `app/templates/auth/login.html`,
`app/templates/partner_relations/_department_summary.html`,
`app/templates/partners/_field_input.html`. Despite the parse errors on the
other 61, semgrep still extracted **partial** matches from at least 4 of them
(the `var-in-href`/`var-in-script-tag` hits listed in `TOOL-LEAD-MAP.md` are
all in files that also appear in the error list) — so "61 files with parse
errors" is not the same as "61 files with zero coverage," but it does mean
semgrep's read of nearly every template in this app is incomplete and
partial, not a clean full-file analysis.

I could not locate the specific "53 files skipped by `.semgrepignore`"
figure anywhere in this run's actual output — flagging the discrepancy with
your stated number rather than silently adopting it. If you have a separate
semgrep invocation/log with that number, it used a different flag set or
config than what's in `.audit/raw/` right now; worth reconciling before Unit
14 starts so it isn't chasing a phantom 53rd file.

**Conclusion unchanged from your instruction**: whatever the exact count,
coverage of the 66 Jinja templates by automated SAST is effectively
negligible. **Unit 14 is the only real coverage the template layer will
get**, is rated HIGH, and runs in Batch 2. **Status: OPEN** (the 53-vs-61
discrepancy specifically), core conclusion **CONFIRMED**.

---

## PRE-011 — NEW (found during this pass): `daily_report_create_v2` blueprint has no module-level gate

Found while building the blueprint→unit completeness table in `MODULES.md`
(Part 4). `require_reports_module_access`'s gated-prefix tuple
(`app/__init__.py:174`) does not include `"daily_report_create_v2."`, and
`app/reports/create_v2.py` has no `@bp.before_request` of its own (confirmed
by reading the full file, 135 lines). Every route in that file does call a
shared `_project()` helper (`app/reports/create_v2.py:29-35`) which enforces
`can_create_report(current_user, project.id)` — a per-project capability
check — consistently across all 7 routes. This is the same per-project check
`app/projects/routes.py`'s legacy upload-session routes perform
(`report_upload_session_create` etc., lines 136+) — **but** those legacy
routes additionally get the global module-gate check for free, because
`projects.` *is* in the gated tuple, and `daily_report_create_v2.` isn't.

Read `user_has_project_capability()`/`is_viewer_admin()`
(`app/project_memberships.py:78-89`) to size actual impact: `can_create_reports`
is **not** in `READ_CAPABILITIES`, so a `VIEWER_ADMIN` does not get an
automatic pass on it, and a user with no active `ProjectUser` row for the
target project gets denied regardless of module-gate presence. So the
practical exploitability of this specific gap looks low — the per-project
capability check alone already blocks the obvious cases (non-members,
`VIEWER_ADMIN`). What remains open: whether there's any RBAC/role
configuration where a user has `can_create_reports=True` on a `ProjectUser`
row but has deliberately had `modules.reports.access` revoked — in that
narrower case, the v2 API would let them through where the v1 API would not.
**Status: OPEN**, assigned to unit 3b as its primary deliverable (the
side-by-side comparison this finding motivated in the first place).

---

## A1-001 — Production config validation gates on an unvalidated `APP_ENV` string — Phase 11 blocker candidate

Found during Foundation-A1. `app/security.py:62`:

```python
def production_configuration_errors(config) -> list[str]:
    if config.get("APP_ENV") != "production":
        return []
```

`APP_ENV` (`app/config.py`, `os.getenv("APP_ENV", "local")`) is a free
string with no allow-list validation anywhere in the codebase. All 8 checks
inside `production_configuration_errors()` (`app/security.py:61-83` —
`SECRET_KEY` default/short, sample/SQLite `DATABASE_URL`, `DEBUG` on,
`SESSION_COOKIE_SECURE`/`HTTPONLY`/`SAMESITE`, `STORAGE_PROVIDER=fake`,
missing S3 credentials) are skipped entirely unless `APP_ENV` is the exact
lowercase string `"production"`. The caller
(`app/__init__.py:46-48`) is unconditional — if the function returns an
empty list (as it does for any non-matching `APP_ENV`), startup proceeds
silently, no log line, no warning, no non-zero exit.

**Concrete deploy-time consequence**: an operator who sets every other
production value correctly but spells `APP_ENV=Production` (capital P),
leaves it unset, or otherwise diverges from the exact string
`"production"` gets a running app with a possibly-default `SECRET_KEY`,
`SESSION_COOKIE_SECURE=False`, and/or `STORAGE_PROVIDER=fake` — the entire
production safety net collapses to a single case-sensitive string
comparison, with zero observability into whether it fired.

**Minimal fix (not implemented, read-only pass)**: validate `APP_ENV`
against a fixed allow-list at the same call site and fail closed (raise) on
any unrecognized value, rather than silently treating anything that isn't
exactly `"production"` as equivalent to local/dev.

**Status: OPEN.** Filed as a Phase 11 blocker candidate — this is a
deploy-configuration-discipline gap, not a code vulnerability per se, but
it is exactly the kind of thing that should be closed before Phase 11's
real-server cutover. Assigned to Unit 1 (CLI & Ops) for the fix
recommendation write-up and Unit 12 (Docker/IaC) for cross-reference (does
the Docker entrypoint or Compose file set `APP_ENV` explicitly and
correctly today? — if yes, this is a defense-in-depth gap rather than an
active live issue; confirm either way before Phase 11 sign-off).
