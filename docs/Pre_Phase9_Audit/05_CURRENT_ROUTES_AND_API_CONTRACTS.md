# Current routes and API contracts

**VERIFIED.** Complete route output is [flask_routes.txt](evidence/flask_routes.txt). Relevant inventory follows; all routes also pass global login and Reports-module access in `app/__init__.py::register_auth_guard`.

| Endpoint/function | Method/URL | Gate/scope | Response | Mutation/risk |
|---|---|---|---|---|
| `dashboard.index` | GET `/reports/dashboard` | module + scoped queries | HTML | read |
| dashboard APIs | GET `/api/reports/dashboard/{status-chart,report-count-chart}` | module + scope | JSON | read |
| `projects.index/dashboard/reports` | GET `/projects...` | `can_read_project` or accessible list | HTML | read |
| `projects.reports_create` | GET `/projects/<id>/reports/create` | only `can_read_project` | HTML | **gap: page renders readonly for view-only** |
| legacy create POST | POST same URL | none beyond project exists | JSON 405 | compatibility contract |
| V2 `preflight/create_session/presign/complete/finalize` | POST `/api/projects/<id>/daily-reports/...` | `can_create_report`; session owner/project | JSON `{ok,data}`/`{ok:false,error}` | write, rate-limited |
| `reports.index/detail/edit/delete` | GET/POST `/reports...` | list scope; `can_view/edit/delete_report` | HTML/JSON | edit legacy; hard delete |
| attachments | GET/POST `/attachments...` | `can_view_report` / edit | redirect/JSON | private signed storage |
| issues/project issues | `/reports/issues...`, `/projects/<id>/issues...` | capability helpers | HTML | issue mutation |
| admin project/membership/category | `/admin/projects...` | registry permission plus category project helper | HTML | admin/config |

CSRF is installed globally (`app/__init__.py`); JSON client requests use its existing frontend contract. The old project-prefixed upload endpoints still exist alongside canonical V2 `/api/...` endpoints, a bookmark/API compatibility risk. Tests: `test_reports_route_namespace.py`, `test_report_create_entry.py`, `test_daily_report_create_v2.py`, `test_reports_attachments.py`.
