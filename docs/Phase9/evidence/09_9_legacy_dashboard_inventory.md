# Step 9.9 — Legacy Dashboard inventory

Date: 2026-07-27

## Baseline source and route scan

The pre-removal route map and source scan found these live legacy surfaces:

- `dashboard.index` → `GET /reports/dashboard`
- `dashboard_api.status_chart` → `GET /api/reports/dashboard/status-chart`
- `dashboard_api.report_count_chart` → `GET /api/reports/dashboard/report-count-chart`
- `app/templates/dashboard/index.html`
- `initDashboardCharts()` in `app/static/js/app.js`
- report/issue filter and chart helpers in `app/dashboard/services.py`

No dedicated Step 9.7 or 9.8 evidence files were found.  Commits `31c785e`
and `bc8dfe6`, their source, and their tests were used as the implementation
baseline.

## Classification

| Classification | Items |
| --- | --- |
| DELETE | The three routes/endpoints above, report-centric template, app.js chart initializer, and report/issue filtering/chart service helpers used only by that page. |
| KEEP | Dashboard blueprints/package; System, Customer, Project, Contractor pages and APIs; scoped/project chart scripts; auth/scope helpers; Partner and storage dashboards. |
| HISTORICAL | Prompt, build-pack, pre-Phase9 audit, and earlier investigation references remain unchanged as evidence of their pre-9.9 state; they are not live links. |

## Final live scan

`app/` has no `dashboard.index`, `status_chart`, `report_count_chart`,
`data-dashboard-chart`, or `Vấn đề đang mở` reference.  The legacy strings
remain only in 404 regression tests and historical/prompt/audit material.
