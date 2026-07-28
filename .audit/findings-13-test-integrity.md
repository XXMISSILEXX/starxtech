# Findings — Unit 13: test-suite integrity

## Summary

- The collected suite contains 325 pytest cases from 43 `tests/test_*.py` modules and three Node test modules.  It primarily uses a Flask test client against real registered routes, but it also uses direct service calls and fakes for storage/async work.
- The shared fixture creates a fresh in-memory SQLite schema with `db.create_all()` rather than applying migrations, disables CSRF, and seeds fixed principals/projects.  It therefore cannot prove PostgreSQL migration, locking, production-CSRF, S3, or broker behaviour.
- Four authorization assertions exercise two synthetic fixture-only routes.  They establish the behaviour of two unused decorators, not the authorization of a registered production endpoint (PRE-002).
- Five high-value privilege-escalation regressions exist only under `.audit/poc/critical_*.py`; default pytest collection does not collect them.  They are evidence of coverage that is absent from the normal suite, not expected-suite passes.
- No test references the account avatar endpoints or the direct `/media-display-preview` endpoint.  This leaves the synchronous Pillow/format/pixel-limit path without a regression test.

Files read: 50 (43 Python test modules, `conftest.py`, two helper modules, `.gitkeep`, three JS test modules) plus five existing `.audit/poc/critical_*.py` evidence files | Files skipped: none in the assigned test paths.  `claude-partial-audit-backup/` was not read or searched.

## Test-file inventory

| Test file | Classification | DB/backend | Main behaviour actually exercised |
|---|---|---|---|
| `tests/conftest.py` | fixture + synthetic routes | SQLite memory | app fixture, fixed seed data, `test_project_read/write` only |
| `tests/helpers/daily_report_create_v2.py` | real HTTP helper + fake object upload | SQLite/FakeStorage | V2 preflight/presign/complete/finalize orchestration |
| `tests/helpers/report_direct_upload.py` | real HTTP helper + fake object upload | SQLite/FakeStorage | legacy direct-upload orchestration |
| `tests/test_admin_screens.py` | real HTTP | SQLite | admin users/projects/memberships/categories UI and RBAC |
| `tests/test_auth_permissions.py` | real HTTP + synthetic-route subset | SQLite | login/change-password plus unused project decorators |
| `tests/test_celery_context.py` | service/task unit, mock-heavy | SQLite | task wrapper/context/retry; mocked pipeline/service |
| `tests/test_company_media_permissions_ux.py` | real HTTP + service | SQLite/FakeStorage | album ACL and mutation deny paths |
| `tests/test_daily_report_create_v2.py` | real HTTP + static check | SQLite/FakeStorage | V2 idempotency, dates, UUIDs, create UI JS imports |
| `tests/test_dashboard_issues.py` | real HTTP + service | SQLite | dashboard scopes, issue/report aggregates, query-count checks |
| `tests/test_docker_deployment.py` | config/filesystem unit + one real HTTP route | SQLite | config parsing/deploy text, `/healthz` |
| `tests/test_document_library_custom_roots.py` | real HTTP | SQLite | custom roots/project-root creation |
| `tests/test_issue_buttons_html.py` | real HTTP | SQLite | issue-page visibility/form validation markup |
| `tests/test_login_membership_ux.py` | real HTTP | SQLite | login next, membership lifecycle |
| `tests/test_media_processing_foundation.py` | service/pipeline unit, mock-heavy | SQLite/FakeStorage | image/video pipeline with mocked Celery/subprocess |
| `tests/test_mobile_nav_markup.py` | real HTTP | SQLite | mobile account/navigation markup |
| `tests/test_module_switch_visibility.py` | real HTTP | SQLite/FakeStorage | module cards and company-media ACL visibility |
| `tests/test_native_bulk_download_form.py` | real HTTP + fake provider | SQLite/FakeStorage | native download form/preflight |
| `tests/test_partner_demo_seed.py` | CLI/service + real HTTP | SQLite | partner-demo seed idempotency and display |
| `tests/test_partner_module.py` | real HTTP | SQLite | module choice, partner field/value forms |
| `tests/test_partner_rbac.py` | real HTTP | SQLite | partner module/permission deny paths |
| `tests/test_partner_ux_improvements.py` | real HTTP | SQLite | partner/company/department/relationship validation |
| `tests/test_phase9_contractors.py` | service + real HTTP | SQLite | contractor/assignment lifecycle and project scope |
| `tests/test_phase9_customers.py` | service + real HTTP | SQLite | customer move/archive/scope and SQLite migration check |
| `tests/test_phase9_dashboard_ui_polish.py` | real HTTP/static source | SQLite | dashboard/project-operations markup contracts |
| `tests/test_phase9_project_operations_ui.py` | real HTTP | SQLite | operations workspace/search/accessibility |
| `tests/test_phase9_project_updates.py` | service + real HTTP | SQLite | project-update scope/date/soft delete |
| `tests/test_phase9_rbac.py` | service + real HTTP + synthetic-route subset | SQLite | registry/scope/dashboard checks; two synthetic decorator calls |
| `tests/test_phase9_today.py` | real HTTP | SQLite | current-day report scope |
| `tests/test_phase9_vietnamese_ui.py` | static-template unit | no DB | localized enum/template output |
| `tests/test_production_ops.py` | service/config/filesystem unit | SQLite | audit/config/backup-script checks |
| `tests/test_project_documents_core.py` | service + real HTTP | SQLite | folders, ACL, move/archive permission paths |
| `tests/test_project_documents_folder_lifecycle_ux.py` | real HTTP | SQLite | folder filters/lifecycle markup |
| `tests/test_project_documents_permissions_ux.py` | service + real HTTP | SQLite | folder ACL UI and mutation permission |
| `tests/test_project_documents_upload.py` | service + real HTTP, mock-heavy subset | SQLite/FakeStorage | upload/finalize/archive/download/media job paths |
| `tests/test_project_documents_upload_ux.py` | real HTTP + fake provider | SQLite/FakeStorage | upload controls, ACL markup, S3 config shape |
| `tests/test_project_manager_permissions.py` | real HTTP | SQLite | project-scoped reports/categories/issues mutation |
| `tests/test_rbac_navigation.py` | real HTTP | SQLite | roles navigation/route access |
| `tests/test_report_create_entry.py` | real HTTP | SQLite | report-create entry visibility |
| `tests/test_reports_attachments.py` | real HTTP + fake provider | SQLite/FakeStorage | reports, direct upload, attachment/report deletion |
| `tests/test_reports_route_namespace.py` | real HTTP/router | SQLite | endpoint names and legacy-route removal |
| `tests/test_security_hardening.py` | service/config + real HTTP | SQLite/FakeStorage | headers, attachment signed redirect, CLI safeguards |
| `tests/test_storage_dashboard.py` | real HTTP + service | SQLite | storage dashboard/export/aggregates |
| `tests/test_storage_foundation.py` | service-only | SQLite/FakeStorage | storage metadata validation/lifecycle |
| `tests/test_storage_namespace_bulk_download.py` | service-only | SQLite/FakeStorage | key namespaces and ZIP access |
| `tests/test_three_layer_authorization.py` | service-only | SQLite | membership capability predicates |
| `tests/test_vietnamese_dates.py` | service-only | no DB | strict date parser/formatting |
| `tests_js/daily-report-create-v2.test.js` | JS unit (JSDOM/source) | n/a | client create-V2 DOM contract |
| `tests_js/report-direct-upload.test.js` | JS unit (JSDOM/source) | n/a | direct-upload DOM contract |
| `tests_js/scoped-dashboard-charts.test.js` | JS unit (JSDOM/source) | n/a | chart rendering/update contract |

## Findings

### TEST-001 — Synthetic routes are the only coverage of two dead authorization decorators
- **Severity:** Info (test-confidence weakness; not a production vulnerability)
- **Confidence:** High
- **CWE:** CWE-693 (protection mechanism not tested where used)
- **Location:** `tests/conftest.py:29-38`, `tests/test_auth_permissions.py:73-95`, `tests/test_phase9_rbac.py:75-76`
- **Reachability:** Test-only. `app()` adds routes after `create_app()` only for the fixture; they are absent from normal application registration.
- **Evidence:**
  ```python
  # tests/conftest.py:29-38
  @app.get("/test/projects/<int:project_id>/read")
  @project_read_required()
  def test_project_read(project_id):
      return {"project_id": project_id}

  @app.post("/test/projects/<int:project_id>/write")
  @project_write_required()
  def test_project_write(project_id):
      return {"project_id": project_id}
  ```
  ```python
  # tests/test_auth_permissions.py:73-95
  response = client.post("/test/projects/1/write")
  assert response.status_code == 403
  ...
  response = client.get("/test/projects/2/read")
  assert response.status_code == 403
  ```
  `rg` found these two decorator call sites only in `tests/conftest.py`; production routes hand-roll their checks.  This independently confirms PRE-002 rather than creating a duplicate application finding.
- **Impact:** A green suite proves only `project_read_required`/`project_write_required`, not any live endpoint’s module gate, permission, object lookup, or project capability chain.
- **Recommended future test:** Replace/add coverage using registered representative read/write routes with an unauthorized and cross-project actor; retire the synthetic routes once no longer needed as unit tests.

### TEST-002 — High-impact authorization regressions are excluded from the normal test suite
- **Severity:** Medium (test-confidence weakness; not a production vulnerability)
- **Confidence:** High
- **CWE:** CWE-693
- **Location:** `.audit/poc/critical_01_admin_self_grant_super_admin_test.py:11-40`, `.audit/poc/critical_02_super_admin_password_reset_test.py:11-40`, `.audit/poc/critical_03_roles_manage_self_grant_test.py:13-57`, `.audit/poc/critical_04_project_membership_self_insert_test.py:13-62`, `.audit/poc/critical_05_company_media_acl_escalation_test.py:11-56`, `pytest.ini:1-3`
- **Reachability:** CI/local default pytest collection, which produced 325 collected tests.  The five files live outside pytest’s `test*.py` discovery path and are not normal test-suite members.
- **Evidence:**
  ```python
  # .audit/poc/critical_01_admin_self_grant_super_admin_test.py:24-35
  response = client.post(
      f"/admin/users/{admin_id}/edit",
      data={..., "role_id": str(super_admin_role_id), ...},
  )
  ...
  assert secure
  ```
  ```ini
  # pytest.ini:1-3
  [pytest]
  filterwarnings =
      error
  ```
  These tests cover lower-admin self-promotion, lower-admin reset of a super-admin password, self-grant through role permissions, self-insert into an unrelated project, and ACL self-escalation.  They are useful evidence but are neither collected by `pytest --collect-only` nor part of `tests/`.
- **Impact:** Regressions on five sensitive real routes can pass the ordinary suite undetected.  This is separate from the audited route findings themselves.
- **Recommended future test:** Move or reproduce each as an ordinary `tests/test_*.py` regression after its owning finding is accepted; keep normal test names and fixture isolation.

### TEST-003 — The common fixture cannot prove production security controls or PostgreSQL transactional behaviour
- **Severity:** Medium (evidence/test-confidence weakness; not a production vulnerability)
- **Confidence:** High
- **CWE:** CWE-754 / CWE-841 (unverified failure and state-transition behaviour)
- **Location:** `tests/conftest.py:10-22,40-45`, `app/media_processing/services.py:86-93`, `app/reports/services.py:182-185`, `app/reports/direct_uploads.py:227-233,260-262`, `app/models/audit_log.py:1,16-17`
- **Reachability:** Every Python HTTP test that uses the shared `app` fixture.
- **Evidence:**
  ```python
  # tests/conftest.py:10-22
  class TestConfig:
      TESTING = True
      SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
      ...
      WTF_CSRF_ENABLED = False
      SESSION_COOKIE_SECURE = False
  ```
  ```python
  # tests/conftest.py:40-45
  with app.app_context():
      db.create_all()
      seed_test_data()
      ...
  ...
  db.drop_all()
  ```
  ```python
  # app/media_processing/services.py:86-93
  def dispatch_media_processing_job(job_id):
      ...
      if current_app.testing:
          return job
      return _dispatch_media_job(job)
  ```
  ```python
  # app/reports/services.py:182-185
  session = db.session.scalar(...with_for_update())
  ...
  upload_items = db.session.scalars(...with_for_update()).all()
  ```
- **Impact:** The suite does not prove CSRF enforcement, secure-cookie delivery, Alembic upgrade compatibility, PostgreSQL `JSONB` semantics (`app/models/audit_log.py:1,16-17`), foreign-key/check/index enforcement, `FOR UPDATE` locking, competing finalize requests, S3 completion semantics, or actual Celery `.delay()` delivery.  The FakeStorage and task mocks are legitimate isolation for application logic, but they invalidate any claim about real object storage/broker integration.
- **Recommended future test:** Add a separately provisioned PostgreSQL integration job that runs migrations and exercises concurrent upload finalization; add an authenticated production-like Flask configuration with CSRF enabled; test storage/broker adapters in their own controlled integration environment.

### TEST-004 — The account image and direct display-preview trust boundary has no test coverage
- **Severity:** Medium (ordinary missing security regression coverage; runtime image risk belongs to Unit 10)
- **Confidence:** High
- **CWE:** CWE-400
- **Location:** `tests/conftest.py:10-22`, `app/__init__.py:114-115`, `app/account/routes.py:14-38`
- **Reachability:** Any authenticated user can reach the account profile/avatar routes; `register_blueprints()` separately registers the POST preview handler.
- **Evidence:**
  ```python
  # app/__init__.py:114-115
  from app.account.routes import media_display_preview
  app.add_url_rule("/media-display-preview", endpoint="media_display_preview",
                   view_func=media_display_preview, methods=["POST"])
  ```
  ```python
  # tests/conftest.py:18-22
  UPLOAD_ROOT = "/tmp/starx-test-uploads"
  MAX_UPLOAD_MB = 10
  MAX_IMAGES_PER_SECTION = 3
  DAILY_REPORT_MAX_FILES_PER_SECTION = 3
  ```
  A full assigned-path search found no reference in `tests/` or `tests_js/` to `avatar`, `media-display-preview`, `display_images`, `Image.open`, `DecompressionBomb`, or `MAX_IMAGE_PIXELS` (the sole `Image.open` phrase is a comment in `tests/test_media_processing_foundation.py:41-42`, for a separate worker pipeline).
- **Impact:** There is no regression evidence for account-only authorization, deletion/replacement ordering, malformed/polyglot image rejection, pixel/decompression limits, output headers, or CSRF behaviour on this direct route.  This does not itself prove Unit 10’s image finding.
- **Recommended future test:** Add real Flask-route tests with CSRF enabled for own-avatar only, corrupt/oversized/pixel-bomb fixtures, allowed/disallowed formats, replacement rollback, and `/media-display-preview` auth/cache/content-type handling.

## Security regression test gaps

| Priority | Surface | Real route tested? | Negative path? | Gap | Recommended future test |
|---|---|---|---|---|---|
| P0 | User edit / role assignment | Yes | Partial | No ordinary lower-admin self-promotion test; POC only | Lower-admin POSTs own user edit with SUPER_ADMIN role, assert reject and unchanged role |
| P0 | Password reset | Partial | No relevant lower-admin target test | POC only for reset of SUPER_ADMIN | Assert lower admin cannot reset super-admin and no secret is rendered |
| P0 | Role permission update | Partial | No self-grant test | POC only | Role manager attempts grant to own role, assert no grant |
| P0 | Project membership assignment | Yes | Partial | No arbitrary-self-insert test | Assignment manager attempts owner-equivalent membership in unscoped project |
| P0 | Company Media ACL | Yes | Yes, broad | Share-only self-escalation is POC-only | ACL holder attempts to grant own edit/delete/upload rights |
| P1 | Report delete | Yes | Yes | Assigned vs unassigned path covered | Add concurrent/delete-vs-edit rollback coverage on PostgreSQL |
| P1 | Attachment delete | Yes | Yes | Project and capability negatives covered | Add storage-delete failure/transaction rollback test |
| P1 | Issue delete | Yes | Partial | Tests do not distinguish the dedicated `issues.delete` permission from edit capability | Assert edit-only actor’s delete result matches intended permission design |
| P1 | Contractor assignment | Yes | Yes | Unassigned-project denial covered | Add concurrent reassignment/unique-index PostgreSQL test |
| P1 | Customer project move | Yes | Partial | Scope/read-only negatives exist; cross-customer forged-ID cases are limited | Actor supplies unrelated target customer/project pair |
| P1 | Upload session/finalize | Yes | Yes | Validation/idempotent retry covered only on SQLite/FakeStorage | Concurrent duplicate finalize with real PostgreSQL locks and provider completion failure |
| P1 | Dashboard object scope | Yes | Yes | Multiple project/customer/contractor scope negatives covered | Keep a per-capability issue-detail regression for reported dashboard drift |
| P1 | Partner PII | Partial | Partial | Module/permission tests exist, not an explicit unauthorised sensitive-field disclosure matrix | Unauthorised/limited actor requests partner/company detail and media preview |
| P0 | Avatar and media display preview | No | No | No test references either endpoint | Full authorization, CSRF, malformed image, and response-header tests |

## Explicitly checked and found clean

- No `pytest.mark.skip`, `pytest.mark.xfail`, `pytest.skip`, `pytest.xfail`, or broad `except:` occurrence was found in the assigned test files.
- The suite has meaningful assertions beyond status-only checks in its sensitive report/attachment tests: for example `tests/test_reports_attachments.py:311-321` verifies DB rows, fake-provider deletes, and an audit row after attachment deletion.
- Real negative-route coverage exists for report delete (`tests/test_project_manager_permissions.py:107-110`), issue delete by a reporter (`:137-153`), attachment read/delete (`tests/test_reports_attachments.py:282-293,324-361`), Company Media ACL mutation (`tests/test_company_media_permissions_ux.py:114-141`), contractor project scope, upload input validation, and dashboard scope.
- Monkeypatches are restored by pytest.  Most FakeStorage use legitimately isolates S3; the Celery/pipeline mocks and `current_app.testing` bypass are correctly classified above as proof limits, not test pollution or a production vulnerability.
- Fixed IDs are intentional fixture isolation.  The fixture recreates/drops the schema per test, so no order-dependent persistent database state was observed within the isolated test process.

## Needs verification

- Run a controlled PostgreSQL integration job (outside this batch) to prove migration chain, FK/check/index enforcement, `JSONB`, and `with_for_update()` race behaviour.  SQLite cannot establish these guarantees.
- Run an external storage/Celery integration job to prove presigned-upload completion, broker dispatch/retry, and cleanup.  Current tests use FakeStorage and return early from `dispatch_media_processing_job()` while `TESTING` is true.
- The inventory classifies tests by the code they invoke, not line coverage.  A route test with a happy-path response does not prove every guard in its handler.
