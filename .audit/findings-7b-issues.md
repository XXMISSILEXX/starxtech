# Findings — Unit 7B: Persistent Issues

## Summary

- `issues` is a registered blueprint with prefix `/reports/issues`; the six direct routes are authenticated by the application-wide hook, then module-gated because the endpoint begins `issues.`. It has no blueprint-local `before_request` hook.
- Object-changing routes re-load the issue by its own ID and evaluate the relevant capability against the loaded row's `project_id`; client input cannot reassign an issue's project or assign an owner outside that project.
- The global issue list uses a different project capability to qualify entry (`can_view_issues`, on any project) than to select rows (`can_view_project`, on every visible project). This is a confirmed cross-project data disclosure.
- Deletion is a soft delete and is audited, but it requires exactly the same capability as edit and never evaluates the registered dangerous `issues.delete` permission.
- All five primary files were read in full. Direct route, authorization, membership, model, enum, date, audit, and project-issue dependencies were read as needed; no primary file was unread.

### Module-gate proof and hook order

`create_app()` registers blueprints before it installs the application guards:

```python
register_blueprints(app)
register_health_route(app)
register_trusted_host_guard(app)
register_auth_guard(app)
```

`app/__init__.py:69-75`

The registered issue blueprint and endpoint prefix are:

```python
bp = Blueprint("issues", __name__, url_prefix="/reports/issues")
...
app.register_blueprint(issues_bp)
```

`app/issues/__init__.py:3-5`; `app/__init__.py:96,129`

At request time, Flask runs the app-level hooks in registration order: trusted-host (when configured), `require_login`, then `require_reports_module_access`. The latter applies to all `issues.*` endpoint names:

```python
if current_user.is_authenticated:
    return None
...
report_endpoints = ("dashboard.", "dashboard_api.", "projects.", "reports.", "issues.", "attachments.", "customers.", "project_operations.")
...
if endpoint.startswith(report_endpoints) or is_report_admin:
    ...
    if not can_access_reports_module(current_user):
        abort(403, description=REPORTS_MODULE_DENY_MESSAGE)
```

`app/__init__.py:155-189`

`app/issues/routes.py` has no `before_request`; all its routes consequently depend on that global chain plus their inline per-project checks. `can_access_reports_module()` itself accepts an active user with the module permission, project-admin/viewer-admin status, or a membership carrying `can_view_reports` or `can_create_reports` (`app/auth/permissions.py:51-56`). Global CSRF protection is documented in `FOUNDATION-A1`; the forms also emit `csrf_token` (`app/templates/issues/form.html:8-10`, `app/templates/issues/index.html:44-50`).

### Complete issue route matrix

| Method | Route | RBAC / module gate | Project capability and object scope | Side effect |
|---|---|---|---|---|
| GET | `/reports/issues` | Login → reports-module gate; any-project `can_view_issues` | Rows are selected from projects returned by `accessible_projects_query()` (currently `can_view_project`), not per-row `can_view_issues` | Read only; **ISSUE-001** |
| GET, POST | `/reports/issues/new` | Same global gates; entry requires any-project `can_view_issues` | Candidate projects are prefiltered to `can_create_issues`; supplied `project_id` is looked up only in that set | POST creates and audits an issue |
| GET, POST | `/reports/issues/<issue_id>/edit` | Same global gates | Loads non-deleted issue; GET requires `can_view_issues` and POST `can_edit_issues` for that issue's actual `project_id` | POST updates and audits |
| POST | `/reports/issues/<issue_id>/close` | Same global gates | Loads non-deleted issue; `can_close_reopen_issues` for its actual project | Sets `CLOSED` and `closed_date`; audits |
| POST | `/reports/issues/<issue_id>/reopen` | Same global gates | Loads non-deleted issue; `can_close_reopen_issues` for its actual project | Sets `OPEN`, clears `closed_date`; audits |
| POST | `/reports/issues/<issue_id>/delete` | Same global gates; no `issues.delete` RBAC evaluation | Loads non-deleted issue; `can_edit_issues` for its actual project | Soft-deletes and audits; **ISSUE-002** |
| GET | `/reports/projects/<project_id>/issues` | Login → reports-module gate (`projects.`) | Non-deleted URL project, then both `can_view_project` and `can_view_issues` for that exact project | Read only |
| GET, POST | `/reports/projects/<project_id>/issues/create` | Same `projects.` global gate | Non-deleted URL project; entry needs view; POST needs `can_create_issues` for exact URL project | POST creates and audits an issue |

The project-specific routes are implemented in `app/projects/routes.py:195-239`; the direct issue routes are at `app/issues/routes.py:28-154`.

## Findings

### ISSUE-001 — Global issues list discloses projects for which the caller lacks issue-view authority

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-639 / CWE-862
- **Location:** `app/issues/routes.py:29-44`; `app/reports/services.py:219-224`; `app/admin/routes.py:326-336`
- **Reachability:** An authenticated, reports-module-authorized user with `can_view_issues` on project A and `can_view_project=True, can_view_issues=False` on project B can request `GET /reports/issues`. This membership state is reachable through the production membership-management route, not merely a hand-made database state.
- **Vulnerable code:**
  ```python
  if not has_any_project_capability(current_user, ("can_view_issues",)):
      abort(403)
  projects = accessible_projects_query().all()
  project_ids = [project.id for project in projects]
  ...
  PersistentIssue.query.filter(
      PersistentIssue.project_id.in_(project_ids),
      PersistentIssue.deleted_at.is_(None),
  )
  ```
  `app/issues/routes.py:29-44`

  ```python
  ids = accessible_project_ids(current_user, ("can_view_project",))
  if ids is not None:
      query = query.filter(Project.id.in_(ids or [0]))
  ```
  `app/reports/services.py:219-224`

  ```python
  enabled = {field for field in CAPABILITY_FIELDS if request.form.get(field) == "1"}
  ...
  for field in CAPABILITY_FIELDS:
      setattr(membership, field, field in enabled)
  ```
  `app/admin/routes.py:326-336`
- **Exploit:** An authorized administrator can configure the two independent capability combinations above. The user then loads the global list. The entry check succeeds because A has `can_view_issues`; the row query includes B because B has `can_view_project`. The response renders B's title, project code, severity, status, dates, and owner (`app/templates/issues/index.html:29-37`). The template does **not** render `issue.description`; the earlier ENDPOINTS lead's reference to description disclosure is not confirmed by this source review.
- **Impact:** Cross-project disclosure of persistent-issue metadata to a caller explicitly denied issue viewing for the affected project. This can expose operational risk and ownership information.
- **Remediation:** Derive the list's candidate projects with `accessible_project_ids(current_user, ("can_view_issues",))`, or apply `user_has_project_capability(..., "can_view_issues")` per project before querying. Keep the top-level gate only as an empty-list/403 decision, not as a substitute for row scope.
- **Evidence and duplication:** Independently confirmed from source. It is related to, but not the same root cause or route as, dashboard finding `DASHBOARD-004`; it is not duplicated under an existing ISSUE ID.

### ISSUE-002 — Soft deletion bypasses the dedicated dangerous `issues.delete` permission

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-863
- **Location:** `app/issues/routes.py:146-154`; `app/auth/permissions.py:189-190`; `app/issues/services.py:78-82`; `app/permissions/registry.py:40-46`
- **Reachability:** Any authenticated user who passes the reports-module gate and has `can_edit_issues` on an issue's project can POST to the delete endpoint. `PROJECT_EDITOR` and `PROJECT_ISSUE_COORDINATOR` both carry that capability (`app/project_memberships.py:39-41`).
- **Vulnerable code:**
  ```python
  @bp.post("/<int:issue_id>/delete")
  def delete(issue_id):
      issue = _issue_or_404(issue_id)
      if not can_delete_persistent_issue(issue):
          abort(403)
      project_id = issue.project_id
      delete_issue(issue)
  ```
  `app/issues/routes.py:146-152`

  ```python
  def can_delete_persistent_issue(issue, user=None):
      return user_has_project_capability(_user_or_current(user), issue.project_id, "can_edit_issues")
  ```
  `app/auth/permissions.py:189-190`

  ```python
  def delete_issue(issue):
      old_values = issue_snapshot(issue)
      issue.deleted_at = db.func.now()
      audit("issue.delete", "PersistentIssue", issue.id, old_values, {"deleted_at": True})
      db.session.commit()
  ```
  `app/issues/services.py:78-82`

  ```python
  *[_permission(f"{resource}.{action}", ..., dangerous=action == "delete")
    for resource in ("reports", "attachments", "issues", ...)
    for action in ("view", "create", "edit", "delete")],
  ```
  `app/permissions/registry.py:40-43`
- **Exploit:** A project issue editor with no global `issues.delete` grant submits the CSRF-protected delete form or an equivalent POST for an issue in that project. The handler checks only edit capability, then makes the issue disappear from all normal issue queries, each of which filters `deleted_at.is_(None)` (`app/issues/routes.py:186-190`; `app/issues/services.py:18-22`).
- **Impact:** The dedicated dangerous permission is inert for this destructive operation. The action is not a SQL hard delete, but it is a real business-record deletion with no restore route in this module and no distinct per-project delete capability in `CAPABILITY_FIELDS` (`app/project_memberships.py:8-15`). Audit logging preserves evidence but does not prevent unauthorized policy-level deletion.
- **Remediation:** Make the enforced policy explicit and consistent: require `current_user.can("issues.delete")` in addition to the project scope check, or introduce a separately administered `can_delete_issues` capability and remove/retire the unused global permission if per-project authority is the intended design.
- **Evidence and duplication:** Independently confirmed. This is the ENDPOINTS deletion lead requested for verification; no earlier module finding has an ISSUE ID for it.

### ISSUE-003 — List date filters accept malformed values and can cause a database error

- **Severity:** Low (reliability/data-validation debt, not SQL injection)
- **Confidence:** High for missing validation; Medium for the exact production exception response
- **CWE:** CWE-20
- **Location:** `app/issues/routes.py:193-208`; duplicate project-specific implementation at `app/projects/routes.py:299-315`
- **Reachability:** Any user who can view the relevant issue list can submit arbitrary `date_from` or `date_to` query parameters. Neither route is rate-limited.
- **Vulnerable code:**
  ```python
  date_from = request.args.get("date_from", "").strip()
  date_to = request.args.get("date_to", "").strip()
  ...
  if date_from:
      query = query.filter(PersistentIssue.opened_date >= date_from)
  if date_to:
      query = query.filter(PersistentIssue.opened_date <= date_to)
  ```
  `app/issues/routes.py:193-208`
- **Impact:** The code bypasses the available `parse_iso_date()` validation used for writes (`app/issues/services.py:137-141,188-197`) and binds an arbitrary string to a `Date` comparison. On the declared PostgreSQL deployment, a malformed date is expected to fail at type coercion rather than return a controlled 400; this is availability/error-handling debt, not injection because SQLAlchemy binds the value.
- **Remediation:** Parse both query parameters with `parse_iso_date`, return 400 on invalid values, and validate `date_from <= date_to`.

### ISSUE-004 — Issue title length is left to a database exception instead of validated before commit

- **Severity:** Low (reliability/data-integrity debt)
- **Confidence:** High
- **CWE:** CWE-20
- **Location:** `app/issues/services.py:99-122,168-204`; `app/models/issue.py:20-27`
- **Reachability:** Any actor permitted to create or edit an issue can submit a title longer than 255 characters in a normal form POST.
- **Vulnerable code:**
  ```python
  title = form.get("title", "").strip()
  ...
  if not title:
      raise IssueValidationError("Vui lòng nhập tiêu đề.", {"title": "Vui lòng nhập tiêu đề."})
  ...
  issue.title = title
  ```
  `app/issues/services.py:99-122`

  ```python
  if not title:
      errors["title"] = "Vui lòng nhập tiêu đề."
  ```
  `app/issues/services.py:168-181`

  ```python
  title = db.Column(db.String(255), nullable=False)
  ```
  `app/models/issue.py:20-27`
- **Impact:** The validation prevents an empty title but has no maximum. PostgreSQL enforces the column limit at flush/commit; the routes only catch `IssueValidationError` (`app/issues/routes.py:85-95,111-119`), so an overlong title is not converted to a form error and may leave the request in an error path. The global 10 MB request cap limits payload size, but not this correctness failure.
- **Remediation:** Reject titles exceeding 255 characters in `validate_issue_form`/`_assign_issue_fields`, return a field error, and ensure unexpected commit failures roll back the session before rendering or propagating.

## Needs verification

- **ISSUE-003 runtime confirmation:** Run an isolated existing test or a disposable PostgreSQL query against `GET /reports/issues?date_from=not-a-date` to record the actual status and session cleanup behavior. No test or database was run here because this batch is read-only and no database mutation is allowed.
- The direct issue-ID routes do not add `Project.deleted_at` or `Project.status == "active"` to `_issue_or_404()` (`app/issues/routes.py:186-190`). Source inspection found the production archive route only sets `project.status = "archived"` (`app/admin/routes.py:250-253`) and found no application route that soft-deletes a `Project`. Whether archived projects are intentionally still editable across the reports module is a product-policy decision; it is not reported as an authorization vulnerability without that policy evidence.

## Explicitly checked and found clean

- **Client identifiers and substitution:** `issue_id` is loaded server-side and every direct operation applies its capability to `issue.project_id` (`app/issues/routes.py:103-105,127-130,137-140,147-150`). The new-form `project_id` is resolved only within the already-authorized candidate list (`app/issues/routes.py:64-76,212-216`). Project-specific create ignores form project identity and passes the URL-loaded project to `create_issue` (`app/projects/routes.py:217-227`), which fixes `PersistentIssue.project_id = project.id` (`app/issues/services.py:39-45`).
- **Owner, status, severity, and dates on writes:** Owner IDs are checked for active membership in the selected issue project (`app/issues/services.py:144-165`); status/severity are enum allow-lists and due date cannot precede open date (`app/issues/services.py:99-114,168-204`). Future dates are accepted intentionally; no stated business rule prohibits them.
- **Mass assignment/XSS:** `_assign_issue_fields` enumerates assignable fields and never assigns `project_id` (`app/issues/services.py:99-122`). Both issue templates use ordinary Jinja interpolation, with no `|safe` or disabled autoescaping (`app/templates/issues/index.html:29-50`; `app/templates/issues/form.html:12-70`). Semgrep's `create_url` lead is a false positive: the only value passed is server-created `url_for("issues.new")` (`app/issues/routes.py:52-53`) and it is HTML-attribute escaped by Jinja.
- **Audit and deletion semantics:** Create/update/close/reopen/delete all call `audit()` before their single `db.session.commit()` (`app/issues/services.py:39-82`). Delete is soft, not hard; normal read queries exclude deleted records. No attachment/storage action is part of this module.
- **PersistentIssue independence:** Full-repository source search (excluding the prohibited backup path) found `PersistentIssue` creation only in `app/issues/services.py:create_issue`; `create_issue` is called only by the two explicit issue-create routes (`app/issues/routes.py:85-86`, `app/projects/routes.py:224-227`). `app/reports/` and `app/project_operations/` contain no creation, automatic linking, status mapping, or shadow `OpenIssue`/observation model. Daily-report and project-update handling therefore does not automatically create a PersistentIssue.
- **Dashboards:** The project dashboard uses a per-project issue predicate before showing issue rows (`app/dashboard/services.py:128-136`; `app/templates/dashboard/project.html:71-158`). Existing findings `DASHBOARD-001` through `DASHBOARD-004` already cover independent dashboard aggregate/title exposure defects; they are cross-referenced, not duplicated here.
- **Performance:** Both global and project issue lists are unpaginated and perform three membership capability lookups per rendered issue (`app/issues/routes.py:42-56`; `app/projects/routes.py:200-212`). This is confirmed performance debt, but no materially exploitable amplification beyond an actor with authority to create/retain a large issue population was established in this unit; it is not counted as a vulnerability.

## Coverage accounting

| Category | Count |
|---|---:|
| Critical | 0 |
| High | 0 |
| Medium | 2 |
| Low | 2 |
| Info | 0 |
| Needs verification | 2 |
| Primary files unread | 0 |

Files read in full: 5 primary (`app/issues/__init__.py`, `routes.py`, `services.py`, `app/templates/issues/index.html`, `form.html`) and 13 direct dependencies/cross-checks. No files under `claude-partial-audit-backup/` were read, searched, or modified. Only this assigned output file was written.
