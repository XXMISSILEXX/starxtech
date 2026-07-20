# RBAC final review

Reviewed: 2026-07-20. SUPER_ADMIN bypasses registered permissions, while the
application still prevents removal, reassignment, or deactivation of the final
active SUPER_ADMIN.

## Route coverage

| Area | Endpoint/path | Methods | Module/resource permission | Scope/helper | UI guard | Risk/notes |
| --- | --- | --- | --- | --- | --- | --- |
| Module selection | `/modules/`, `/modules/select/<module>` | GET | `modules.reports.access` or `modules.partners.access` | `can_access_*_module` | module switch link | Selection denied without selected module grant. |
| Reports | dashboard, projects, reports, issues, attachments | all | `modules.reports.access` first | global `require_reports_module_access` | report-module nav | Includes report project/category administration. |
| Reports | report/project/issue read routes | GET | `reports.view`, `projects.view`, `issues.view` | `can_view_report`, `can_read_project`, `can_view_issue` | scope maps passed by routes | PM/REPORTER assignment scope is enforced. |
| Reports | report and issue create/edit routes | GET, POST | dedicated create/edit permission | `can_create_report`, `can_edit_report`, issue helpers | create/write maps | REPORTER edits only self-created reports; PM needs assignment. |
| Reports | report/issue delete routes | POST | dedicated delete permission | delete helpers | delete maps | PM/REPORTER receive no default delete grant. |
| Reports | `/attachments/<id>` | GET | `report_attachments.view` | `can_view_report` | protected attachment links | Files are not public/static. |
| Reports | `/attachments/<id>/delete` | POST | `report_attachments.delete` | `can_edit_report` | `can_delete_attachment` | Preserves Reporter ownership and PM assignment scope. |
| Report admin | `/admin/projects…`, categories | GET, POST | reports module plus project/category grant | category/project helpers | permission and scope flags | Global module guard runs before the route. |
| Partners | partners, companies, fields, collections, relations blueprints | all | `modules.partners.access` first | blueprint `before_request` | partner nav | PM/REPORTER have no default Partner module grant. |
| Partners | partner/company reads and mutations | GET, POST | dedicated `partners.*`/`partner_companies.*` | route resource lookup | `can_create/edit/delete` | Direct URLs and POSTs are checked server-side. |
| Partners | field/collection mutations | GET, POST | `partner_fields.manage`/`partner_field_collections.manage` | route resource lookup | `can_manage` | Manage grant required for every direct URL. |
| Partners | relation mutations | GET, POST | `partner_relations.manage`/`.delete` | route resource lookup | `can_manage` | Department-head field is visible only with `.manage`; changed submitted values are rejected otherwise. |
| User admin | `/admin/users`, new/edit forms | GET | `users.view` | `permission_required` | `current_user.can('users.view')` | VIEWER_ADMIN is read-only. |
| User admin | create/edit/activate/deactivate/reset | POST | `users.manage` | last-active-SUPER_ADMIN guard on role/status changes | `current_user.can('users.manage')` | ADMIN can manage users by default. |
| Roles | `/admin/roles…` | GET, POST | `roles.view`/`roles.manage` | SUPER_ADMIN role immutable | `current_user.can` | ADMIN lacks `roles.manage` by default. |

There is no registered report export, report attachment download, or Partner
export endpoint. `report_attachments.download` is registry metadata only: it
has no current endpoint and receives no default grant.

## Default grants

| Role | User administration | Reports | Partners | Roles |
| --- | --- | --- | --- | --- |
| SUPER_ADMIN | bypass | bypass | bypass | bypass |
| ADMIN | `users.view`, `users.manage` | registered report grants | module plus registered Partner grants | `roles.view` only |
| VIEWER_ADMIN | `users.view` | report module plus view grants | Partner module plus view grants | none |
| PROJECT_MANAGER | none | assigned-project report create/edit/view and configured issue actions | none | none |
| REPORTER | none | assigned-project report create/edit/view; self-created report edit only | none | none |

VIEWER_ADMIN receives no mutation permission. PM/REPORTER receive no default
report or issue delete permission; attachment deletion remains scoped by the
report edit policy.

## Remaining role checks and residual risks

Role-code checks remain only for labels, legacy compatibility, project scope,
Reporter ownership policy, and the active-SUPER_ADMIN invariant. They do not
authorize User Administration or Partner/Reports actions.

Custom role-permission edits can intentionally expand access and are protected
by `roles.manage`. Registry updates require `flask sync-permissions` against
the configured database.

## Audit commands and result

Run against the configured local database only; do not reset or migrate it.

```bash
python -m compileall app tests
pytest -q
flask sync-permissions
flask security-audit
```

Result: `python -m compileall app tests` and `pytest -q` passed in `.venv`
(51 tests). `flask sync-permissions` reached the configured PostgreSQL only
when run with the environment's database access, then stopped safely because
the target database has no `roles` table. Consequently `flask security-audit`
was not run: this review does not create/reset/migrate a database. Apply the
existing migrations to the intended local database, then rerun both commands.
