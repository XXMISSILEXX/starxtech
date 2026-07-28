# Findings — Customers & Project Operations

## Summary

- Both live blueprints are registered as `customers` and `project_operations` in `app/__init__.py:106-107,125-126`. Their actual Flask endpoint names therefore begin `customers.` and `project_operations.`; both are covered by the app-level login guard and reports-module gate at `app/__init__.py:155-189`. Neither blueprint defines a second `before_request` hook.
- The customer module protects normal edit/archive/restore operations with both global RBAC and `can_manage_customer`, and project operations generally re-derive a child object's project before applying `can_read_project`.
- Two authenticated, custom-role privilege issues are confirmed: a project can be re-parented without management authority over its source customer, and an arbitrary active contractor can be attached by ID without contractor visibility authorization.
- The project-update create error path confirms the assignment/project mismatch before writing, but renders the foreign assignment's contractor name and role in its 400 response.
- No application code, templates, tests, migrations, configuration, databases, or remote systems were modified. Only this audit file was written.

Files read: 26 primary/supporting files (all 6 primary Python files and all 12 assigned templates, plus app factory, permissions, membership, model, audit, registry, and assigned audit context) | Files skipped and why: compiled `__pycache__` only; `claude-partial-audit-backup/` was excluded without reading.

## Findings

### CUSTOMER-001 — Project move lacks source-customer management authorization

- **Severity:** High
- **Confidence:** High
- **CWE:** CWE-862
- **Location:** `app/customers/routes.py:174-191`; `app/customers/services.py:16-45`
- **Reachability:** Authenticated caller reaching endpoint `customers.move_project` (`POST /customers/<customer_id>/projects/<project_id>/move`). The global hook requires reports-module access, and the route requires `customers.edit` plus `can_view_project` for the source project. A non-admin custom role can satisfy those without source-customer management authority.
- **Vulnerable code:**
  ```python
  # app/customers/routes.py:174-191
  @bp.post("/<int:customer_id>/projects/<int:project_id>/move")
  def move_project(customer_id, project_id):
      _permission_required("customers.edit")
      customer = _customer_or_404(customer_id)
      project = Project.query.filter(Project.id == project_id, Project.deleted_at.is_(None)).first_or_404()
      if project.customer_id != customer.id or not can_access_customer(current_user, customer):
          abort(403)
      project_ids = accessible_project_ids(current_user, ("can_view_project",))
      if project_ids is not None and project.id not in project_ids:
          abort(403)
      target_id = request.form.get("target_customer_id", type=int)
      target = Customer.query.filter_by(id=target_id, is_active=True).first_or_404()
      if not can_access_customer(current_user, target) or not can_manage_customer(current_user, target):
          abort(403)
      old_values = {"customer_id": project.customer_id}
      project.customer_id = target.id
  ```
  ```python
  # app/customers/services.py:38-45
  def can_manage_customer(user, customer):
      if is_project_admin(user) or user.can("projects.scope_all"):
          return True
      project_ids = [project.id for project in customer.projects if project.deleted_at is None]
      if not project_ids:
          return True
      visible_ids = accessible_project_ids(user, ("can_view_project",)) or []
      return set(project_ids).issubset(visible_ids)
  ```
- **Exploit:** A non-admin custom role with `customers.edit`, reports-module access, and `can_view_project` on project P can submit P under its real source customer. The source check is only `can_access_customer`, which follows project visibility. The caller can select an active customer with no projects: `accessible_customers_query` deliberately makes such customers accessible (`services.py:25-30`) and `can_manage_customer` returns `True` for them. The endpoint then changes `P.customer_id` without ever calling `can_manage_customer` for the source.
- **Impact:** Unauthorized cross-customer re-parenting changes customer/project ownership and customer-scoped reporting relationships. The audit row records the mutation but does not prevent it.
- **Fix:** Require `can_manage_customer(current_user, customer)` in the source condition, and define a write-capability policy for project moves rather than treating project read as sufficient. Not implemented.
- **Effort:** S

### CONTRACTOR-001 — Assignment endpoint accepts an inaccessible contractor ID

- **Severity:** High
- **Confidence:** High
- **CWE:** CWE-639
- **Location:** `app/project_operations/routes.py:253-281`; `app/project_operations/services.py:38-69,164-194`
- **Reachability:** Authenticated caller reaching endpoint `project_operations.project_contractors` (`POST /projects/<project_id>/contractors/<role_path>`). Minimum authority is reports-module access, global `contractor_assignments.view` and `contractor_assignments.manage`, and `can_view_project` for the target project. `role_path` is allow-listed, but the submitted contractor is not scope-checked.
- **Vulnerable code:**
  ```python
  # app/project_operations/routes.py:253-273
  @bp.route("/projects/<int:project_id>/contractors/<role_path>", methods=["GET", "POST"])
  def project_contractors(project_id, role_path):
      _permission_required("contractor_assignments.view")
      role = ROLE_PATHS.get(role_path)
      if role is None:
          abort(404)
      project = _project_or_404(project_id)
      if not can_read_project(project.id):
          abort(403)
      if request.method == "GET":
          return _render_project_role(project, role)
      _permission_required("contractor_assignments.manage")
      contractor = _contractor_or_404(request.form.get("contractor_id", type=int))
      try:
          status = request.form.get("status", ProjectContractorAssignmentStatus.ACTIVE.value)
          assign_contractor(project=project, contractor=contractor, role=role,
                            status=status, started_on=_date_from_form("started_on"),
                            note=request.form.get("note"), actor_id=current_user.id)
          db.session.commit()
  ```
  ```python
  # app/project_operations/services.py:46-69
  return query.filter(
      or_(
          ~ProjectContractor.assignments.any(),
          ProjectContractor.assignments.any(
              ProjectContractorAssignment.project_id.in_(project_ids or [0])
          ),
      )
  )

  def can_manage_contractor(user, contractor):
      ...
      assignment_project_ids = [assignment.project_id for assignment in contractor.assignments]
      ...
      return set(assignment_project_ids).issubset(visible_ids)
  ```
- **Exploit:** Submit the numeric ID of any active contractor not returned by the caller's scoped picker. `_contractor_or_404` only loads by ID; it never calls `can_access_contractor`. `assign_contractor` validates active status, enum state, project state, and duplicate assignments, but not caller visibility. Once the new assignment exists, `accessible_contractors_query` treats the contractor as visible through the caller's target project; if that is the contractor's only assignment, `can_manage_contractor` also becomes true for that caller.
- **Impact:** An attacker can attach an arbitrary contractor to a readable project, disclose its name/phone/email/address through the contractor list/detail routes, and potentially gain edit/archive authority over the contractor. This is a cross-project PII and authorization escalation.
- **Fix:** After loading the contractor, reject unless `can_access_contractor(current_user, contractor)` is true; use an explicit assignment-management project capability instead of `can_read_project` for the write. Not implemented.
- **Effort:** S

### PROJECT-OPS-001 — Invalid cross-project update submission discloses contractor identity

- **Severity:** Medium
- **Confidence:** High
- **CWE:** CWE-200
- **Location:** `app/project_operations/routes.py:402-417`; `app/project_operations/services.py:258-275`; `app/templates/project_operations/updates/form.html:12`
- **Reachability:** Authenticated caller reaching endpoint `project_operations.project_update_create` (`POST /projects/<project_id>/updates`) with `project_updates.create` and `can_view_project` for a project they may update. The submitted `contractor_assignment_id` may name an assignment from another project.
- **Vulnerable code:**
  ```python
  # app/project_operations/routes.py:402-417
  @bp.post("/projects/<int:project_id>/updates")
  def project_update_create(project_id):
      _permission_required("project_updates.create")
      project = _project_or_404(project_id)
      if not can_read_project(project.id):
          abort(403)
      assignment_id = request.form.get("contractor_assignment_id", type=int)
      assignment = _assignment_or_404(assignment_id) if assignment_id else None
      try:
          update = create_project_update(project=project, assignment=assignment, ...)
          db.session.commit()
      except (ValueError, TypeError) as error:
          db.session.rollback(); flash(str(error), "danger")
          return _update_form(project, assignment=assignment,
                              form_values=request.form.to_dict(), form_error=str(error)), 400
  ```
  ```python
  # app/project_operations/services.py:269-275
  if assignment is not None:
      if assignment.project_id != project.id:
          raise ValueError("Đối tác không thuộc dự án này.")
  ```
  ```jinja2
  {# app/templates/project_operations/updates/form.html:12 #}
  {% if locked_assignment %}... value="{{ locked_assignment.contractor.name }} · {{ locked_assignment.role|contractor_role_label }}" ...{% endif %}
  ```
- **Exploit:** Submit a valid assignment ID from an inaccessible project along with otherwise valid update fields. The service correctly rejects the cross-project association, but the exception path passes that foreign assignment as `locked_assignment`; the form response includes its contractor name and role.
- **Impact:** Assignment-ID probing leaks contractor identity and role across project scope. No `ProjectUpdate`, `DailyReport`, or `PersistentIssue` is created by this failed request.
- **Fix:** Reject assignment/project mismatch before passing the object to any rendering function, or render the error form with `assignment=None`. Not implemented.
- **Effort:** S

## Explicitly checked and found clean

- **Module gates and endpoint registration:** `app/__init__.py:106-107,125-126` registers both blueprints. `require_login` applies to all matched endpoints (`:155-167`), and the module gate checks both endpoint prefixes (`:169-189`). There is no blueprint-local hook to bypass or alter this behavior.
- **Customer normal operations:** `detail`, `edit`, `archive`, and `restore` require their named RBAC code and use `can_access_customer` plus `can_manage_customer` (`app/customers/routes.py:104-176`). Archive/restore update both lifecycle fields and write audits (`:143-148,164-169`); restore checks active-name collision (`:161`).
- **Customer IDs and lists:** the move route re-derives the source from `project.customer_id` and filters out soft-deleted projects (`app/customers/routes.py:177-183`); the target must be an active customer (`:184-186`). Customer list/detail scope project visibility (`app/customers/services.py:16-35`; `routes.py:35-43`). A customer whose only project is soft-deleted may be omitted for a non-admin because `Customer.projects.any()` is unfiltered, a correctness/visibility asymmetry rather than a disclosure.
- **Contractor catalog PII paths:** list, detail, edit, archive, and restore all call `can_access_contractor`; mutations also require `can_manage_contractor` (`app/project_operations/routes.py:160-256`). The visible detail assignments are filtered by `can_read_project` (`:170-177`). Create/update assign fields explicitly, audit snapshots include PII, and no template uses `|safe` for these fields.
- **Assignment lifecycle:** role paths are fixed by `ROLE_PATHS` (`routes.py:47-50,253-258`); status is enum-validated; inactive contractors and inactive/deleted projects are rejected; duplicate open assignments are application-checked and backed by the partial unique index `uq_project_contractor_assignments_open_role` (`services.py:164-194`; `app/models/project_contractor.py:215-236`). Update/end re-derive the project from the assignment (`routes.py:284-330`), date order is checked, ending is idempotent, optional `ended_on` is supported, and lifecycle events are audited (`services.py:197-227`).
- **ProjectUpdate operations:** project list/detail/update endpoints scope reads through `can_read_project`; edit is constrained to `edit_all` or the creator's `edit` grant (`routes.py:337-346,360-460`). Creation validates project state, update type, length, future dates, assignment membership/status, and contractor activity (`services.py:258-286`). Delete is intentionally authorized by the distinct global `project_updates.delete` permission plus target-project visibility (`routes.py:441-450`), not an author-only permission; the registry has no `delete_own` code.
- **Cross-object effects:** `app/project_operations/` contains only read-count uses of `DailyReport` (`routes.py:18,65,113`) and no `PersistentIssue` import/call; `create_project_update` only creates and audits `ProjectUpdate` (`services.py:278-286`). There is no automatic DailyReport/PersistentIssue creation or status mapping.
- **Transaction/audit coverage:** customer create/update/move and contractor/assignment/update mutations emit audit records before their route commit; exception paths for assignment and update creation call `db.session.rollback()` (`customers/routes.py:71-87,188-191`; `project_operations/routes.py:274-278,295-304,319-327,415-417`; `services.py:125-131,192-193,213,226,285,294,304`).

## Needs verification

- The source confirms all default `ADMIN` grants include the relevant global permissions while `VIEWER_ADMIN` has only view permissions (`app/permissions/registry.py:98-111`). Exploitability of CUSTOMER-001 and CONTRACTOR-001 for a non-admin depends on whether a live custom role is granted the stated write RBAC codes; inspecting the persistent role-permission data is out of scope under the no-database-read instruction.
- The assignment partial unique index prevents concurrent duplicate open rows, but a concurrent conflict is not caught as `IntegrityError` in `project_contractors`; confirm production behavior/UX only with an isolated non-persistent test environment if later authorized.

## Tool leads closed as false positive/info

- **ENDPOINTS lead — customer move:** confirmed as **CUSTOMER-001**, not a false positive. The source customer uses access-only authorization while every sibling customer mutation requires management authorization.
- **ENDPOINTS lead — contractor assignment:** confirmed as **CONTRACTOR-001**, not a false positive. The POST route loads a client-supplied contractor ID without `can_access_contractor`; the GET picker's scoped query does not protect direct POSTs.
- **ENDPOINTS lead — project update assignment substitution:** confirmed as **PROJECT-OPS-001** for the error-path identity disclosure. The service prevents the write, so it is not a cross-project update-write vulnerability.
- **Tool-lead coverage:** no Unit 8 scanner-specific lead is assigned in `.audit/TOOL-LEAD-MAP.md`; its listed static-analysis leads map to other units. No additional Unit 8 tool lead remained open.
