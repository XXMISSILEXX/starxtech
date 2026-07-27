# Route map

## Existing relevant routes

- Dashboard: `GET /reports/dashboard/system`, `/customers/<id>`, `/contractors/<id>` and their scoped overview APIs below `/api/reports/dashboard`.
- Project: `GET /projects`, `/projects/<id>`, `/projects/<id>/dashboard`, `/projects/<id>/reports/create`.
- Daily Report V2: `POST /api/projects/<id>/daily-reports/{preflight,upload-sessions,presign,complete,finalize}`.
- Reports: `/reports...`; attachments `/attachments...`; issues `/reports/issues...` and `/projects/<id>/issues...`.
- Configuration: `/admin/projects...`, memberships and categories.

Project-domain configuration has a permanent Reports presentation context:
`/admin/projects...`, `/customers...`, and `/project-operations/contractors...`
render the **Quản lý dự án** shell and make **Cấu hình** active.  Their original
URLs remain canonical. `/admin/roles...` is deliberately excluded and remains
in the System Admin shell.

## Planned additive route family

`/reports/today`, `/project-operations`, Customer/project/role/update/contractor subroutes below `/project-operations`, dashboard scope routes below `/reports/dashboard`, and `/reports/config`.

The retired report-centric Dashboard page and its two chart APIs intentionally return 404. Reports navigation target is: Hôm nay; Quản lý dự án & nhà thầu; Dashboard quản trị; Cấu hình. Visibility is permission-based and direct URLs remain backend-enforced.
# STEP 9.3 — Contractor routes

| Route | Purpose | Permission and scope |
| --- | --- | --- |
| `/project-operations/contractors` | Contractor catalog | `project_contractors.view` |
| `/project-operations/contractors/<id>` | Contractor detail | `project_contractors.view`; assigned-project data is scope-filtered |
| `/projects/<id>/contractors/construction` | Construction assignments | `contractor_assignments.view` + project read scope |
| `/projects/<id>/contractors/solution` | Solution assignments | `contractor_assignments.view` + project read scope |

The legacy project blueprint uses `/reports/projects`; the new `/projects/<id>/contractors/...` paths therefore do not collide and preserve the locked route contract. Mutations additionally require the matching `project_contractors.*` or `contractor_assignments.*` action permission.
