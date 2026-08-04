# Phase 11 Delta — Scope and Coverage Map

## Baseline verification

- **Baseline:** `fc1a117` — `docs(audit): close Phase 10 and record RC readiness`.
- **Audited HEAD:** `e764509c5e2cc174499248c79e7d4ec7fdedfe2a` — `merge: complete phase 5 upload cancellation and cleanup`.
- **Branch / worktree at start:** `Phase12/Progress-and-beyond`; clean (`git status --short --branch`).
- **Delta check:** `git rev-list --count fc1a117..HEAD` = **20 commits**; `git diff --stat fc1a117..HEAD` = **111 files, +7,685/−303 lines**. These match the requested approximate baseline exactly, so this delta audit proceeded.

Commands retained as reproducible evidence:

```bash
git status --short --branch
git log --oneline fc1a117..HEAD
git diff --stat fc1a117..HEAD
git diff --name-status fc1a117..HEAD
git diff --numstat fc1a117..HEAD
```

## Audit boundary and method

Every changed or added file below is in scope. Files are grouped by the trust
boundary they change, rather than by extension. A group marked **deep** is read
end-to-end: registration/guard → route → service/model/storage transaction →
template/JavaScript → tests. A group marked **moderate** is read sufficiently to
verify that it neither weakens the changed boundary nor contradicts the executable
code; documentation is checked against the implementation it describes.

The audit honours the intentional project rules in `CLAUDE.md`: S3-compatible
storage is canonical; no filesystem upload fallback or original-file preview
fallback is permitted; permissions are not startup-synchronised; authorization is
module gate + global RBAC + per-project capability; and media derivatives are
post-commit/asynchronous. Those designs are not findings unless this delta violates
them.

## Delta units

| Unit | Changed files (all are in scope) | Depth | Risk | Why / coverage objective |
|---|---|---|---|---|
| U1 — private storage cache and signed delivery | `app/storage/cache.py`, `downloads.py`, `exceptions.py`, `providers.py`, `services.py`, `validation.py`, `limits.py`, `company_media_errors.py`; `app/models/storage.py`; `app/attachments/routes.py`; `app/branding.py`; `deploy/nginx/starx-report.conf`; `tests/test_media_cache.py`, `test_signed_download_contract.py`, `test_storage_foundation.py`; `tests_js/media-cache-frontend.test.js` | **Deep** | **Critical** | New local read-through cache and X-Accel delivery sit between private S3 objects and users. Verify cache admission/path permissions, authorization-before-cache, no original/ZIP delivery, signed URL construction, expiry, quotas, headers, error disclosure, cleanup and Nginx assumptions. The unchanged media/display, permission, task and quota callers are read where this path reaches them. |
| U2 — Company Media direct upload, limits and cancellation | `app/company_media/routes.py`, `services.py`, `upload_cleanup.py`; `app/static/js/company-media-upload.js`, `company-media-covers.js`; `app/templates/company_media/album.html`, `index.html`; migrations `20260730_0028_company_media_selection_item_idempotency.py`, `20260731_0029_company_media_upload_cleanup.py`; `tests/test_company_media_permissions_ux.py`, `test_company_media_phase4_idempotency.py`, `test_company_media_phase4_postgresql.py`, `test_company_media_phase5_cleanup.py`, `test_company_media_phase5_postgresql.py`, `test_company_media_upload_limits.py`; `tests_js/company-media-upload.test.js` | **Deep** | **Critical** | New presign batches, selection limits, unique/idempotency constraint and abandoned-upload cleanup mutate private storage and DB state under retries/races. Verify all endpoint guards and endpoint-prefix module gate, server-side limits, object ownership/session binding, PostgreSQL concurrency, cancellation cleanup and worker/CLI lifecycle. |
| U3 — report attachment edit/direct-upload regression | `app/reports/constants.py`, `direct_uploads.py`, `routes.py`, `services.py`; `app/projects/routes.py`; `app/static/js/report-direct-upload.js`, `daily-report-create-v2.js`; `app/templates/reports/detail.html`, `form.html`, `templates/projects/index.html`; `tests/helpers/daily_report_create_v2.py`, `tests/test_daily_report_create_v2.py`, `test_reports_attachments.py`; `tests_js/report-direct-upload.test.js`, `daily-report-create-v2.test.js` | **Deep** | **High** | Changed attachment replacement/deletion and a raised per-subtask count can invalidate the old report/session isolation and capability guarantees. Verify server enforcement versus UI, replacement ownership, cleanup ordering, archival behavior and the intentionally exceptional `daily_report_create_v2` module-gate prefix. |
| U4 — Company/Project document and customer integration | `app/project_documents/routes.py`, `services.py`; `app/customers/routes.py`, `services.py`; `app/templates/project_documents/folder.html`, `customers/detail.html`; `app/static/js/project-document-folder-actions.js`, `project-document-preview.js`; `tests/test_project_documents_upload_ux.py`, `test_project_customer_assignment.py`; `tests_js/project-document-preview-download.test.js` | **Deep** | **High** | New document folder actions/download presentation and project–customer association can create IDOR, CSRF, lifecycle or disclosure regressions. Read old document permissions/download code and customer/project scope helpers because they are on the changed request path. |
| U5 — account preference/theme/display media | `app/account/preferences.py`, `routes.py`; `app/models/user.py`; migration `20260729_0027_add_user_ui_preferences.py`; `app/static/js/account-preferences.js`, `theme-preload.js`; `app/static/css/app.css`; `app/templates/account/profile.html`, `base.html`; `tests/test_account_preferences.py`; `tests_js/theme-preferences.test.js` | **Deep** | **Medium** | Adds user-controlled persistence and browser-preload rendering. Verify authenticated self-only mutation, CSRF, input allow-list/defaults, template/DOM injection and migration compatibility. Cache/media callers in U1 are cross-read for avatar/branding effects. |
| U6 — administration and project-management UI | `app/admin/routes.py`; `app/templates/admin/branding.html`, `admin/projects/form.html`, `admin/projects/index.html`; `app/static/js/app.js`; `tests/test_phase10_lifecycle_disclosure.py` | **Deep** | **High** | A Phase-10 repaired privilege boundary has been touched. Re-audit the changed admin mutations for regression against CRIT-01..05 and validate project/customer form inputs and branding rendering. |
| U7 — application registration, runtime configuration and CLI | `app/__init__.py`, `app/config.py`, `app/cli.py`; `gunicorn.conf.py`; `.env.example`; `tests/test_docker_deployment.py` | **Deep** | **Critical** | New endpoint prefixes, defaults and cleanup commands can bypass module gates, fail open in production or turn an inspection command into a mutation. Verify all defaults against Compose and CLI implementation, production validation and command classification. |
| U8 — deployment/operations contract | `docker-compose.yml`, `DEPLOY_UBUNTU.md`, `DOCKER_DEPLOY.md`, `README.md`, `.gitignore`, `docs/S3_document_media_execution_plan/13_DEPLOYMENT_AND_OPERATIONS.md`, `PHASE11_CLOUDFLY_UPLOAD_TEST_CHECKLIST.md` | **Deep** | **High** | Bind mounts and Nginx cache permissions make the new delivery boundary deployable or unsafe. Compare documentation and environment examples to actual Compose/Nginx/config behavior, keeping secrets and deployment-specific values out of reports. |
| U9 — dashboard/frontend chart compatibility | `app/static/js/contractor-dashboard-charts.js`, `project-dashboard-charts.js`, `scoped-dashboard-charts.js` | **Moderate** | **Medium** | Client changes consume scoped aggregate data audited in Phase 10. Check they do not reintroduce unsafe DOM sinks, broad unbounded requests or private data disclosure; old dashboard services/routes are read only as required by these calls. |
| U10 — implementation-history / evidence documentation | `docs/Phase11_Fix_Single_Download_CONFIG_AND_UI/{EVIDENCE_MAP.md,PHASE2_IMPLEMENTATION_REPORT.md,PHASE3A_IMPLEMENTATION_REPORT.md,PROPOSED_FIX_PLAN.md,README.md,TEST_AND_ROLLOUT_PLAN.md,VERIFICATION_REPORT.md}`; `docs/Phase11_Safe_Race_Idempotent_Upload/{AUDIT_COMMANDS_AND_RESULTS.md,CURRENT_FLOW.md,FINDINGS.md,IMPLEMENTATION_OPTIONS.md,MIGRATION_PLAN.md,PHASE4_IMPLEMENTATION_REPORT.md,PHASE5_IMPLEMENTATION_REPORT.md,PHASE5_INVESTIGATION.md,PROPOSED_PHASE4_SCOPE.md,README.md,SCHEMA_AND_CONSTRAINT_AUDIT.md,TEST_AND_VERIFICATION_PLAN.md,TRANSACTION_AND_IDEMPOTENCY_DESIGN.md}` | **Moderate** | **Medium** | 20 new design/evidence documents materially claim safety of high-risk upload/download changes. Check claims against source/tests and record contradictions; documents themselves do not create a runtime entry point. |

The table enumerates **111 changed paths**: U1 16, U2 16, U3 15, U4 11,
U5 11, U6 6, U7 6, U8 7, U9 3, U10 20. The complete line-level
`git diff --name-status` command above remains the authoritative inventory.

## Deliberately outside the delta scope

The following unchanged areas are not re-audited merely because they exist. They
were covered before the baseline and are not on a changed request/data path. They
will be read if a delta call chain reaches them; that exception is recorded in the
relevant delta finding or verification note.

| Excluded unchanged area | Prior evidence | Reason it is not silently skipped |
|---|---|---|
| Dashboard routes, services and templates (except the three changed chart clients in U9) | `findings-9-dashboard.md` | Full HTML/JSON scope and capability parity audit already completed; only changed JavaScript contract is revisited. |
| Issues module | `findings-7b-issues.md` | No delta route/service/template calls it. |
| Partner, companies, fields, collections and relations modules | `findings-6a-partners.md`, `findings-6b-partner-fields-relations.md` | No changed module gate, route, model or service reaches these module flows. |
| Project operations / contractors | `findings-8-customers-operations.md` | No changed request path reaches it; only its chart-client consumer is read in U9. |
| Auth, RBAC registry and core project-membership implementation | `FOUNDATION-A1.md`, `findings-1-cli.md`, `findings-2-admin.md` | These remain baseline evidence; their helpers are nevertheless cross-read wherever U2/U3/U6/U7 calls them. |
| Old attachment base service/model and media-processing worker tasks | `findings-3b-uploads.md`, `findings-7-attachments.md`, `FOUNDATION-B.md` | Not changed wholesale; read only as U1/U3 delivery and cleanup paths invoke them. |
| Unchanged tests and JavaScript outside listed changed files | `findings-11-frontend-js.md`, `findings-13-test-integrity.md` | The audit focuses on changed tests for misleading/regressive coverage and reads old tests only when needed to establish a changed contract. |

## Planned outputs

1. `ENDPOINTS-g5.md`: all new or behaviorally changed endpoints only, including a
   per-row test of whether its endpoint name matches the global
   `require_reports_module_access()` prefix map.
2. Unit findings and a regression record where warranted, using the exact heading,
   evidence, confirmed-clean and needs-verification style of
   `findings-9-dashboard.md`.
3. A delta verification/closure note that distinguishes confirmed defects, test
   gaps, operational prerequisites, intentional designs and clean results.
