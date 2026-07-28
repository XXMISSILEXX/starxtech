# Findings — Attachments

## Summary

- The live attachment blueprint is `attachments` at `/attachments` (`app/attachments/__init__.py:3`) and is registered by `register_blueprints()` at `app/__init__.py:92,130`. Its six endpoints are `attachments.view`, `.thumbnail`, `.status`, `.status_batch`, `.download`, and `.delete` (`app/attachments/routes.py:14-85`).
- **Module-gate proof:** `create_app()` calls `register_blueprints(app)` before `register_auth_guard(app)` (`app/__init__.py:69-74`). `register_auth_guard()` installs `require_login` first (`app/__init__.py:155-167`) and `require_reports_module_access` second (`app/__init__.py:169-190`). The latter's real tuple includes `"attachments."` and aborts unless `can_access_reports_module(current_user)` is true:
  ```python
  report_endpoints = ("dashboard.", "dashboard_api.", "projects.", "reports.", "issues.", "attachments.", "customers.", "project_operations.")
  ...
  if endpoint.startswith(report_endpoints) or is_report_admin:
      ...
      if not can_access_reports_module(current_user):
          abort(403, description=REPORTS_MODULE_DENY_MESSAGE)
  ```
  (`app/__init__.py:176-189`). Flask processes the registered app-level request hooks before dispatch to a blueprint view; consequently each `attachments.*` endpoint runs login, then the Reports-module gate, then its inline authorization. The attachment blueprint has no competing `before_request` hook.
- `_authorised()` is a real object authorization check, not merely a name: it loads a non-deleted `ReportAttachment`, follows `attachment.section.daily_report`, and checks `can_view_report` against that report's server-derived `project_id` (`app/attachments/routes.py:94-101`; `app/auth/permissions.py:154-155`). This closes attachment-ID and cross-project substitution for every read endpoint that calls it. `status_batch` instead repeats the report check independently for every returned row (`app/attachments/routes.py:54-66`).
- Reads mint 300-second S3-style bearer URLs rather than proxying bytes. The bearer capability is authorized before URL creation and the original/derivative object state is checked before preview/download (`app/attachments/routes.py:16-31, 69-81, 104-114`; default TTL `app/__init__.py:19`). This is a material boundary: after issuance, the object store cannot re-check Flask session or project membership.
- Batch 1 already records the distinct `REPORTS-004` root cause: `attachments.delete` does not enforce `report_attachments.delete` even though the UI does. It is cross-referenced here and deliberately not duplicated.

Files read: 20 application/supporting files, 3 attachment-focused test files, and all required shared audit context files. | Files skipped and why: no primary `app/attachments/` files skipped; no production database, remote object store, or backup snapshot was accessed.

## Findings

### ATTACH-001 — Preview and thumbnail bearer URLs bypass bandwidth enforcement and endpoint rate limits

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-400
- **Location:** `app/attachments/routes.py:14-45`; `app/storage/quota.py:26-37`; `app/extensions.py:12`; `app/__init__.py:19`
- **Reachability:** Any authenticated user that passes the global Reports-module gate and has `can_view_reports` for the attachment's project can call the two GET endpoints. No CSRF token is needed for either GET. A single returned URL is an unauthenticated S3 bearer capability for its TTL.
- **Vulnerable code:**
  ```python
  ensure_bandwidth(current_user, target.file_size, preview=True)
  record_download(current_user, kind="preview", source_type=source,
      module="daily-reports", estimated_bytes=target.file_size, storage_object_id=None,
      derivative_id=derivative.id, estimated_storage_egress_bytes=target.file_size,
      estimated_client_egress_bytes=target.file_size)
  db.session.commit()
  response = redirect(get_storage_provider().create_presigned_download(target.bucket, target.object_key,
      current_app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"], "inline", obj.original_filename)["url"])
  ```
  (`app/attachments/routes.py:22-30`)
  ```python
  response = redirect(get_storage_provider().create_presigned_download(
      derivative.bucket, derivative.object_key,
      current_app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"], "inline", obj.original_filename,
  )["url"])
  ```
  (`app/attachments/routes.py:40-43`)
  ```python
  def ensure_bandwidth(user, amount, *, preview=False):
      from flask import current_app
      used = monthly_bandwidth_bytes(); limit = int(current_app.config["DOWNLOAD_MONTHLY_QUOTA_BYTES"])
      if not preview and used + int(amount) > int(limit * .95): raise ValueError("Đã đạt giới hạn băng thông tháng.")
  ```
  (`app/storage/quota.py:26-29`)
- **Exploit:**
  1. A permitted project member requests `GET /attachments/<authorized-id>` or `/thumbnail` after derivatives exist.
  2. The server returns a signed object-store URL. The preview branch invokes `ensure_bandwidth(..., preview=True)`, which has no limiting branch; the thumbnail branch neither calls `ensure_bandwidth` nor records an event.
  3. The member, or anyone they provide the URL to, repeatedly fetches the bearer URL directly from object storage during the configured 300-second lifetime. Those direct object-store requests do not traverse Flask and cannot be rate-limited or revoked there.
  4. The endpoint has no `@limiter.limit`, while the application's limiter has `default_limits=[]` (`app/extensions.py:12`). Repeating the flow mints further bearer URLs without an application-side request cap.
- **Impact:** A low-privilege report viewer can create unbounded preview/thumbnail egress and associated object-store cost. Thumbnail egress is absent from `DownloadEvent` entirely, so the storage dashboard's monthly accounting cannot even observe it. The configured global monthly quota does not prevent this preview path; it only rejects non-preview issuance after a non-atomic aggregate query.
- **Fix:** Apply an intentional per-user/per-project rate limit to all attachment URL-minting endpoints, account thumbnails, and enforce a quota/reservation before issuing both preview and original URLs. Treat signed URLs as short-lived, non-revocable bearer credentials in the policy.
- **Effort:** M

### ATTACH-002 — Browser-private caching can replay an authorized redirect to a later unauthorized user of the same browser profile

- **Severity:** Low
- **Confidence:** High
- **CWE:** CWE-525
- **Location:** `app/attachments/routes.py:28-31, 40-45`; `app/__init__.py:207-236`
- **Reachability:** An authorized user must first request the preview or thumbnail endpoint. The exposure is then limited to a shared/reused browser profile, the same attachment URL, the 60-second HTTP-cache lifetime, and the signed URL's 300-second lifetime.
- **Vulnerable code:**
  ```python
  response = redirect(get_storage_provider().create_presigned_download(target.bucket, target.object_key,
      current_app.config["STORAGE_DOWNLOAD_URL_TTL_SECONDS"], "inline", obj.original_filename)["url"])
  response.headers["Cache-Control"] = "private, max-age=60"
  return response
  ```
  (`app/attachments/routes.py:28-31`)
  ```python
  response.headers["Cache-Control"] = "private, max-age=60"
  return response
  ```
  (`app/attachments/routes.py:40-45`)
- **Exploit:**
  1. User A, authorized for a report attachment, opens `/attachments/<id>` or `/attachments/<id>/thumbnail`; the browser caches the 302 redirect containing the signed URL.
  2. Within 60 seconds, the browser profile is logged out or used by User B, who lacks access to the project, and requests the same endpoint URL.
  3. A private browser cache may satisfy the fresh redirect without a request to Flask. The cached Location points at the still-valid object-store bearer URL, so User B receives the derivative without `_authorised()` running.
- **Impact:** This is a narrow, local authorization bypass on shared workstations. `private` prevents storage by shared proxies but explicitly permits the browser cache; the global response headers set CSP, `nosniff`, referrer policy, and frame protection, but do not add `Vary: Cookie` or replace this positive cache directive (`app/__init__.py:221-235`).
- **Fix:** Return `Cache-Control: no-store, private` for authorization-bearing redirects (the module already uses this policy for placeholder/status responses at `app/attachments/routes.py:148-151`), or avoid caching signed-location redirects and ensure cache variation is safe for authenticated responses.
- **Effort:** S

## Explicitly checked and found clean

- **Every attachment endpoint has the global Reports module backstop.** The registration, endpoint namespace, global tuple, and order of installed app hooks are quoted in the Summary. This closes the prior uncertainty in the module map.
- **Read-side attachment, report, and project ownership is re-derived from database relationships.** `view`, `thumbnail`, `status`, and `download` call `_authorised()` (`app/attachments/routes.py:16,36,50,71,94-97`), and no read route accepts a report/project/storage ID from the request. `status_batch` filters attachment rows then calls `can_view_report(current_user, attachment.section.daily_report)` for each row (`:61-65`), silently omitting unauthorized IDs. Cross-project attachment-ID substitution is therefore denied.
- **Deleted attachment rows cannot be read or deleted.** `_attachment_or_404()` requires `ReportAttachment.deleted_at.is_(None)` (`app/attachments/routes.py:100-101`). The `ReportAttachment → DailyReportSection → DailyReport` FK chain is non-client-controlled (`app/models/daily_report.py:73-77, 105-108, 120-121`).
- **Preview, thumbnail, and original-download storage state checks are present before storage URL creation.** `_preview_target()` rejects a missing object, `deleted_at is not None`, and an `upload_status` other than `active` (`app/attachments/routes.py:104-107`); `download()` makes the same two-flag check (`:72-74`). The endpoint never reads object bytes directly; it redirects after authorization to `create_presigned_download` (`:28-29, :40-43, :80-81`).
- **Missing derivatives fail closed.** `view`/`thumbnail` return the static processing placeholder when no matching, non-deleted derivative exists (`app/attachments/routes.py:17-20, 37-39, 108-114`); they do not fall back to the original object.
- **Delete has project/report ownership enforcement, permanent cleanup, and an audit record.** The route derives `report` from `attachment.section.daily_report` and requires `can_edit_report` (`app/attachments/routes.py:86-89`). `delete_attachment()` removes unshared derivatives, jobs, database object metadata, and then emits `attachment.delete` before commit (`app/reports/services.py:461-505`). This does not cure Batch 1's separate missing `report_attachments.delete` RBAC check, which is intentionally not repeated here.
- **Filename/object-key traversal is not reachable through daily-report uploads.** Upload keys are constructed with a UUID and `safe_storage_filename` (`app/reports/direct_uploads.py:98-103`; `app/storage/keys.py:32-64`), and no attachment endpoint accepts a bucket or object key.
- **No GET route writes application data.** `view` and `download` do create `DownloadEvent` records and commit (`app/attachments/routes.py:22-27, 75-79`); this is accounting/audit telemetry rather than a resource mutation. `thumbnail` is read-only, which is also the root of ATTACH-001's missing accounting.

## Needs verification

- **Deleted-project behavior is a defense-in-depth gap, not a proven reachable vulnerability.** `_authorised()` does not query `Project.deleted_at`; it only checks `can_view_report` against `report.project_id` (`app/attachments/routes.py:94-97`; `app/auth/permissions.py:154-155`). This pass found no HTTP writer that sets `Project.deleted_at`; the visible admin archive action only sets `project.status = ProjectStatus.ARCHIVED.value` (`app/admin/routes.py:245-251`). If an operator/DB process can soft-delete a project while retaining its reports and memberships, attachments could still be authorized. Prove or disprove with the production lifecycle/processes; do not treat this as a live route vulnerability from this repository alone.
- **`_attachment_status()` checks `obj.upload_status` but omits `obj.deleted_at`** (`app/attachments/routes.py:117-144`). A manually inconsistent active attachment/soft-deleted object could receive `ready` plus internal attachment URLs, but subsequent `view`/`thumbnail` re-check both state flags and return 410 (`:104-107`). The code proves a stale-status correctness gap, not an information or byte-disclosure path; determine whether such a state can occur outside manual data intervention.
- **External-delete/DB-transaction ordering remains a reliability concern.** `delete_attachment()` calls `_delete_storage_objects()` before its database transaction block (`app/reports/services.py:469-472`), and a later database exception rolls back metadata (`:472-505`) after external bytes cannot be rolled back. The source does not establish an attacker-controlled way to force that later database failure. Test fault injection in a non-production environment before classifying this as a security finding.
- **Content-Disposition handling needs object-store verification.** The original filename is request-controlled metadata after extension/MIME/size validation (`app/storage/validation.py:24-47`) and is interpolated into S3's `ResponseContentDisposition` parameter (`app/storage/providers.py:90-92`). This audit did not contact S3/MinIO, so it cannot prove whether the deployed provider rejects/control-character-normalizes malformed filenames. Verify against the actual provider before claiming response-header injection.

## Tool leads closed as false positive/info

- No scanner lead was assigned specifically to `app/attachments/`. The manual leads in `ENDPOINTS-g2.md` were resolved as follows: global module-gate coverage is **confirmed**, not missing; the Batch 1 delete-permission mismatch is a **known, already-reported root cause**; and the two-flag status omission is **Info/needs verification only** because the later storage-serving path fails closed.
- The apparent lack of `@login_required` decorators on attachment views is not an unauthenticated route: app-level `require_login` is installed at `app/__init__.py:155-167` before the Reports module hook, and all attachment endpoint names fall outside its public allow-list.
- S3 presigned URLs are deliberate bearer capabilities with a configured 300-second lifetime, not a standalone IDOR: every issuer in this module first resolves the attachment and authorizes the derived report. ATTACH-001 and ATTACH-002 concern the resulting quota/cache controls, not a missing ownership check at issuance.
