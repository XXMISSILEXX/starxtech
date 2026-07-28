# Findings — Reports core

## Summary

- The `reports.` and `projects.` blueprints are globally login- and Reports-module-gated. Per-project capability checks remain route-local and are the decisive authorization control.
- Primary scope was read in full: `app/reports/__init__.py`, `app/reports/routes.py`, `app/reports/services.py`, and every Python file in `app/projects/`.
- Seven findings: one High, five Medium, and one Low. The most consequential is a project-scoped cancellation route that synchronously purges expired/cancelled upload sessions for every project.
- Daily-report creation/editing does not instantiate or link `PersistentIssue`; persistent issues are only created by the explicit issue routes/services.

## Findings

### REPORTS-001 — Cancelling one upload session purges other projects’ sessions and objects

- **Severity:** High
- **Confidence:** High
- **CWE:** CWE-862, CWE-400
- **Location:** `app/projects/routes.py:180-190`; `app/reports/direct_uploads.py:290-311`
- **Reachability:** Any authenticated Reports-module user with `can_create_reports` on one non-deleted project can POST their own session cancellation endpoint. CSRF applies globally.
- **Exact code quote:**
  ```python
  session = report_upload_session(current_user, project.id, session_id)
  session.status = "cancelled"; db.session.commit()
  cleanup_expired_sessions(dry_run=False)
  ```
  ```python
  sessions = UploadSelectionSession.query.filter(UploadSelectionSession.module_type == SCOPE[0], UploadSelectionSession.target_type == SCOPE[1], UploadSelectionSession.status != "finalized", or_(UploadSelectionSession.expires_at <= _now(), UploadSelectionSession.status == "cancelled")).all()
  ```
- **Full guard chain:** Global `require_login` → `require_reports_module_access` (`projects.`) → `_project_or_404()` checks only the URL project’s `deleted_at` → `can_create_report(current_user, project.id)` → `direct_uploads._session()` binds the supplied session to actor, module, target type, and that project. The subsequent cleanup has no actor/project/session scope.
- **Object-scope evidence:** The route correctly authorizes `session_id` against the caller and target project, but `cleanup_expired_sessions()` queries every daily-report/project session whose status is cancelled or expired. Its loop deletes each matched session’s storage objects and DB records.
- **Resulting write/read/delete:** The caller changes their session to `cancelled`, then triggers synchronous external-object deletion and DB deletion of upload batches/items/storage objects for unrelated projects and users.
- **Concrete impact:** A low-privilege reporter can make cancellation latency and destructive work proportional to all expired/cancelled sessions in the system. It can delete another project’s still-recoverable uploaded originals before an operator’s intended cleanup window, and can exhaust a web worker with unbounded S3 deletes.
- **Remediation direction:** Cancellation must only mark/cancel the authorized session. Move global expiry cleanup to an operator/background task; if eager cleanup is required, pass and enforce the one session ID and execute it asynchronously. Audit the cancellation and every cleanup result.

### REPORTS-002 — “Today” reveals reports in projects where the caller lacks report-view capability

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-200, CWE-863
- **Location:** `app/reports/routes.py:70-92`; `app/reports/services.py:227-232`
- **Reachability:** An authenticated user with `reports.today.view`, `can_view_project` for project A, and no `can_view_reports` for A can request `GET /reports/today`.
- **Exact code quote:**
  ```python
  ids = accessible_project_ids(current_user, ("can_view_project",))
  ```
  ```python
  reports = {item.project_id: item for item in DailyReport.query.filter(
      DailyReport.project_id.in_([project.id for project in projects] or [0]),
      DailyReport.report_date == report_date,
  ).all()}
  ```
  The ordinary report query instead scopes by:
  ```python
  ids = accessible_project_ids(current_user, ("can_view_reports",))
  ```
- **Full guard chain:** Global login → Reports module gate → global RBAC `reports.today.view` → project list scoped with `can_view_project`; there is no `can_view_report` check before daily-report rows are loaded and rendered.
- **Object-scope evidence:** The only project-ID set supplied to the daily-report query is derived from `can_view_project`, whereas `can_view_report()` requires `can_view_reports` for the report’s project.
- **Resulting write/read/delete:** Read-only disclosure of whether a report exists today, its report ID in the rendered row/link, and template-visible report metadata for an unauthorized report scope. The detail route subsequently denies access, but the disclosure has already occurred.
- **Concrete impact:** Custom members can enumerate current daily reporting activity on projects for which they were intentionally not granted report visibility.
- **Remediation direction:** Derive the Today project/report set from `can_view_reports`, or apply `can_view_report()` before constructing each rendered item. Keep the capability used here aligned with `reports_query()`.

### REPORTS-003 — Report listing does not exclude reports whose project is soft-deleted

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-200, CWE-863
- **Location:** `app/reports/services.py:227-232`; contrast `app/reports/routes.py:189-192`
- **Reachability:** A user with global project scope or an active report-view membership can request `GET /reports` after a project is soft-deleted while its `DailyReport` rows and memberships remain present.
- **Exact code quote:**
  ```python
  def reports_query():
      query = DailyReport.query.join(DailyReport.project)
      ids = accessible_project_ids(current_user, ("can_view_reports",))
      if ids is not None:
          query = query.filter(DailyReport.project_id.in_(ids or [0]))
      return query
  ```
  The detail route explicitly performs the missing state check:
  ```python
  project = Project.query.filter(Project.id == report.project_id, Project.deleted_at.is_(None)).first()
  if not project or not can_view_report(current_user, report):
      abort(403)
  ```
- **Full guard chain:** Global login → Reports module gate → `can_access_reports_module()` → `reports_query()` scopes only by capability IDs. No `Project.deleted_at` predicate is applied to the joined project. Detail/edit add a per-report capability check; only detail/read helper checks soft-delete.
- **Object-scope evidence:** `DailyReport.project_id` is correctly capability-scoped but is not state-scoped. A join alone does not filter deleted projects. The code’s explicit deleted-project denial for detail demonstrates that such rows are expected to be hidden.
- **Resulting write/read/delete:** `GET /reports` reads and renders report rows belonging to soft-deleted projects; the same query is reused by the per-project report view after its project lookup.
- **Concrete impact:** Historical reports from a project removed from the active application scope remain discoverable and may disclose report summaries/statuses to users who retain global scope or stale memberships.
- **Remediation direction:** Add `Project.deleted_at.is_(None)` to `reports_query()` (or join through an explicitly state-filtered project query) and use one shared state-aware report lookup for detail, edit, and delete.

### REPORTS-004 — Attachment deletion bypasses the explicit dangerous RBAC permission used by the UI

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-863
- **Location:** `app/attachments/routes.py:84-91`; `app/reports/routes.py:177-179`; `app/permissions/registry.py:47-48`
- **Reachability:** An authenticated Reports-module user who can edit a report (including an owner with only `can_edit_own_reports`) can POST `/attachments/<attachment_id>/delete` with CSRF, even when their RBAC role lacks `report_attachments.delete`.
- **Exact code quote:**
  ```python
  if not can_edit_report(current_user, report): abort(403)
  delete_attachment(attachment)
  ```
  The edit-page UI instead requires both controls:
  ```python
  can_delete_attachment=current_user.can("report_attachments.delete") and can_edit_report(current_user, report),
  ```
  The registry marks the missing server-side permission as dangerous:
  ```python
  _permission(f"report_attachments.{action}", f"{action.title()} Ảnh báo cáo", dangerous=action == "delete")
  ```
- **Full guard chain:** Global login → Reports module gate (`attachments.`) → attachment lookup filters active attachment → report is derived from the attachment’s section → `can_edit_report` only. No `current_user.can("report_attachments.delete")` check exists in the endpoint/service.
- **Object-scope evidence:** The attachment is correctly linked to a report and project before the capability check, so this is not a cross-project IDOR. It is an authorization-policy mismatch: an endpoint accepts the object ID and authorizes destruction under a weaker capability than the UI and RBAC catalogue advertise.
- **Resulting write/read/delete:** `delete_attachment()` deletes the attachment record and, if unshared, its derivatives, processing job, storage record, and external object bytes.
- **Concrete impact:** A reporter who is allowed to edit report text/sections but is not intended to hold the dangerous attachment-delete permission can directly invoke the hidden endpoint and irreversibly delete report evidence.
- **Remediation direction:** Make the endpoint enforce the same explicit RBAC permission as the UI (and retain `can_edit_report` for project scope), or remove the unused permission and document that report-edit capability deliberately includes destructive attachment deletion.

### REPORTS-005 — V2 create idempotency fails under concurrent retries of the same client request ID

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-362
- **Location:** `app/reports/services.py:161-164`, `176-179`, `208-214`; `app/models/daily_report.py:8-10`
- **Reachability:** A permitted report creator can submit two concurrent `finalize` requests with the same UUID `client_request_id` (for example, an automatic retry racing a slow first response). The V2 route is owned by Unit 3b, but the defect is in this primary service.
- **Exact code quote:**
  ```python
  existing_request = db.session.scalar(select(DailyReport).where(DailyReport.project_id == project.id,
      DailyReport.client_request_id == client_request_id))
  if existing_request:
      return existing_request
  ```
  ```python
  except IntegrityError as exc:
      db.session.rollback()
      if _is_daily_report_date_constraint(exc): raise DailyReportCreateV2Error("duplicate_report_date", _duplicate_report_error(report_date).args[0], status=409) from exc
      raise
  ```
  ```python
  db.UniqueConstraint("project_id", "client_request_id", name="uq_daily_reports_project_client_request"),
  ```
- **Full guard chain:** Global login; the V2 blueprint currently has no module gate; its `_project()` helper checks target-project soft-delete and `can_create_report`; payload validation UUID-checks `client_request_id`; the service checks for an existing request before entering its write transaction. No row/key lock serializes two absent-row checks.
- **Object-scope evidence:** Both requests are bound to the same authorized project/user/session. The DB correctly prevents two reports with the same `(project_id, client_request_id)`, but the service recognizes only the date constraint and does not reload/return the winning request after the client-request constraint fires.
- **Resulting write/read/delete:** One request creates the report; the racing request rolls back and returns an unhandled integrity error (500), rather than the original report. Its upload-session changes roll back with that transaction.
- **Concrete impact:** The advertised retry/idempotency contract is unreliable precisely during concurrent or duplicated requests; clients can receive a 500 after a report was successfully created and may incorrectly attempt a different creation flow.
- **Remediation direction:** On `uq_daily_reports_project_client_request`, roll back, reload the report by `(project_id, client_request_id)`, and return it. Keep the date-constraint path as a 409. Add a PostgreSQL concurrency test.

### REPORTS-006 — Archived projects remain mutable through reports-core routes

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-840
- **Location:** `app/projects/routes.py:292-296`, `app/reports/routes.py:150-156`, `app/auth/permissions.py:150-166`; `app/models/project.py:9-12`
- **Reachability:** A user retaining report capabilities for a project whose status is `archived` can use report edit/delete and legacy upload-session routes. The same shared `can_create_report` is used by the V2 flow, which Unit 3b must assess independently.
- **Exact code quote:**
  ```python
  def _project_or_404(project_id):
      return Project.query.filter(
          Project.id == project_id,
          Project.deleted_at.is_(None),
      ).first_or_404()
  ```
  ```python
  def can_delete_report(user, report):
      user = _user_or_current(user)
      return user_has_project_capability(user, report.project_id, "can_archive_reports")
  ```
  ```python
  "status IN ('active', 'paused', 'completed', 'archived')"
  ```
- **Full guard chain:** Global login → Reports module gate → report/project lookup checks `deleted_at` but not status → capability check. The capability primitive checks active user/membership flags, not `Project.status`.
- **Object-scope evidence:** URL `project_id` and `report_id` are resolved to their owning project and capability is evaluated against that project. However, no guard in the primary routes/services distinguishes `archived` from an active target.
- **Resulting write/read/delete:** Existing reports can be edited/hard-deleted and upload sessions can be created, presigned, completed, or cancelled for an archived project; report creation is also not blocked by the shared authorization primitive.
- **Concrete impact:** Archive is not an effective lifecycle boundary. Users with retained membership can alter records/evidence in projects that administrators have archived, undermining archival integrity.
- **Remediation direction:** Define allowed operations per project status. If archive means read-only, centralize an `active/mutable project` predicate and require it for report mutations and upload-session endpoints; retain a deliberate read-only exception where needed.

### REPORTS-007 — Upload-session cancellation and cross-session cleanup have no audit trail

- **Severity:** Low
- **Confidence:** High
- **CWE:** CWE-778
- **Location:** `app/projects/routes.py:185-190`; `app/reports/direct_uploads.py:294-311`
- **Reachability:** Same as REPORTS-001.
- **Exact code quote:**
  ```python
  session.status = "cancelled"; db.session.commit()
  cleanup_expired_sessions(dry_run=False)
  return jsonify(upload_session_id=session.id, status=session.status)
  ```
  ```python
  db.session.execute(delete(UploadBatchItem).where(...))
  db.session.execute(delete(UploadBatch).where(UploadBatch.selection_session_id == session.id)); db.session.execute(delete(StorageObject).where(StorageObject.id.in_(ids or [-1])))
  ...
  db.session.commit(); return result
  ```
- **Full guard chain:** Global login → Reports module gate → target-project soft-delete check → creation capability → actor/project/session ownership check. There is no `audit()`/`log_audit()` call after authorization or while deleting matched sessions.
- **Object-scope evidence:** The request has a concrete actor and one authorized session, while the invoked cleanup can affect every matched session. Neither the initiating cancellation nor affected session/object identifiers are written to `AuditLog`.
- **Resulting write/read/delete:** Session status, storage bytes, storage metadata, batches/items, derivative metadata, jobs, and download references can be removed without an audit-log event.
- **Concrete impact:** Incident responders cannot attribute destructive cleanup to the initiating user or determine which unrelated upload sessions were purged, compounding REPORTS-001.
- **Remediation direction:** Emit a cancellation audit event and an auditable per-session cleanup result (actor/system actor, target project/session, object counts, outcome). Prefer background cleanup with structured operational logs.

## Legacy upload-flow security contract

Unit 3b must compare every V2 route and service call against these guards in the legacy project-route flow:

- The legacy `projects.` endpoints inherit global login and the global Reports-module gate. The V2 `daily_report_create_v2.` endpoint prefix is not in that gate; it must retain an explicit module-access decision in addition to project capability.
- Resolve `project_id` through a query requiring `Project.deleted_at IS NULL`; then require `can_create_report(current_user, project.id)`. Neither primary flow checks `Project.status == "active"`, which is the archived-project gap in REPORTS-006.
- Bind every `session_id` to `created_by_id`, `module_type == "daily_reports"`, `target_type == "project"`, and the URL project ID. Session status/expiry must be checked before use.
- Bind every `item_id` to the session through `UploadBatch.selection_session_id`; do not authorize a storage/object ID supplied by the client directly.
- Validate declared file metadata (allowed daily-report image extension/MIME, per-file cap), per-session count/size caps, available storage capacity, and verify object HEAD size/type/checksum on completion.
- For finalization, lock the session and its items; require the submitted item-ID set to equal the full session item set, all items completed/not finalized/`upload_status == "uploaded"`, and each item’s client-section ID to match a validated section.
- Validate each category ID belongs to the target project and is not deleted; validate daily/section statuses against the actual enum values; enforce max three attachments per section and total report limits.
- Preserve uniqueness: `(project_id, report_date)` must return a stable duplicate response, and `(project_id, client_request_id)` must be idempotent even for concurrent retries (REPORTS-005).
- Commit report/session/attachment metadata before dispatching media work. Do not make a failed broker dispatch roll back a committed report; retain a reconcilable pending job.
- Cancellation must be scoped to the authorized session. It must not invoke global expiry cleanup synchronously; cleanup needs explicit ownership/scope, idempotent external deletion, bounded work, and audit coverage.
- All JSON state-changing endpoints require the global CSRF contract and rate limits at least equivalent to legacy create/presign/complete (30/60/120 per minute); state reads that mutate expiry deserve the same scrutiny.

## Explicitly checked and found clean

- `report_id` is loaded server-side; report detail and edit derive its project and check `can_view_report`/`can_edit_report`. Edit’s direct-upload manifest re-binds the session to both actor and report project.
- Legacy session/item ownership is strong: `_session()` checks actor, module, target type, and target project; complete re-checks item-to-session membership; manifest finalization locks the session/items and requires the complete item set.
- Category/project consistency is enforced in both legacy validation (`validate_categories`) and V2 payload validation; client-supplied category IDs cannot name another project.
- DB constraints match the accepted report/section/issue status sets, and report dates are parsed as ISO dates and rejected when in the future.
- Daily-report services contain no `PersistentIssue` creation, mutation, or linkage. The project routes create issues only through explicit issue endpoints/services.
- Report create, update, hard delete, attachment create, and attachment delete invoke `audit()`; REPORTS-007 is limited to the session/cleanup lifecycle.
- The hard-delete path treats missing external objects as idempotent and deletes external bytes before database metadata. It still has a reliability concern (external deletion cannot be rolled back if a later DB failure occurs), but no concrete attacker-controlled failure path was established here.
- `reports.index`, `reports.today`, project index, and project issue list use unbounded queries and render-time membership/customer lookups. This is ordinary performance debt in the reviewed scope, not reported as a material DoS finding absent a demonstrated scale/reachability amplifier.

## Needs verification

- Run a PostgreSQL concurrency test for the same `client_request_id` and separately for two request IDs on the same `(project_id, report_date)`; SQLite test behavior is not sufficient for lock/constraint timing.
- Confirm the product policy for `paused` and `completed` projects as well as `archived`. The code makes all non-deleted statuses mutable; REPORTS-006 assumes the conventional archival read-only meaning.
- Test an induced DB failure after `hard_delete_reports()` removes external objects to quantify recovery behavior. The source proves an external-first/DB-second non-atomic boundary, but not a user-triggerable path to force the second phase to fail.
- Unit 3b must independently audit `create_v2.py` and all direct-upload error handlers/JSON CSRF behavior; those files were read only to establish the legacy-flow comparison contract and service-call effects.
