# Current routes and permissions

Global `before_request` trong `app/__init__.py` redirect anonymous về login (trừ login/health/static). Flask-WTF CSRF được init global. Bảng dưới ghi enforcement backend hiện tại, không suy diễn từ UI.

## Báo cáo hằng ngày và dự án

| Path / method | File | Hiện tại | RBAC đề xuất | Risk |
|---|---|---|---|---|
| `/dashboard`, `/api/dashboard/*` GET | `dashboard/routes.py` | login global; service tự scope project cho Reporter/PM | `reports.dashboard.view` + project scope | Medium |
| `/projects/` GET | `projects/routes.py` | query accessible projects | `projects.view` | Low |
| `/projects/<id>/dashboard`, `/reports`, `/issues` GET | `projects/routes.py` | `can_read_project` | `reports.view`/`issues.view` + project | Low |
| `/projects/<id>/reports/create` GET/POST | `projects/routes.py` | read GET, `can_write_project` POST | `reports.create` + project | Medium |
| `/reports/` GET, `/<id>` GET | `reports/routes.py` | accessible query / `can_read_project` | `reports.view` + project | Low |
| `/reports/<id>/edit` GET/POST | `reports/routes.py` | read GET, project write POST | `reports.edit` + project/own policy | Medium |
| `/reports/<id>/delete` POST | `reports/routes.py` | `can_manage_project` (ADMIN or assigned PM) | `reports.delete` + project | Medium |
| `/issues/`, `/issues/new`, `/<id>/edit|close|reopen|delete` | `issues/routes.py` | create PM/admin only; edit project-write; delete manage-project | split `issues.view/create/edit/close/delete` + project | Medium |
| `/admin/projects/<id>/categories*` | `admin/routes.py` | view super/viewer or project manager; mutate project manage | `report_categories.view/manage` + project | Medium |
| `/attachments/<id>` GET; `/<id>/delete` POST | `attachments/routes.py` | project read/write; path containment | `report_attachments.view/delete` + report/project | Low |

## Partner management

All blueprints use `can_access_partners_module()` in `before_request`: currently every listed authenticated role has read access. `PARTNER_WRITE_ROLES` is SUPER_ADMIN/ADMIN/PROJECT_MANAGER; delete partner itself only ADMIN/SUPER_ADMIN.

| Paths / methods | File | Hiện tại | RBAC đề xuất | Risk |
|---|---|---|---|---|
| `/partners/dashboard`, `/partners/`, `/<id>` GET | `partners/routes.py` | module read; detail repeats view | `partners.view` | Medium |
| `/partners/new`, `/<id>/edit` GET/POST | same | create/edit for PM+admins | `partners.create/edit` | High (PM broad write) |
| `/partners/<id>/deactivate` POST | same | admin roles | `partners.delete` dangerous | Medium |
| `/partner-companies/`, `/<id>`, departments GET | `partner_companies/routes.py` | module read | `companies.view` | Medium |
| company/department create/edit/delete/deactivate | same | PM+admins edit; company deactivate also PM | split `companies.manage`, `departments.manage`, delete dangerous | High |
| `/partner-fields/*` | `partner_fields/routes.py` | ADMIN/SUPER_ADMIN only | `partner_fields.manage` | Low |
| `/partner-field-collections/*` | `partner_field_collections/routes.py` | ADMIN/SUPER_ADMIN before-request | `partner_fields.manage` | Low |
| `/partner-relations/*` GET | `partner_relations/routes.py` | module read | `partner_relationships.view` | Medium |
| relation manage/edit/delete POST | same | PM+admins edit | `partner_relationships.manage/delete` | High |

## Admin/system/auth

| Paths / methods | Hiện tại | RBAC đề xuất | Risk |
|---|---|---|---|
| `/admin/users`, projects GET; user/project forms GET | `admin_read_required`: SUPER/ADMIN/VIEWER | `users.view`, `projects.manage` separately | Medium |
| user/project create/edit POST, reporter assignment POST | route performs additional SUPER/ADMIN check (despite UI saying SUPER only) | `users.manage`, `projects.manage`, `project_assignments.manage` | High |
| activate/deactivate/reset password/archive POST | `super_admin_required()` actually permits SUPER_ADMIN **and ADMIN** | distinct dangerous permissions; protect final super-admin | High |
| `/modules/select/*` GET | module helper and session write | `module.access` / respective `.view` | Low |
| `/login`, `/logout`, `/change-password` | auth forms / login required | unchanged auth policy | Low |

## Known UI and hard-code locations

- Core hard-code: `app/auth/permissions.py`; further checks in `app/admin/routes.py`, `reports/services.py`, `dashboard/services.py`, `issues/services.py`.
- UI hard-code: `base.html`, dashboard, admin users/projects/categories/reporters templates.
- `partner_companies/departments.html` exposes add/edit/delete controls without `can_edit`; backend still blocks, so UX mismatch rather than bypass.
- There is no export route in scanned routes. Future export/download must be a permission, not inferred from view.
