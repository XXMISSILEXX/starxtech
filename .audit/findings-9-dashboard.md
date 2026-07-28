# Findings — Unit 9 Dashboard

## Summary

- Read every primary dashboard file: `app/dashboard/__init__.py`, `routes.py`, and `services.py`; all four matching templates; and the three dashboard JavaScript files. Supporting route registration, global hooks, permissions, membership, project-operation, report, and issue code was read where it determines access.
- Both dashboard blueprints are registered at `app/__init__.py:119-120`. Every registered dashboard endpoint first passes the global login hook at `app/__init__.py:153-167` and then the reports-module hook at `app/__init__.py:169-189`; no local `before_request` exists in `app/dashboard/routes.py`.
- System and customer dashboards correctly require both their dashboard permission and `projects.scope_all`; their source query applies the effective project scope before aggregates. The project and contractor dashboards have distinct, confirmed data-authorization defects below.
- Files read: 22 primary/supporting files | Files skipped: none in the assigned primary scope. `claude-partial-audit-backup/` was neither read nor searched.

## HTML ↔ JSON matrix

| Dashboard | HTML route | JSON route | Auth/RBAC | Scope filter | Fields HTML | Fields JSON | Difference | Consequence |
|---|---|---|---|---|---|---|---|---|
| System | `GET /reports/dashboard/system` → `dashboard.system_dashboard` | `GET /api/reports/dashboard/system/overview` → `dashboard_api.system_dashboard_payload` | Both use `_require_dashboard_scope("dashboards.system.view")`: reports access, dashboard permission, and `projects.scope_all` (`app/dashboard/routes.py:23-33,81-84,124-130`). | Both derive `DashboardScope.system().projects_query()`, excluding soft-deleted projects and applying `accessible_project_ids` (`app/dashboard/services.py:91-103,210-221,297-299`). | Aggregate cards; up to five active projects (code/name/customer/submitted/issue count); up to five updates (title/type/project/customer/contractor); up to five reports (project code/highlight/date/status); missing project code/name list. | Chart aggregates plus all in-scope active-project codes/statuses, status and severity counts, per-project issue counts; system analytics includes customer names, contractor names and IDs, project codes/names and IDs, report/issue activity and 7/30/90-day totals (`services.py:303-358,659-719`). | JSON is intentionally chart-oriented but exposes internal `contractor_ids` and `project_ids` that the HTML does not render. | Defense-in-depth/data-minimization gap only: caller already has global scope; no scope expansion found. |
| Customer | `GET /reports/dashboard/customers/<customer_id>` → `dashboard.customer_dashboard` | `GET /api/reports/dashboard/customers/<customer_id>/overview` → `dashboard_api.customer_dashboard_payload` | Identical `_require_dashboard_scope("dashboards.customer.view")` (`routes.py:36-50,87-91,124-130`). | Identical system scope intersected with `Project.customer_id == customer_id` (`services.py:91-103,210-221,297-299`). Customer is loaded only after RBAC and must be active. | Same scoped cards/recent projects, updates, reports and missing-project list as system, without system-only analytics. | Chart-only aggregate values: date/timezone; section statuses/trend; per-active-project code/submission/status; issue breakdowns/per-project values; contractor role counts (`services.py:303-350`). | JSON omits HTML's report highlights and update text, but supplies chart fields/IDs not rendered in HTML. | No object/scope drift found; IDs are a low-value minimization difference for a `projects.scope_all` holder. |
| Project | `GET /reports/projects/<project_id>/dashboard` → `projects.dashboard` | `GET /api/reports/dashboard/projects/<project_id>/section-status` → `dashboard_api.project_section_status` | HTML requires reports access + `dashboards.project.view` + `can_read_project`; JSON performs the same checks (`app/projects/routes.py:60-75`; `app/dashboard/routes.py:66-78`). | Both query the requested non-deleted project ID. Neither requires `can_view_reports`, `project_updates.view`, or a per-project `can_view_issues` check for all returned material. | Project code/name/description/status; report history IDs/dates/status/highlight/reporter; recent update title/date/contractor/creator; issue total, and issue rows only when per-project issue viewing is allowed (`templates/dashboard/project.html:8-50,75-158`). | Selected date/timezone; report ID/date/submission; section totals/trend; contractor counts; all issue totals by status; latest project-update ID/date/title (`services.py:194-207`). | JSON has report/update IDs and issue breakdown not in the HTML; HTML also leaks report history and update metadata which dedicated routes protect more narrowly. | Confirmed authorization drift: see DASHBOARD-001 through DASHBOARD-003. |
| Contractor | `GET /reports/dashboard/contractors/<contractor_id>` → `dashboard.contractor_dashboard` | `GET /api/reports/dashboard/contractors/<contractor_id>/overview` → `dashboard_api.contractor_dashboard_payload_api` | Both require reports access + `dashboards.contractor.view`, then `_contractor_or_404`/`contractor_is_visible` (`routes.py:53-63,94-102,112-121`). | Both derive assignment-backed projects from `DashboardScope.contractor(...).projects_query()` and re-check `project_id` filter membership (`services.py:379-421`). | Contractor name/short name/status; project selector code/name; assignments with project/customer/role/status/dates; update title/content; latest report project/date/status; issue title/project/status/severity when `has_any_project_capability(can_view_issues)` is true (`templates/dashboard/contractor.html:7-48`). | Contractor ID/name/short name/status; requested filters; cards; customer-name aggregate; assignment role/status aggregates; latest update ID/title/date (`services.py:526-540`). | JSON omits assignment rows, report rows, issue rows, and update content, while adding contractor/update IDs. HTML alone exposes the issue titles. | No JSON scope expansion found. HTML issue disclosure is a confirmed cross-project authorization failure (DASHBOARD-004). |

### DASHBOARD-001 — Project dashboard exposes daily-report data to a project reader lacking report-view capability

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-862
- **Reachability:** Any authenticated reports-module user granted `dashboards.project.view` and `can_view_project` for a project, but not `can_view_reports`. The capability model expressly permits that custom combination: `can_view_project` and `can_view_reports` are separate flags (`app/project_memberships.py:8-15,78-89`).
- **Location:** `app/projects/routes.py:60-75`; `app/dashboard/routes.py:66-78`; `app/dashboard/services.py:110-125,194-207`; `app/templates/dashboard/project.html:95-114`.
- **Vulnerable code:**
  ```python
  if (
      not can_access_reports_module(current_user)
      or not current_user.can("dashboards.project.view")
      or not can_read_project(project.id)
  ):
      abort(403)
  ```
  ```python
  reports = DailyReport.query.filter(DailyReport.project_id == project.id).order_by(
      DailyReport.report_date.desc(),
      DailyReport.id.desc(),
  )
  ```
  The dedicated report route instead calls `_require_can_read(report)` (`app/reports/routes.py:106-115`), which resolves to `can_view_report` and therefore `can_view_reports` for the report's project (`app/auth/permissions.py:154-155`).
- **Impact:** The HTML page renders report dates, status, user-controlled highlights, and reporter names; the JSON route returns report ID, date, and submission state. This bypasses the report-specific capability used by the canonical report-detail route.
- **Why this is distinct:** This is report-data authorization, not the ProjectUpdate permission bypass in DASHBOARD-002 or issue authorization in DASHBOARD-003/004.

### DASHBOARD-002 — Project dashboard bypasses the separate ProjectUpdate view permission

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-862
- **Reachability:** Any authenticated user passing the project dashboard's `dashboards.project.view` + `can_read_project` gate but lacking global `project_updates.view`. The two permissions are independent registry entries (`app/permissions/registry.py:80-95`).
- **Location:** `app/dashboard/services.py:138-155`; `app/templates/dashboard/project.html:26-30`; contrast `app/project_operations/routes.py:360-370`.
- **Vulnerable code:**
  ```python
  recent_updates_query = ProjectUpdate.query.options(
      joinedload(ProjectUpdate.contractor_assignment).joinedload(ProjectContractorAssignment.contractor),
      joinedload(ProjectUpdate.created_by),
  ).filter(
      ProjectUpdate.project_id == project.id,
      ProjectUpdate.deleted_at.is_(None),
  )
  ```
  ```python
  @bp.get("/projects/<int:project_id>/updates")
  def project_updates(project_id):
      _permission_required("project_updates.view")
  ```
- **Impact:** The dashboard returns update title, date, associated contractor name/role, and creator name without the explicit `project_updates.view` check that protects the updates endpoint. It exposes cross-project-operation records through a dashboard permission intended to be separately assignable.

### DASHBOARD-003 — Project dashboard and section-status API disclose issue aggregates without project issue-view authorization

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-200
- **Reachability:** An authenticated user with project dashboard permission and `can_view_project` for the selected project, but no `can_view_issues` for that same project. This is a supported custom-membership state (`app/project_memberships.py:37-42,78-89`).
- **Location:** `app/dashboard/services.py:181-191,194-207`; `app/templates/dashboard/project.html:19-24`; `app/dashboard/routes.py:66-78`.
- **Vulnerable code:**
  ```python
  issue_counts = dict(db.session.query(PersistentIssue.status, func.count(PersistentIssue.id)).filter(
      PersistentIssue.project_id == project.id, PersistentIssue.deleted_at.is_(None)
  ).group_by(PersistentIssue.status).all())
  ```
  ```python
  "persistent_issues": {"total": sum(metrics["issue_counts"].values()), "by_status": metrics["issue_counts"]},
  ```
  By comparison, the HTML detail rows alone use the correct per-project predicate: `user_has_project_capability(current_user, project.id, "can_view_issues")` (`app/dashboard/services.py:128-136`).
- **Impact:** The HTML card reveals total issue volume and the JSON endpoint reveals the full status breakdown, despite the caller not being allowed to view issues. This is aggregate disclosure rather than title/content disclosure.

### DASHBOARD-004 — Contractor dashboard uses an any-project issue permission to disclose issues from other visible projects

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-639
- **Reachability:** An authenticated user with reports access, `dashboards.contractor.view`, `can_view_issues` on project A, and only `can_view_project` on contractor-linked project B. Both assignment-backed project visibility and the unrelated any-project issue test are reachable through the HTML contractor dashboard.
- **Location:** `app/dashboard/services.py:490-497`; `app/templates/dashboard/contractor.html:48`; `app/dashboard/services.py:379-421`.
- **Vulnerable code:**
  ```python
  can_view_issues = has_any_project_capability(current_user, ("can_view_issues",))
  issues = (
      PersistentIssue.query.options(joinedload(PersistentIssue.project))
      .filter(PersistentIssue.project_id.in_(project_ids.select()), PersistentIssue.deleted_at.is_(None))
      .order_by(PersistentIssue.opened_date.desc(), PersistentIssue.id.desc()).limit(RECENT_DASHBOARD_LIMIT).all()
      if can_view_issues else []
  )
  ```
  ```jinja
  <div class="fw-semibold">{{ issue.title }}</div>
  <div class="small text-muted">{{ issue.project.code }} · {{ issue.status|status_label }} · {{ issue.severity|status_label }}</div>
  ```
- **Impact:** The user can select a contractor connected to both projects and obtain up to five issue titles, project codes, statuses, and severities from B even though B grants no issue-view capability. The JSON sibling does not serialize `issues`, but it still executes the unnecessary issue query as part of the shared context.
- **Related work:** Independently confirms the pre-audit ENDPOINTS-g3/ENDPOINTS central lead; no external-unit finding ID exists to cross-reference.

## Explicitly checked and found clean

- Route registration and actual endpoint names: `flask --app run.py routes` lists exactly the seven `dashboard.`/`dashboard_api.` handlers in the matrix and `projects.dashboard`; no duplicate or fallback endpoint was found.
- System/customer direct-object access: `_require_dashboard_scope` executes before `Customer.query...first_or_404()`, and both require `projects.scope_all` (`app/dashboard/routes.py:36-50,87-91,124-130`). Changing customer ID cannot expand beyond the data query's customer + effective-project intersection.
- Contractor direct-object/filter access: `contractor_is_visible` requires a visible assignment for non-global callers (`services.py:389-395`); a `project_id` query parameter is re-checked against that contractor's visible project set (`services.py:410-415`); assignment-status values are allow-listed (`services.py:366-376,416-421`).
- Archived/deleted handling: System/customer/project-scoped queries exclude `Project.deleted_at` (`services.py:91-103`); project JSON uses `deleted_at=None` (`routes.py:70`); inactive customers are not loadable (`routes.py:41,90`). Contractor history intentionally includes inactive contractors, but the caller must still have an assignment-backed visible project; no scope bypass follows from this asymmetry.
- Time windows: system/customer routes do not read caller-supplied dates/days. They use Asia/Ho_Chi_Minh and fixed 7-day trends; system report activity exposes fixed constants `(7, 30, 90)` with default 30 (`services.py:54-55,166-180,210-217,659-704`). Project JSON accepts only a strict `YYYY-MM-DD` selected date and fixes its trend at 7 days (`routes.py:73-77`, `services.py:194-207`).
- Denominators remain scoped: expected/submitted report counts derive from active project IDs, whereas issue/contractor/recent records derive from all scoped non-deleted project IDs (`services.py:217-293`). No global/scoped denominator mix was found.
- Legacy paths remain absent: the live route list contains no `/reports/dashboard`, `/api/reports/dashboard/report-count-chart`, or `/api/reports/dashboard/status-chart`; global login behavior preserves a real 404 for an unknown route because `request.endpoint is None` returns from the login hook (`app/__init__.py:155-160`).
- No SQL injection/raw serialization: dashboard queries use SQLAlchemy expressions and JSON payloads are explicitly constructed; no raw model object, SQL/internal exception, user email, storage key, phone, address, or attachment data is serialized by these routes.

## Needs verification

- Production query plans and traffic volume are needed to quantify whether system dashboard's unbounded project/list loading and seven-branch `UNION ALL` (`app/dashboard/routes.py:139-154`; `app/dashboard/services.py:659-676`) constitutes a production reliability issue. The source proves the cost pattern, not its production impact.
- The audit did not alter fixtures or create a PoC. An isolated authorization test with a custom membership containing `can_view_project=True`, `can_view_reports=False`, `can_view_issues=False`, and a role holding only the applicable dashboard permission would confirm each project-dashboard distinction end-to-end.

## Tool leads closed as false positive/info

- `app/templates/dashboard/_type_navigation.html:7` is the semgrep `var-in-href` lead. It is not an open redirect or XSS sink: every enabled `item.href` is constructed by fixed `url_for(...)` calls in `dashboard_navigation_context` (`app/dashboard/routes.py:156-160`), never from request data. Closed as false positive.
- The source confirms no dashboard-owned SQL-injection lead. The only formatted strings in the analytics query are fixed constants from `PROJECT_ACTIVITY_PERIODS` (`app/dashboard/services.py:54,672-674`), while query values are SQLAlchemy expressions/literals.
