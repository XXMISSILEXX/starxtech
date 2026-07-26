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
