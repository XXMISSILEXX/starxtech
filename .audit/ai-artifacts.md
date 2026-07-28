# AI-Generated Code Failure-Mode Pass

## Summary

- Examined the registered Flask application, every blueprint route module, authorization and validation helpers, storage/media/Celery wiring, manifests, tracked deployment files, templates/first-party JS call sites, tests, migrations by cross-reference, and all required Phase 10 inputs. `claude-partial-audit-backup/` was neither read nor searched.
- Overall posture: application-wide login and most object-level route checks are real, but generated parallel implementations left one effective permission unenforced, one advertised processing control unwired, several dead RBAC catalogue entries, and a production image that contradicts the required runtime.
- New findings: 4 (Medium: 2, Low: 1, Info: 1). Existing findings cross-referenced: 28. Needs verification: 3.
- No remote service, database, container, migration, or PoC was run. Only this file was written.

## Findings

### AI-001 — Production image violates the required Python 3.12 runtime

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-1104 (use of unsupported/outdated component; deployment integrity)
- **Location:** `Dockerfile:2`
- **Reachability:** Every build from the tracked Docker deployment starts from this image. `docker-compose.yml:5-9` builds it for the `web` service.
- **Code quote:**

  ```dockerfile
  FROM python:3.10-slim@sha256:032f5a6e4684899c16735305a83c2a8b1849724b4b6976083ead9aca0846ceb0
  ```

- **Caller/registration evidence:** Docker Compose selects `dockerfile: Dockerfile` at `docker-compose.yml:5-8`; `Dockerfile:25` runs Gunicorn from the resulting Python 3.10 image. The repository instruction requires Python 3.12.
- **Downstream effect:** The production artifact is not the specified/tested runtime. Python-version-sensitive dependency, security, and behavior claims made for 3.12 do not apply to a Compose deployment; local 3.12 test success cannot establish container behavior.
- **Existing finding cross-reference:** None. DEPLOY-001/DEPLOY-002 concern storage/worker startup, not this runtime contradiction.
- **Why this is specifically an AI-generated-code failure mode:** The generated deployment artifact preserved a digest-pinned but stale base image while the project specification and application requirements moved to 3.12.
- **Remediation direction:** Build and test the tracked image from a reviewed Python 3.12 digest, and make the supported runtime explicit in the deployment verification gate.

### AI-002 — Project Documents download permission is catalogue-only; view capability authorizes download

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-863 (Incorrect Authorization)
- **Location:** `app/project_documents/permissions.py:59-63`; `app/project_documents/routes.py:152-156`; `app/project_documents/services.py:157-171`
- **Reachability:** An authenticated Documents-module user with project `can_view_documents` can call `POST /project-documents/files/<file_id>/signed-download`. This remains true even when a custom role intentionally lacks `project_document_files.download`.
- **Code quote:**

  ```python
  def can_download_project_document_file(user, file):
      return bool(file and file.is_active and file.deleted_at is None and _can(user, file.folder, "can_view_documents", "view"))
  ```

  ```python
  if not can_download_project_document_file(current_user, document_file): abort(403)
  return jsonify(create_file_download_url(current_user, document_file))
  ```

- **Caller/registration evidence:** The only production download predicate is the helper above: route `signed_download` calls it at `routes.py:155`; `create_file_download_url` repeats it at `services.py:157-159`; bulk selection also calls it at `services.py:333-339`. The repository-wide fixed-string search `rg -n -F 'project_document_files.download' . -g '!claude-partial-audit-backup/**'` found no application enforcement call site. The catalogue nevertheless registers the code at `app/permissions/registry.py:62`, and the tracked RBAC result says download needs that RBAC permission (`PHASE4_8_FOLDER_SHARING_UX_RESULT.md:5`).
- **Downstream effect:** A role designer cannot withhold document download while granting document viewing. A successful route response mints a 300-second attachment presigned URL through `create_file_download_url` (`app/project_documents/services.py:171`), so this is a backend authorization divergence, not merely a hidden UI control.
- **Existing finding cross-reference:** None. PD-001/PD-002 are ACL-escalation/archive-state defects; they do not cover the catalogue-to-download mismatch. Company Media uses the distinct, correct-looking code path `company_media_files.download` at `app/company_media/permissions.py:79`.
- **Why this is specifically an AI-generated-code failure mode:** Parallel Project Documents and Company Media ACL modules use similarly named, independently generated permission models that diverged: one maps a `download` action to its download permission while the other hardcodes `view`.
- **Remediation direction:** Decide whether viewing includes downloading. If download is separately grantable as the catalogue/docs state, require `project_document_files.download` in the file-download and bulk-download predicates, and add real-endpoint tests for a viewer role without it.

### AI-003 — `MEDIA_ENABLE_PROCESSING` is a no-op configuration control

- **Severity:** Low
- **Confidence:** High
- **CWE:** CWE-1188 (Insecure Default Initialization of Resource / ineffective configuration)
- **Location:** `app/config.py:116`; `app/media_processing/services.py:96-110`
- **Reachability:** Any operator who sets `MEDIA_ENABLE_PROCESSING=false` expects media processing to be disabled. Every successful document/media upload that reaches `enqueue_media_processing_for_storage_object` still stages and dispatches a job.
- **Code quote:**

  ```python
  MEDIA_ENABLE_PROCESSING = os.getenv("MEDIA_ENABLE_PROCESSING", "true").lower() == "true"
  ```

  ```python
  job_ids = stage_media_processing_jobs([storage_object])
  db.session.commit()
  ...
  return dispatch_media_processing_job(job.id)
  ```

- **Caller/registration evidence:** A repository-wide fixed-string search for `MEDIA_ENABLE_PROCESSING` found only `app/config.py:116`; there is no consumer. `app/project_documents/services.py:140-143` and Company Media completion paths call the enqueue service, whose code never reads the flag.
- **Downstream effect:** The documented environment control cannot prevent broker use, worker load, or generation of derived media. In a failure/recovery setting an operator can believe processing is disabled while uploads still queue durable jobs and attempt dispatch.
- **Existing finding cross-reference:** DEPLOY-002 covers absent worker supervision; this is the separate false configuration switch that cannot mitigate it.
- **Why this is specifically an AI-generated-code failure mode:** A configuration setting was added alongside an asynchronous feature but never threaded into the actual dispatcher.
- **Remediation direction:** Either wire the setting into job staging/dispatch with defined pending-state semantics, or remove it from configuration and deployment documentation so operators do not rely on it.

### AI-004 — Three dangerous permission codes describe features with no enforcement surface

- **Severity:** Info
- **Confidence:** High
- **CWE:** CWE-693 (Protection Mechanism Failure; false authorization control)
- **Location:** `app/permissions/registry.py:53-54,73`
- **Reachability:** Role-management users can assign `security.audit`, `system.settings`, and `storage.dashboard.manage`; no registered route, service, navigation item, or template condition consumes any of them.
- **Code quote:**

  ```python
  _permission("security.audit", "Xem nhật ký bảo mật", dangerous=True),
  _permission("system.settings", "Cấu hình hệ thống", dangerous=True),
  _permission("storage.dashboard.manage", "Quản lý Dung lượng & băng thông", dangerous=True),
  ```

- **Caller/registration evidence:** The exact repository-wide searches `rg -n -F 'security.audit' app`, `rg -n -F 'system.settings' app`, and `rg -n -F 'storage.dashboard.manage' app` return only registry/default-list references. Actual storage routes require only `storage.dashboard.view` and `.export` (`app/admin_storage/routes.py:21-31`); branding uses `settings.branding.*` (`app/admin/routes.py:706-728`).
- **Downstream effect:** There is no current direct privilege escalation because there is no corresponding endpoint. The permission editor, however, can represent these codes as dangerous controls even though assigning/removing them changes no runtime authorization outcome.
- **Existing finding cross-reference:** None.
- **Why this is specifically an AI-generated-code failure mode:** The generated permission catalogue outgrew the delivered route/service surface and was never reconciled against it.
- **Remediation direction:** Remove deprecated codes or implement and enforce the owned features; until then mark them deprecated/non-assignable and add a catalogue-versus-enforcement test.

## Security-theatre inventory

| Helper / check | Production callers | Verdict |
| --- | --- | --- |
| `permission_required`, `user_has_permission` (`app/permissions/services.py:14-39`) | Admin, partner, fields, storage, and user routes | Enforcing; fails closed for unknown codes at `:24-28`. |
| `can_access_reports_module` (`app/auth/permissions.py:51-56`) | Global `before_request` at `app/__init__.py:169-189`, reports/dashboard routes, UI | Enforcing. V2 does not pass through the global endpoint-prefix gate, but every V2 handler calls `_project()` and `can_create_report`; Unit 3b proved the current predicate implication. |
| `can_access_partners_module` / Documents / Company Media helpers | Blueprint hooks and navigation | Enforcing; no unconditional success found. |
| `can_*_report`, issue, category predicates (`app/auth/permissions.py:146-219`) | Reports, projects, issues, attachments | Enforcing at current route callers; known route divergences remain cross-referenced below. |
| `role_required`, `viewer_or_admin_required`, `admin_read_required`, `super_admin_required` (`app/auth/permissions.py:14-39`) | Zero production callers | Dead decorators. No route receives their protection. |
| `project_read_required`, `project_write_required` (`app/auth/permissions.py:222-247`) | Test-only synthetic routes in `tests/conftest.py:30-38` | Cross-reference TEST-001; do not treat their passing tests as real-route assurance. |
| `project_manage_required`, `can_write_project`, `can_manage_project`, `can_delete_report_for_project` (`app/auth/permissions.py:202-231`) | Zero production callers; `can_delete_report_for_project` always returns `False` at `:210-211` | Dead compatibility layer, not reachable enforcement. |
| `_check_phase_one_scope` (`app/storage/services.py:190-192`) | `create_upload_batch_presign` | Intentional literal no-op (`return None`); every current Documents/Media route supplies an object-level gate first. It is a fragile service boundary, not a newly reachable bypass. |
| `can_manage_users` (`app/auth/permissions.py:41-43`) | Registered as a Jinja global only (`app/ui.py:206-243`), no template caller | Misnamed (`users.view`, not manage) but no production decision depends on it. |

Search basis for zero/test-only claims: `rg -n '<symbol>' app tests` for each symbol, excluding `claude-partial-audit-backup/**`.

## Sibling-route authorization comparison

| Family | Divergence | Reachability / verdict |
| --- | --- | --- |
| Daily-report legacy routes vs V2 JSON create | V2 blueprint endpoint prefix is absent from the global Reports gate (`app/__init__.py:179`), while legacy is covered. | Clean for current create-only handlers: `_project()` requires the specific `can_create_reports` capability (`app/reports/create_v2.py:29-35`), which implies `can_access_reports_module`; cross-reference Unit 3b explicit-clean result. |
| Project Documents preview vs download | Preview checks view; download is also implemented as view, not the registered download code. | New AI-002. |
| Company Media preview vs download | Preview accepts `view_file`; video preview can return an original URL, while download requires `download_file`. | CM-001. |
| Reports detail/edit/delete and attachment deletion | Report delete/attachment delete use divergent permission checks. | REPORTS-004. |
| Issues edit/close/delete | Delete maps to edit capability rather than dedicated dangerous permission. | ISSUE-002. |
| Dashboard HTML/API | Project/customer/contractor scope fields and issue/report capability checks diverge. | DASHBOARD-001 through DASHBOARD-004. |
| Project Documents and Company Media bulk vs single | Both re-check per object after parent visibility. | Clean for cross-parent ID substitution; CM-003 is the separate uncapped Company Media bulk input issue. |

## Validation-enforcement gaps

| Declaration / validation | Enforcement result |
| --- | --- |
| `project_document_files.download` catalogue code | Not enforced by any document download path: AI-002. |
| `MEDIA_ENABLE_PROCESSING` config | Defined but not consumed: AI-003. |
| `storage.validation.ALLOWED_FILES` | Defined but unused; actual policy comes from `POLICIES` in `app/storage/file_types.py` and `validate_file_metadata`. No distinct impact beyond stale code. |
| `validate_password` (`app/security.py:40-43`) | Zero production callers; Flask-WTF forms call `password_policy_errors` directly. No route accepts a password through this unused wrapper. |
| Partner field collection selected definition IDs | Create/edit accepts submitted IDs without validating active definitions: PARTNER-FIELD-001. |
| Client-side upload/image checks | Server metadata checks exist but do not inspect magic bytes: UPLOAD-001; first-party JS lacks equivalent behavioral tests: JS-001. |
| Database uniqueness relied upon in service prechecks | Concurrent backstops are absent where already reported: PD-004, CM-006, UPLOAD-003, REPORTS-005. |

## Test-confidence cross-references

- TEST-001: only synthetic routes exercise the two dead project decorators identified above.
- TEST-002: high-impact authorization regressions are excluded from the normal suite.
- TEST-003: the common SQLite fixture cannot prove PostgreSQL transactional/concurrency behavior.
- TEST-004 and JS-001: synchronous display-image and first-party JavaScript trust boundaries lack direct behavioral coverage.

No additional cross-module fake-confidence root cause was established: real endpoint tests do cover the normal module guards, but their PostgreSQL/concurrency limits remain the cited findings.

## Duplicated-logic divergence table

| Copy A | Copy B | Difference | Reachability | Existing finding or new root cause |
| --- | --- | --- | --- | --- |
| `app/project_documents/permissions.py:62-63` | `app/company_media/permissions.py:79` | Documents maps download to `can_view_documents`/`view`; Media maps it to `company_media_files.download`/`download`. | Signed and bulk document download | AI-002 |
| `app/project_documents/services.py:429-459` | `app/company_media/services.py:78-95` | Both ACL writers trust the sharer’s submitted flags; Documents retains project capability AND-gate, Media does not. | Restricted folder/album ACL updates | PD-001; verified Company Media critical (not duplicated) |
| `app/projects/routes.py:180-192` | `app/reports/create_v2.py:104-131` | Legacy cancellation eagerly invokes cleanup; V2 cancellation leaves completed bytes/session objects. | Authorized report upload cancellations | REPORTS-001; UPLOAD-002 |
| `app/dashboard/routes.py:23-102` | `app/dashboard/services.py` response builders | HTML/API use distinct authorization/query construction. | Dashboard viewers | DASHBOARD-001–004 |
| `app/media_processing/services.py:96-111` | `app/project_documents/services.py:140-146` | Both tolerate dispatch failure after durable state; the former retains a job, the latter swallows the exception after calling it. | Media/document completion | Intentional best-effort behavior; DEPLOY-002 makes reconciliation/supervision the operational risk. |

## Defaults and development fallbacks

- `APP_ENV` defaults to `local`, `SECRET_KEY` to `dev-secret-key`, storage to `fake`, and production checks run only for exact `production` (`app/config.py:35-41`; `app/security.py:61-82`): CLI-001 and DEPLOY-001.
- Default database/Redis/local-storage addresses and LAN storage CORS fallback are deployment defaults, not hardcoded production credentials; their production reachability is covered by CLI-001 and DEPLOY-001.
- `CELERY_TASK_ALWAYS_EAGER` defaults false and is rejected in exact production mode; no eager-mode path is enabled in tracked Compose.
- Compose disables debug and seeds by default but has placeholder admin identity fields (`docker-compose.yml:14-64`); seed-password behavior is CLI-005.

## Error-handling review

| Location | Result |
| --- | --- |
| `app/company_media/routes.py:71-78` | Reflects `str(e)` from a broad exception to uploaders: CM-005. |
| `app/project_documents/services.py:140-146` | Broad catch/pass after a durable upload/file write. Intentional best-effort dispatch; the durable job created by `enqueue_media_processing_for_storage_object` is the recovery source. Cross-reference DEPLOY-002 for missing supervision. |
| `app/media_processing/services.py:106-111` | Broad catch returns a durable pending job after broker dispatch fails. Deliberate partial-failure behavior, not HTTP success for a failed file write. |
| `app/reports/services.py:725-728` | Logs broker dispatch failure after report commit; documented durable reconciliation design, not swallowed authorization/validation failure. |
| `app/bulk_downloads/services.py:113-115,170-174` | Cleanup re-raises or marks the job failed; no silent successful ZIP response. |
| `app/branding.py:13-19` | Best-effort logo URL failure becomes no logo; no authorization/data mutation. |

No bare `except` or unbounded retry loop was found. Celery media retry is bounded at three retries (`app/media_processing/tasks.py:13-19`).

## Dependency verification

- `requirements.txt` declares every non-stdlib production import identified in `app/` (Flask family, SQLAlchemy, Pillow/pillow-heif, Celery/Redis, boto3, psycopg, Gunicorn). `package.json` and `package-lock.json` contain `esbuild`, `jsdom`, and `heic-to`; `.audit/raw/phantom-packages.txt` reports all three as known.
- No phantom package, absent lock entry, or runtime binary assumption was proven from repository state. External registry/version/CVE verification was not performed; Pillow risk is already ACCOUNT-001/UPLOAD-001 context.
- The one manifest/build inconsistency proven locally is AI-001: the Docker runtime is Python 3.10, not the required 3.12.

## Temporary/simplified implementation review

| Marker / implementation | Runtime consequence |
| --- | --- |
| `_check_phase_one_scope` comment “Future folder/album ACL hooks” and `return None` (`app/storage/services.py:190-192`) | Service-layer scope check is intentionally absent; current routes do enforce object ACLs first. Fragile for future callers, no independently reachable bypass found. |
| V2 module doc says edit remains legacy (`app/reports/create_v2.py:1-5`) | Deliberate partial migration; divergent upload cancellation lifecycle is already REPORTS-001/UPLOAD-002. |
| Fake storage provider (`app/storage/providers.py:34-40,116`) | Local/test capability; exact production mode rejects it (DEPLOY-001). |
| Test-only direct task behavior (`app/bulk_downloads/services.py:129-136`; `app/media_processing/services.py:91-93`) | Tests do not exercise real broker dispatch; cross-reference TEST-003/DEPLOY-002. |

## Registered but unused permission codes

| Permission code | Registry location | Enforcement call sites | Verdict |
| --- | --- | --- | --- |
| `security.audit` | `app/permissions/registry.py:53` | None (`rg -n -F 'security.audit' app`) | Dead dangerous catalogue entry; AI-004. |
| `system.settings` | `app/permissions/registry.py:54` | None (`rg -n -F 'system.settings' app`) | Dead dangerous catalogue entry; AI-004. |
| `storage.dashboard.manage` | `app/permissions/registry.py:73` | None (`rg -n -F 'storage.dashboard.manage' app`) | Dead dangerous catalogue entry; AI-004. |
| `project_document_files.download` | `app/permissions/registry.py:62` | No literal enforcement; Document predicates use view capability | Ineffective permission; AI-002. |

## Config-variable wiring

| Variable | Defined/read at | Effective consumer | Verdict |
| --- | --- | --- |
| `MEDIA_ENABLE_PROCESSING` | `app/config.py:116` | None (exact app-wide search finds definition only) | No-op; AI-003. |
| `TMP_ROOT` | `app/config.py:44`; Compose/example set it | None | Unused legacy/temp-root setting; no current runtime effect. |
| `CELERY_*`, media size/time limits | `app/config.py:99-115` | `app/celery_app.py:49-67`, pipeline/services | Wired, but supervision absent: DEPLOY-002. |
| Storage quota, type, TTL, batch limits | `app/config.py:66-98` | storage services/providers, bulk downloads, report upload routes | Wired; content/magic-byte and race findings are cross-referenced. |
| `MAX_IMAGES_PER_SECTION`, Daily Report limits | `app/config.py:47-56` | report services/routes/direct uploads | Wired. |

## Background-task wiring

| Task | Enqueue call site | Worker registration | Runtime supervision evidence | Verdict |
| --- | --- | --- | --- | --- |
| `media.process_image_derivatives`, `media.process_video_derivatives` | `_dispatch_media_job` at `app/media_processing/services.py:43-49` | `app/media_processing/tasks.py:29-36`; imported by `app/celery_worker.py:12` | No Compose/systemd worker | Enqueued but unsupervised: DEPLOY-002. |
| `bulk_download.build_zip` | `app/bulk_downloads/services.py:129-136` outside tests | `app/bulk_downloads/tasks.py:4-7`; worker import at `celery_worker.py:13` | No Compose/systemd worker | Enqueued but unsupervised: DEPLOY-002. |
| `media.reconcile_media_jobs` | None; exact `.delay`/`.apply_async` search found none | `app/media_processing/tasks.py:39-47` | No scheduler/beat | Defined but never scheduled. |
| `reports.cleanup_expired_upload_sessions` | None; manual CLI path at `app/cli.py:170-171` | `app/media_processing/tasks.py:50-53` | No scheduler/beat | Defined but never scheduled; UPLOAD-002/DEPLOY-002. |
| `bulk_download.cleanup_expired` | None | `app/bulk_downloads/tasks.py:10-13` | No scheduler/beat | Defined but never scheduled. |

## Blueprint and route reachability

All 22 imported blueprints are registered in `app/__init__.py:88-135`; the direct `media_display_preview` route is registered at `:114-115`. The `rg -n '@(bp|api_bp)\.(get|post|route)' app/*/routes.py app/reports/create_v2.py` inventory was compared with that registration list.

| Blueprint/route group | Definition | Registration | Caller/UI | Verdict |
| --- | --- | --- | --- | --- |
| account, admin, admin_storage, attachments, auth, modules, users | corresponding `app/*/routes.py` | `app/__init__.py:112-121,130` | templates/navigation | Reachable. |
| dashboard + dashboard_api, projects, reports, V2 create, issues, customers, project_operations | respective route modules | `app/__init__.py:119-129` | templates and first-party JS | Reachable; existing scope divergences cross-referenced. |
| project_documents, company_media | respective route modules | `app/__init__.py:123-124` | templates and first-party JS | Reachable; AI-002 applies to Documents download. |
| partners, partner_companies, partner_fields, partner_field_collections, partner_relations | respective route modules | `app/__init__.py:131-135` | templates/navigation | Reachable. |
| `users.index` | `app/users/routes.py:5-8` | `app/__init__.py:121` | No navigation link; admin users route is the actual UI | Backend reachable but likely vestigial; protected by `users.view`, no false success. |

## UI-to-backend wiring

| UI action | JS/form source | Backend endpoint | Server enforcement | Verdict |
| --- | --- | --- | --- | --- |
| Daily Report V2 preflight/session/presign/complete/finalize | `app/static/js/daily-report-create-v2.js`; form context `app/projects/routes.py:242-260` | `daily_report_create_v2.*` | `_project()` on every handler | Wired; UPLOAD-002/003 remain. |
| Project Documents file actions | `project-document-file-actions.js`, upload/preview JS and folder template | Documents signed/bulk/upload routes | object predicates | Wired; download permission mismatch is AI-002. |
| Company Media actions | `company-media-*.js`, `media-preview-modal.js`, album template | Company Media routes | blueprint module gate plus per-album/file predicates | Wired; CM-001/003/005 apply. |
| Dashboard charts | dashboard JS modules/templates | dashboard API routes | dashboard/project scope checks | Wired; DASHBOARD-001–004 apply. |
| Account display preview | `display-image-picker.js` | direct app route `/media-display-preview` | login + rate limit | Wired; ACCOUNT-001 test coverage gap is TEST-004. |

## Explicitly checked and found clean

- Required module reports existed and were non-empty before this pass.
- No unregistered blueprint was found; all application routes are behind the app-wide login hook except the explicit login/health/static public set.
- No unconditional-true authorization helper or route that relies solely on a UI check was found beyond the dead/no-op inventory above.
- V2 create’s missing endpoint-prefix module gate does not currently create an authorization bypass because project create capability implies module access (Unit 3b’s source-verified conclusion).
- No new test-only synthetic route beyond TEST-001, no phantom dependency, no repository-proven permissive CORS wildcard, and no unbounded retry loop was found.
- Intentional best-effort broker failure paths retain durable database state and are not reported as false HTTP write success.

## Needs verification

1. Confirm whether production role policy intentionally defines document viewing as download authority; the catalogue and tracked RBAC document contradict that interpretation, but no external authorization specification was read beyond the repository.
2. Confirm any host-level worker, Celery beat, cron, or platform scheduler outside the repository. The tracked deployment has no evidence of one.
3. Verify package publication/security metadata externally only if authorized; this pass intentionally did not contact registries.
