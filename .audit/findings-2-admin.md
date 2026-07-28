# Findings — Admin & RBAC UI

## Summary

- Reviewed all 8 Python files in `app/admin/`, `app/admin_storage/`, and `app/users/`, plus all 11 matching templates. Cross-referenced the global login/CSRF hooks, RBAC service, membership model, audit helper, storage metadata pipeline, and report-create paths needed to resolve calls.
- Every in-scope endpoint is globally login-gated; state-changing requests are covered by global CSRF protection. `admin`, `admin_storage`, and `users` intentionally have no blueprint-wide module gate, so their route-level RBAC checks are the primary control.
- The four pre-existing critical escalation findings were re-confirmed but are intentionally not reproduced here.
- Separate findings: a `users.manage` holder can disable non-last `SUPER_ADMIN` accounts; CSV export passes formula-prefixed database strings through unchanged; membership privilege changes are not forensically reconstructable from audit logs.

## Findings

### ADMIN-001 — `users.manage` holder can deactivate a SUPER_ADMIN account

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-269 — Improper Privilege Management
- **Location:** `app/admin/routes.py:73-83`, `app/admin/routes.py:663-674`
- **Reachability:** Any authenticated, active user with `users.manage` can POST `/admin/users/<super_admin_id>/deactivate`. `ADMIN` receives `users.manage` in the version-controlled default grant set (`app/permissions/registry.py:98-100`). Global login and CSRF apply, but neither adds a target-role hierarchy check.
- **Code quote:**
  ```python
  @bp.post("/users/<int:user_id>/deactivate")
  @permission_required("users.manage")
  def users_deactivate(user_id):
      user = db.get_or_404(User, user_id)
      ensure_not_last_active_super_admin(user, new_is_active=False)
      ...
      user.is_active = False
  ```
  ```python
  if user.has_role(UserRole.SUPER_ADMIN.value) and user.is_active and not will_remain and count_active_super_admins(user.id) == 0:
      abort(400)
  ```
- **Full guard/call-chain trace:** `require_login` in `app/__init__.py:155-167` establishes authentication, then `permission_required("users.manage")` calls `user_has_permission`. That service permits an active `ADMIN` through its role-permission rows. The handler loads the attacker-selected target by primary key. `ensure_not_last_active_super_admin` only rejects the change when the target is the *last* active super admin; it never compares actor and target roles. With two active super admins, excluding the selected target yields a count of one, so the guard returns and the route writes `is_active=False`, logs `user.deactivate`, and commits.
- **Actual resulting state:** The chosen SUPER_ADMIN account becomes inactive and is denied by the permission service and project-role predicates. The attacker can repeat this against every super-admin account except the final active one.
- **Impact:** A lower-tier administrative account can selectively lock out total administrators and disrupt recovery/oversight. This is distinct from the known password-reset takeover: it is an availability and administrative-control violation even if the password-reset route is fixed.
- **Remediation direction:** Define and enforce a target-role hierarchy in every user mutation route. At minimum, only SUPER_ADMIN should deactivate, activate, edit, reassign, or reset another SUPER_ADMIN; retain the last-active-super-admin invariant as a separate safeguard.

### ADMIN-002 — Storage CSV export does not neutralize spreadsheet formula cells

- **Severity:** Low
- **Confidence:** Medium
- **CWE:** CWE-1236 — Improper Neutralization of Formula Elements in a CSV File
- **Location:** `app/admin_storage/routes.py:39-43`; attacker-controlled filename preservation at `app/storage/validation.py:24-47` and `app/storage/services.py:65-70`
- **Reachability:** An authenticated user who can upload a permitted file can supply a formula-prefixed filename. `validate_file_metadata` strips surrounding whitespace and validates the extension/MIME, but preserves the remaining filename verbatim in `StorageObject.original_filename`. An authenticated user with `storage.dashboard.export` downloads `/admin/storage/export.csv`; that permission is checked before the export limiter.
- **Code quote:**
  ```python
  filename = (filename or "").strip()
  ...
  return {"filename": filename, ...}
  ```
  ```python
  storage_object = StorageObject(..., original_filename=meta["filename"], ...)
  ```
  ```python
  for row in data["top_objects"]:
      writer.writerow(["top_object", row.original_filename or "Không còn metadata", row.bytes, row.count, "", row.bytes])
  ```
- **Full guard/call-chain trace:** The global login hook runs first. `@permission_required("storage.dashboard.export")` checks the exporter role, and `@limiter.limit(...)` then limits successful export attempts. `export_csv()` calls `dashboard_context()`, whose `top_objects` query selects `StorageObject.original_filename`; no output transform occurs before `csv.writer.writerow`. `csv.writer` correctly quotes CSV delimiters but does not prefix-neutralize `=`, `+`, `-`, or `@`, so those values remain spreadsheet-formula candidates after CSV parsing.
- **Actual resulting state:** The generated CSV contains the stored string as the first character of the object-name cell. Opening such a cell in a formula-evaluating spreadsheet can execute the spreadsheet expression rather than display it as text. The strict allowed-extension rule narrows payload construction, so the exact behavior remains dependent on the spreadsheet product and formula syntax.
- **Impact:** A lower-privileged uploader can plant a value later opened by a storage-dashboard exporter, creating a client-side formula-injection boundary. Depending on the spreadsheet client and policy, this can support deceptive links, external data requests, or other formula capabilities.
- **Remediation direction:** Before every `writer.writerow`, prefix untrusted text cells beginning with `=`, `+`, `-`, or `@` with a single quote (and apply the same helper to usernames, full names, labels, and filenames). Preserve the original value only in internal data, not export cells.

### ADMIN-003 — Membership capability grants and edits are not reconstructable from audit logs

- **Severity:** Low
- **Confidence:** High
- **CWE:** CWE-778 — Insufficient Logging
- **Location:** `app/admin/routes.py:284-336`; `app/admin/routes.py:306-323`; audit record construction at `app/audit.py:9-21`
- **Reachability:** Any authenticated user permitted to use a membership mutation route (including a legitimate SUPER_ADMIN) produces these incomplete records. Global login and CSRF apply; this is an audit-integrity defect, not an unauthenticated write.
- **Code quote:**
  ```python
  _apply_membership_form(membership)
  membership.is_active = True
  audit("project_membership.assign", "ProjectUser", membership.id,
        new_values={"project_id": project.id, "user_id": user.id})
  ```
  ```python
  def memberships_update(project_id, membership_id):
      membership = ProjectUser.query.filter_by(...).first_or_404()
      _apply_membership_form(membership)
      audit("project_membership.update", "ProjectUser", membership.id)
  ```
  ```python
  for field in CAPABILITY_FIELDS:
      setattr(membership, field, field in enabled)
  ```
- **Full guard/call-chain trace:** The membership routes authenticate globally and enforce `project_assignments.manage`; the handler selects the membership using both membership and project IDs for update/deactivate. `_apply_membership_form` overwrites every capability in `CAPABILITY_FIELDS` and the project-role code. `log_audit()` faithfully stores the supplied `old_values` and `new_values` JSON, but the create path records only project/user identity, the update path supplies neither old nor new values, and deactivation records only `new_values={"is_active": False}`.
- **Actual resulting state:** The database has the effective 17 capability flags, but the audit trail cannot answer which flags were granted, revoked, or changed, nor reconstruct the previous role/capabilities for an update.
- **Impact:** Privileged project-access changes cannot be reliably investigated or rolled back from the audit trail. This materially weakens detection and incident response around the membership surface, including events related to the separately verified critical escalation path.
- **Remediation direction:** Snapshot `project_role_code`, `is_active`, and all `CAPABILITY_FIELDS` before mutation; log both old and new snapshots on create, update, reactivation, and deactivation. Keep passwords and other secrets out of the snapshots.

## Known critical findings intentionally not duplicated

The following four `ENDPOINTS.md` Group-1 critical findings are owned by `.audit/VERIFIED-CRITICAL.md` and are intentionally not duplicated in this Unit 2 report:

- `ENDPOINTS.md #1 [G1]` — ADMIN self-grants SUPER_ADMIN through `POST /admin/users/<user_id>/edit`.
- `ENDPOINTS.md #2 [G1]` — ADMIN resets a SUPER_ADMIN password through `POST /admin/users/<user_id>/reset-password`.
- `ENDPOINTS.md #3 [G1]` — `roles.manage` rewrites/self-grants permissions through `POST /admin/roles/<role_id>/permissions`.
- `ENDPOINTS.md #4 [G1]` — `project_assignments.manage` self-inserts into any project through `POST /admin/projects/<project_id>/memberships`.

## Explicitly checked and found clean

- Global authentication applies to all in-scope endpoints; no route bypasses the application `require_login` hook. Global `CSRFProtect` covers all in-scope POST routes, and the matching HTML forms include CSRF fields.
- No in-scope GET route writes application data. POST handlers use redirects after successful mutations.
- The `VIEWER_ADMIN` write boundary is server-enforced for user, role, project, membership, storage-export, and branding writes; disabled controls in templates are not relied upon as the authorization mechanism.
- Membership update/deactivation scope `membership_id` to the URL `project_id`; cross-project membership-ID substitution returns 404. The database also has `UniqueConstraint(project_id, user_id)`, preventing duplicate membership rows.
- Category routes check the project capability server-side and scope every category lookup to its parent project; category IDs cannot be substituted across projects.
- Built-in system-role names are protected from editing, custom role codes are database-unique, and no role-deletion endpoint exists. The exception for system-role permission mutation is one of the intentionally excluded known critical findings.
- The storage dashboard does not enumerate object storage, issue presigned URLs, expose storage credentials/endpoints, or accept object IDs. Its dashboard and CSV routes enforce separate RBAC permissions; CSV export is rate-limited.
- Password hashes and generated temporary passwords are not written to audit records. The plaintext reset-password flash is covered by the excluded known critical finding.
- No account deletion/archive handler exists in the three primary modules.

## Needs verification

- `Project.status == "archived"` is not a universal write lock: membership routes load projects with `db.get_or_404`, and the v2 report-create helper filters only `deleted_at`, not status. The intended archive lifecycle policy is not specified clearly enough to classify this as a security finding in Unit 2; confirm whether archived projects must reject membership and report mutations.
- The CSV-formula impact depends on the spreadsheet client. The raw formula-prefix preservation is confirmed, but a client-specific test with a permitted-extension filename should establish the highest-impact executable expression before raising severity.
- No dedicated last-project-owner/last-manager invariant exists. Removing the final `PROJECT_OWNER` leaves the project without a member bearing that preset, but global project administrators can restore membership and the model does not define `PROJECT_OWNER` as a required control-plane role. Confirm the product policy before treating this as a defect.
- Sensitive admin mutations other than CSV export generally have no route-specific rate limits. This was not reported separately because an authenticated holder already has the associated mutation authority and no distinct concrete abuse impact was established.
