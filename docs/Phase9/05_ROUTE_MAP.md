# Route map

## Existing relevant routes

- Dashboard: `GET /reports/dashboard`, APIs `/api/reports/dashboard/status-chart` and `/report-count-chart`.
- Project: `GET /projects`, `/projects/<id>`, `/projects/<id>/dashboard`, `/projects/<id>/reports/create`.
- Daily Report V2: `POST /api/projects/<id>/daily-reports/{preflight,upload-sessions,presign,complete,finalize}`.
- Reports: `/reports...`; attachments `/attachments...`; issues `/reports/issues...` and `/projects/<id>/issues...`.
- Configuration: `/admin/projects...`, memberships and categories.

## Planned additive route family

`/reports/today`, `/project-operations`, Customer/project/role/update/contractor subroutes below `/project-operations`, dashboard scope routes below `/reports/dashboard`, and `/reports/config`.

All old routes remain operational or receive a tested redirect. Reports navigation target is: Hôm nay; Quản lý dự án & nhà thầu; Dashboard quản trị; Cấu hình. Visibility is permission-based and direct URLs remain backend-enforced.
# STEP 9.3 — Contractor routes

| Route | Purpose | Permission and scope |
| --- | --- | --- |
| `/project-operations/contractors` | Contractor catalog | `project_contractors.view` |
| `/project-operations/contractors/<id>` | Contractor detail | `project_contractors.view`; assigned-project data is scope-filtered |
| `/projects/<id>/contractors/construction` | Construction assignments | `contractor_assignments.view` + project read scope |
| `/projects/<id>/contractors/solution` | Solution assignments | `contractor_assignments.view` + project read scope |

The legacy project blueprint uses `/reports/projects`; the new `/projects/<id>/contractors/...` paths therefore do not collide and preserve the locked route contract. Mutations additionally require the matching `project_contractors.*` or `contractor_assignments.*` action permission.
