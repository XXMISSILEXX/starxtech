# Phase 9 RBAC and navigation matrix

Authorization is `modules.reports.access` (or the established administrator/project
capability access path), an action permission, and project scope where the resource
belongs to a project. Custom-role behaviour is permission-code based; no new feature
uses a custom role name.

| Area | Visible navigation permission | Direct route/action gate | Scope rule |
| --- | --- | --- | --- |
| Today | `reports.today.view` | same | accessible active Projects only |
| Project operations | `project_operations.view` | same | `ProjectUser.can_view_project` or approved global scope |
| Customer catalog | `customers.view` | create/edit/archive use matching `customers.*` | customer/project visibility and manager helper |
| Contractor catalog | `project_contractors.view` | matching `project_contractors.*` | visible assignment Projects; manager helper for mutation |
| Assignment | `contractor_assignments.view` | `manage` / `end` for mutation | target Project read scope |
| ProjectUpdate | `project_updates.view` | create/edit/edit_all/delete | target Project read scope; own vs all edit permission |
| Project dashboards | `dashboards.project.view` | same | Project read scope |
| Customer/System dashboard | matching dashboard permission plus `projects.scope_all` | same | aggregate effective scope only |
| Contractor dashboard | `dashboards.contractor.view` | same | assignment-backed visible Projects only |
| Configuration | `reports.configuration.view` | existing project/category/membership permissions | project category/membership helpers |
| Roles | `roles.view` | `roles.manage` for mutation | System Admin shell; intentionally not a Reports configuration link |

`SUPER_ADMIN`/`ADMIN` use the established administrator bypass; `VIEWER_ADMIN`
is restricted to read capabilities. A `projects.scope_all` custom role gains global
read scope, not write permissions. Hidden navigation is not authorization: routes
still return 403 when the permission/scope checks fail.
