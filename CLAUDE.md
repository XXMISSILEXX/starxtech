# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

StarX Project Daily Report System — an internal Flask app (Vietnamese UI) for
construction project daily progress reports, persistent issues, partner/CRM
management, project document libraries, and a company media library. Full-stack
Flask + Jinja + Bootstrap 5 + Chart.js, no SPA frontend. See `README.md` for
full local/Docker/Ubuntu deployment instructions and `AGENTS.md` for the
original product spec (roles, entities, MVP constraints) — both are
authoritative and should be read for domain rules, not duplicated here.

### Product context and project-specific rules

This system is an internal operational platform for a small Vietnamese company,
used by management, project managers, engineers, reporters, document
controllers, administrative staff, and selected read-only users. Its purpose is
to centralize construction project reporting, unresolved issues, project
documents, company media, and business-partner information in one permissioned
system.

The application is expected to be used primarily in Vietnam, so the user
interface, validation messages, operational terminology, dates, and business
workflows should remain understandable to Vietnamese office and construction
staff. English may be used in code, identifiers, logs, technical documentation,
and infrastructure configuration.

Project data is not globally visible by default. Non-admin users must only see
projects and records granted through project membership and explicit capability
flags. Never infer access merely because a user can access the parent module.

Uploaded files are treated as private business records. Originals must only be
available through explicit authorized download flows. Normal previews should
use generated thumbnails, previews, video posters, or processing placeholders;
they must not silently fall back to serving the original object.

S3-compatible object storage is the canonical storage layer for all user
content. Local filesystem upload paths, compatibility fallbacks, and direct
filesystem serving are intentionally not supported, even when they would make
local development simpler.

Permission behavior is intentionally split across module gates, global RBAC, and
per-project capabilities. This is more complex than a single-role system, but it
is deliberate and must not be simplified without a documented migration plan
and complete authorization review.

Database permission records are not synchronized automatically at startup.
`app/permissions/registry.py` is the source of truth, and administrators must
run `flask sync-permissions --apply-defaults` explicitly after permission
changes. This avoids silently changing production authorization during deploys.

Media processing is asynchronous and post-commit by design. Image thumbnails,
image previews, and video posters may temporarily be unavailable; routes and UI
must handle pending, failed, and retryable processing states without exposing
the original file as a fallback.

The codebase was largely AI-generated and is currently undergoing a production
readiness audit. During audit tasks, prioritize evidence, traceability, concrete
file and line references, reproducible commands, and clearly separated findings
over speculative refactors or broad rewrites.

**Current branch context**: `phase10/audit` — this codebase was largely
AI-generated and is being audited before a production deploy (Phase 11:
Docker + object storage + real server). `AUDIT_RUNBOOK.md` describes that
process. If asked to "audit" or "review" the codebase, treat it as read-only:
do not edit/create/delete files outside `.audit/` unless explicitly told this
is an implementation (not audit) task.

## Audit operating rules

When performing a code review, architecture review, or security audit:

* Read `AUDIT_RUNBOOK.md`, `README.md`, and `AGENTS.md` before forming
  conclusions about intended behavior.
* Treat the repository as read-only except for reports, command outputs, and
  working notes under `.audit/`.
* Do not fix findings during the audit unless the user explicitly changes the
  task from audit to implementation.
* Do not classify something as a vulnerability solely because it looks unusual;
  first determine whether it is an intentional project rule documented here,
  in `AGENTS.md`, or in `AUDIT_RUNBOOK.md`.
* Every finding should identify the affected file, function or route, relevant
  authorization or data-flow boundary, practical impact, and a reproducible
  verification method.
* Distinguish confirmed findings from suspected risks, missing evidence, test
  gaps, hardening opportunities, and accepted design decisions.
* Prefer targeted commands and focused tests over running destructive,
  production-only, migration-generating, or data-reset commands.
* Never run commands that reset databases, delete storage objects, mutate
  production-like data, apply migrations, or synchronize permissions unless
  explicitly authorized.
* Never print secrets, complete presigned URLs, session cookies, access tokens,
  private object keys, or sensitive personal information into audit reports.
* Preserve evidence from failing commands. Do not suppress warnings, weaken
  tests, skip checks, or modify configuration merely to obtain a green result.

## Commands

### Python backend

```bash
source .venv/bin/activate
pip install -r requirements.txt

flask run                                    # dev server
flask --app run.py routes                    # list routes
flask shell                                  # REPL with app context

pytest                                        # full suite
pytest tests/test_reports_attachments.py      # single file
pytest tests/test_reports_attachments.py::test_name -v   # single test
```

`pytest.ini` sets `filterwarnings = error` — any warning raised during a test
run fails it, so don't silently ignore new DeprecationWarnings, etc. Tests run
against an in-memory SQLite app (`tests/conftest.py`), not Postgres.

During an audit, remember that passing SQLite tests do not prove compatibility
with production PostgreSQL. Review database-specific behavior such as
constraints, transaction isolation, locking, JSON operations, indexes,
case-sensitivity, timezone handling, migration ordering, and concurrent writes
separately.

### JS (static assets only — no bundler for the app itself)

```bash
npm test                          # node --test tests_js/**/*.test.js
npm run build:heic:preview        # rebuild vendored HEIC preview bundle (esbuild)
```

Frontend logic lives in plain `app/static/js/*.js` files loaded directly by
Jinja templates (no build step, no framework). `tests_js/*.test.js` load the
raw source via `fs.readFileSync` + `jsdom`, `eval` it into a constructed DOM,
and assert on resulting behavior/regex — see
`tests_js/report-direct-upload.test.js` for the pattern. Any new interactive
`app/static/js/*.js` file that isn't trivial should get a matching
`tests_js/*.test.js`.

Do not assume frontend checks enforce security. Any object identifier,
permission, upload state, file metadata, MIME type, size, ownership, or project
relationship received from the browser must be revalidated server-side.

### Database / migrations

```bash
flask db migrate -m "message"
flask db upgrade
flask sync-permissions --apply-defaults      # sync RBAC registry after any permission change
```

`app/permissions/registry.py` is the source of truth for permissions/roles;
DB rows are only ever synced by explicitly running `sync-permissions`, never
implicitly at startup.

Do not generate a migration merely because SQLAlchemy metadata differs. First
inspect the complete migration history, legacy compatibility requirements,
production data implications, constraint naming, downgrade behavior, and
whether the difference is intentional.

### Useful CLI commands (`app/cli.py`)

* `flask seed-admin` / `flask reset-local-dev` / `flask reset-database` — local
  environment bootstrap (production-guarded, requires `--allow-production` +
  explicit `--confirm` string).
* `flask security-audit` — safe, read-only production configuration checks.
* `flask assert-report-attachments-s3-only` — verifies no pre-Phase-8 local
  attachment rows remain.
* `flask worker-config-check`, `scripts/start-media-worker.sh` — Celery media
  worker (queues: `media_image`, `media_video`, `storage_cleanup`,
  `bulk_download`).
* `flask reconcile-media-jobs` — recover committed Celery jobs after a broker
  outage.
* `flask cleanup-expired-report-upload-sessions`,
  `flask daily-report-upload-sessions` — manage direct-to-S3 upload sessions
  for Daily Report attachments.

During audit tasks, classify CLI commands before running them:

* Read-only inspection commands may be run normally.
* Commands that reconcile, clean up, seed, reset, migrate, synchronize, enqueue,
  retry, or delete must be assumed mutating unless their implementation proves
  otherwise.
* A command being described as “safe” in documentation is not sufficient;
  verify its implementation before running it against non-test data.

## Architecture

### Module layout

Each business area is a self-contained package under `app/<name>/` with its
own `__init__.py` (Blueprint definition), `routes.py`, and often `services.py`
for non-trivial logic. Blueprints are imported and registered by hand in
`register_blueprints()` in `app/__init__.py` — there is no auto-discovery, so
a new module must be registered there explicitly. Current modules: `auth`,
`account`, `admin` (users/roles/projects/categories admin), `admin_storage`,
`modules` (module switcher landing page), `dashboard` (+ separate `dashboard`
JSON API blueprint), `users`, `projects`, `reports` (+ `reports/create_v2.py`
as a second blueprint for the newer direct-upload report creation flow),
`issues`, `attachments`, `customers`, `project_operations` (contractors +
project updates), `project_documents`, `company_media`, `partners` and its
satellites (`partner_companies`, `partner_fields`,
`partner_field_collections`, `partner_relations`).

Models live centrally under `app/models/` (one file per entity group),
re-exported through `app/models/__init__.py`. Import models from
`app.models`, not from the submodule.

When auditing a module, trace the complete request path rather than reviewing
only its route function:

1. Blueprint registration and URL prefix.
2. Global `before_request` hooks.
3. Route decorators and inline authorization.
4. Object lookup and tenant/project scoping.
5. Service-layer validation and state transitions.
6. Database writes and transaction boundaries.
7. Storage or Celery side effects.
8. Template or JSON serialization.
9. Client-side follow-up requests.
10. Tests covering both allowed and denied cases.

### Three-layer authorization (this is the load-bearing design)

1. **Module gates** — `app/auth/permissions.py`
   (`can_access_reports_module`, `can_access_partners_module`,
   `can_access_project_documents_module`,
   `can_access_company_media_module`). Enforced globally by the
   `require_reports_module_access` `before_request` hook in `app/__init__.py`,
   which maps endpoint-name prefixes (e.g. `"reports."`, `"dashboard."`) to a
   module check, independent of the more granular checks below.
2. **Global roles** — `UserRole` (`SUPER_ADMIN`, `ADMIN`, `VIEWER_ADMIN`;
   `PROJECT_MANAGER`/`REPORTER` are legacy values kept only for
   migrations/fixtures) plus a DB-backed RBAC layer (`app/models/rbac.py`:
   `Role`/`Permission`/`RolePermission`, catalogued in
   `app/permissions/registry.py`). `user.can("resource.action")` is the
   primitive; `role_required`, `viewer_or_admin_required`,
   `super_admin_required` in `app/auth/permissions.py` are decorators built on
   role codes directly.
3. **Per-project capability flags** — `app/project_memberships.py`. A user's
   effective permissions on a *specific* project come from `ProjectUser` rows
   carrying boolean capability flags (`can_view_reports`,
   `can_edit_all_reports`, `can_manage_report_categories`, etc., listed in
   `CAPABILITY_FIELDS`). `PROJECT_ROLE_PRESETS` maps named project roles
   (`PROJECT_VIEWER`, `PROJECT_REPORTER`, `PROJECT_EDITOR`,
   `PROJECT_DOCUMENT_CONTROLLER`, `PROJECT_ISSUE_COORDINATOR`,
   `PROJECT_OWNER`, or `CUSTOM`) to a preset of these flags via
   `preset_flags()`. Global admins/viewer-admins bypass per-project checks
   (`has_global_project_scope`); everyone else is gated per-project.
   `user_has_project_capability` is the core check; helpers in
   `app/auth/permissions.py` (`can_read_project`, `can_edit_report`,
   `can_create_persistent_issue`, ...) wrap it for specific actions, and
   `project_read_required`/`project_write_required`/
   `project_manage_required` are route decorators built on it.

When changing permissions, check all three layers — a route can look protected
by role but still be wide open if the module gate or per-project flag isn't
wired up, or vice versa.

Authorization review must include more than route decorators. Check:

* Direct object references and whether the loaded object belongs to a project
  visible to the current user.
* List, search, export, dashboard, count, autocomplete, download, preview,
  thumbnail, metadata, and JSON endpoints.
* POST, PUT, PATCH, DELETE, bulk actions, retries, cleanup actions, and status
  transitions.
* Hidden UI actions that may still have callable backend routes.
* Global-admin bypass behavior and whether `VIEWER_ADMIN` remains read-only
  where intended.
* Project membership changes that could grant capabilities beyond the actor's
  own authority.
* Legacy role values and fixtures that might accidentally trigger modern
  authorization branches.
* Confused-deputy cases where a permitted parent object is combined with an
  unauthorized child object ID.

Default audit expectation: a missing or ambiguous authorization condition is a
deny-by-default problem. Do not “fix” uncertain access by widening visibility.

### Storage / media pipeline

All file storage (report attachments, project documents, company media) goes
through the S3-compatible abstraction in `app/storage/` — never direct
filesystem writes for user content. `app/storage/providers.py` defines
`StorageProvider` with a `FakeStorageProvider` (in-memory, used in tests) and a
real S3/MinIO-backed implementation selected via `STORAGE_PROVIDER`.

Uploads use presigned PUT URLs generated server-side and posted directly from
the browser (see `report-direct-upload.js` /
`app/reports/direct_uploads.py`) — the app itself never proxies raw upload
bytes. `StorageObject` rows in `app/models/storage.py` are the DB-side record
of what exists in the bucket; `app/storage/quota.py` tracks per-tenant storage
and bandwidth quotas.

`app/media_processing/` runs Celery tasks (image resize/thumbnail, video poster)
against uploaded objects post-commit. `MediaProcessingJob` and
`StorageDerivative` track job state and outputs, and
`flask reconcile-media-jobs` repairs jobs orphaned by a broker outage.

Phase 8 removed all pre-S3 local-filesystem attachment serving — there is no
fallback path; `ReportAttachment` no longer has `file_path` or
`stored_filename`.

For any upload or storage review, verify the full lifecycle:

1. Upload session creation authorization.
2. Server-generated object key and tenant/project namespace.
3. Allowed extension, MIME type, declared size, and quota reservation.
4. Presigned URL method, expiry, content constraints, and bucket scope.
5. Upload completion verification against storage metadata.
6. Prevention of client-selected object keys or cross-session object reuse.
7. Database commit ordering and orphan-object handling.
8. Post-commit media-job enqueue behavior.
9. Idempotency and retry behavior.
10. Authorized preview, thumbnail, stream, and download flows.
11. Deletion, soft deletion, cleanup, retention, and derivative cleanup.
12. Logging and auditability without leaking signed URLs or credentials.

Treat browser-provided filenames, MIME types, sizes, upload IDs, object IDs,
project IDs, attachment IDs, checksums, and completion claims as untrusted.

Presigned URLs are credentials. Do not log them in full, expose them to users
without authorization, store them as permanent database values, or include
them in audit artifacts.

### Request-level guards (`app/__init__.py`)

Three `before_request` hooks run in this order for every request:
`require_login` (redirect unauthenticated users to login, except a small
public-endpoint set), `require_reports_module_access` (module gate, see above),
and — only if `TRUSTED_HOSTS` is configured — `require_trusted_host`.

Security headers (CSP, `X-Frame-Options`, etc.) are added via `after_request`
in `register_security_headers`; the CSP's
`connect-src`/`img-src`/`media-src` are widened dynamically to include the
configured storage origin (`storage_connect_source` in `app/security.py`) so
presigned S3/MinIO URLs work.

When adding or auditing routes, inspect endpoint names carefully because module
gating depends on endpoint-name prefixes. A correctly authenticated route can
still bypass its intended module gate if it is registered under an unexpected
blueprint or endpoint prefix.

Public endpoint exceptions must remain minimal and explicit. New health,
callback, login, static, or operational endpoints must not be added to a public
allowlist without reviewing authentication, information disclosure, host
validation, CSRF expectations, rate limiting, and intended deployment
exposure.

### Configuration

`app/config.py` reads all settings from environment (`.env`, loaded via
`python-dotenv`) with `read_secret()` preferring `<NAME>_FILE` (Docker/Compose
secrets) over a plain env var.

`app/__init__.py` additionally sets a large block of infrastructure defaults
via `app.config.setdefault(...)` (storage limits, Celery queues/time limits,
upload/download quotas) — if you need to change a default, check both `Config`
and this `setdefault` block, because they can diverge.

`production_configuration_errors()` in `app/security.py` raises at startup if
`APP_ENV=production` configuration is unsafe, such as a default secret key.

Configuration review must compare:

* Development, test, Docker, and production values.
* Plain environment variables versus `<NAME>_FILE` secret sources.
* `Config` class defaults versus `app.config.setdefault(...)` defaults.
* Flask web process configuration versus Celery worker configuration.
* Application limits versus reverse-proxy, object-storage, database, and broker
  limits.
* Public origin, trusted host, cookie, proxy-header, CORS, CSP, and storage
  origin assumptions.
* Startup validation behavior and whether unsafe values fail closed in
  production.

Never weaken production validation to make local development easier. Add or
adjust explicit development/test configuration instead.

## Domain and data-integrity expectations

Daily reports, persistent issues, documents, media, partner records, and project
memberships are business records. Mutations should be attributable to an
authenticated user and should preserve created/updated timestamps and relevant
ownership or project relationships.

The partner module intentionally supports extensible custom fields. Field
definitions may evolve, but existing partner values must retain enough snapshot
metadata to remain understandable after a definition is renamed, reordered,
changed, or retired. Avoid migrations or refactors that reinterpret historical
values silently.

Project membership and role preset changes are security-sensitive mutations.
Validate both the target project and the actor's authority, and do not allow an
actor to grant capabilities they are not authorized to manage.

Bulk download, export, search, reporting, and dashboard features must apply the
same authorization scope as ordinary detail pages. Aggregate counts and
filenames can disclose sensitive information even when file contents are not
returned.

Deletion workflows must consider related storage objects, derivatives, pending
jobs, quota accounting, audit history, and retries. Database deletion alone is
not sufficient proof that user content has been safely removed.

Dates and times should be stored and compared consistently, with explicit
attention to UTC versus local Vietnamese display time. Do not rely on naive
datetime behavior across Flask, Celery, PostgreSQL, SQLite tests, browser code,
and object-storage timestamps.

## Security baseline

For security-sensitive implementation or review work, explicitly consider:

* Authentication state and session lifecycle.
* CSRF on every state-changing browser request.
* Rate limits on authentication, upload-session creation, downloads, exports,
  bulk operations, and expensive searches.
* IDOR and broken object-level authorization.
* Mass assignment and unsafe form-to-model updates.
* SQL injection, command injection, template injection, and unsafe subprocess
  usage.
* Stored and reflected XSS in names, notes, filenames, custom fields, SVG/HTML
  content, Chart.js labels, JSON embedded in templates, and flash messages.
* Path traversal and object-key manipulation.
* MIME confusion, active-content uploads, archive bombs, decompression bombs,
  malformed HEIC/video/image files, and parser resource exhaustion.
* SSRF through storage endpoints, media processing, external URLs, webhook-like
  fields, or user-controlled fetches.
* Open redirects and unsafe `next` parameters.
* Host-header and reverse-proxy trust.
* Secret exposure through logs, errors, environment dumps, debug mode, Celery
  task arguments, presigned URLs, or generated reports.
* Race conditions between upload completion, database commit, job enqueue,
  cleanup, deletion, quota reservation, and retry.
* Denial of service through oversized requests, expensive pagination,
  unbounded exports, excessive media dimensions, large metadata, or repeated
  Celery retries.
* Dependency and supply-chain risk in Python, npm, vendored JavaScript,
  HEIC/media decoders, Docker images, and CI actions.

Security findings should use a consistent severity model and explain the actual
preconditions and business impact. Do not inflate severity based only on the
presence of a dangerous API when untrusted data cannot reach it.

## Testing expectations

A security or permission change should normally include tests for:

* Unauthenticated access.
* Authenticated but module-denied access.
* Authenticated module user without project membership.
* Project member lacking the required capability.
* Project member with the required capability.
* Read-only/global viewer behavior.
* Admin and super-admin bypass behavior where intended.
* Cross-project and cross-object ID substitution.
* Invalid, expired, reused, or mismatched upload sessions.
* Failed storage, database, broker, and media-processing operations.
* Duplicate requests, retries, and idempotency.
* Both HTML/browser and JSON/API-style endpoints where both exist.

Do not rely only on status-code assertions. Where relevant, verify that no
database row, object-storage write, quota change, job enqueue, derivative,
audit record, or information disclosure occurred.

Tests that use `FakeStorageProvider`, synchronous tasks, SQLite, mocked Celery,
or disabled infrastructure should be described accurately. Passing them does
not prove real S3, PostgreSQL, Redis/broker, worker, reverse-proxy, or
multi-process behavior.

## Implementation style

Keep changes narrow and consistent with the existing Flask/Jinja architecture.
Do not introduce a SPA framework, automatic blueprint discovery, a second
authorization system, direct filesystem uploads, or startup-time permission
synchronization unless the task explicitly requires an architectural change.

Prefer:

* Existing permission helpers over ad hoc role comparisons.
* Service functions for non-trivial state transitions.
* Explicit project-scoped queries over loading globally and checking later.
* Server-generated storage keys over client-provided paths.
* Post-commit side effects with reconciliation over enqueue-before-commit.
* Idempotent jobs and cleanup operations.
* Small migrations with documented production implications.
* Focused tests for regression and denial paths.
* Vietnamese user-facing messages consistent with existing terminology.
* Structured logs that identify operations without exposing sensitive data.

Avoid unrelated formatting, renaming, dependency upgrades, schema changes, or
large refactors in the same patch as a security fix. A small, auditable patch
is preferred over a broad cleanup.

## Definition of done for security fixes

A security fix is not complete until:

1. The vulnerable path and root cause are identified.
2. The narrowest appropriate server-side control is implemented.
3. Equivalent sibling routes and alternate flows are reviewed.
4. Positive and negative regression tests are added.
5. Existing tests pass without suppressing warnings.
6. Storage, Celery, database, and authorization side effects are considered.
7. User-facing behavior remains understandable in Vietnamese.
8. Configuration or migration requirements are documented.
9. No secrets or sensitive production data appear in commits or reports.
10. The audit finding records the fix status and verification evidence.
