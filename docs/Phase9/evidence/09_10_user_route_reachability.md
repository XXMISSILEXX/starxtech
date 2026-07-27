# Step 9.10 — User route reachability

## Audit basis

`flask routes` was run against PostgreSQL at migration head `c4d2e980f617`.
The source scan covered `url_for(`, `href=`, `fetch(`, and `action=` under
`app/templates`, `app/static`, and `app`. Legacy `/reports/dashboard`,
`/api/reports/dashboard/status-chart`, and
`/api/reports/dashboard/report-count-chart` are absent from the route map and
are covered by 404 regression tests.

## Reports and Project Operations pages

| Class | Endpoint / method | UI entry point | Permission and scope | Breadcrumb / back link | Result |
| --- | --- | --- | --- | --- | --- |
| USER_PAGE | `reports.today` GET | Reports sidebar | `reports.today.view` | Reports navigation | KEEP |
| USER_PAGE | `projects.index` GET | Reports module selector | Reports module access | Reports navigation | KEEP |
| USER_PAGE | `project_operations.operations_index` GET | Reports sidebar | `project_operations.view`, effective project scope | Reports navigation | KEEP |
| USER_PAGE | `project_operations.contractors_index` GET | Project Operations / workspace | `project_contractors.view`, effective scope | Operations navigation | KEEP |
| USER_PAGE | `dashboard.system_dashboard` GET | **Dashboard quản trị** sidebar and Reports selector | `modules.reports.access`, `dashboards.system.view`, `projects.scope_all` | Reports navigation | KEEP |
| USER_PAGE | `reports.configuration_hub` GET | Reports sidebar | `reports.configuration.view` | Reports navigation | KEEP |
| CONTEXTUAL_PAGE | `project_operations.project_workspace` GET | Operations project list | project read scope | Operations → project | KEEP |
| CONTEXTUAL_PAGE | `projects.reports` / `projects.reports_create` GET | workspace and project pages | project report scope | project routes | KEEP |
| CONTEXTUAL_PAGE | `projects.dashboard` GET | workspace and System Dashboard project selector | `dashboards.project.view` + effective project scope | Dashboard sidebar active | KEEP |
| CONTEXTUAL_PAGE | `dashboard.customer_dashboard` GET | System Dashboard customer selector | `dashboards.customer.view` + global scope requirement | Dashboard sidebar active | KEEP |
| CONTEXTUAL_PAGE | `dashboard.contractor_dashboard` GET | System selector, contractor detail, project contractor list | `dashboards.contractor.view` + assignment-derived scope | Dashboard sidebar active | KEEP |
| CONTEXTUAL_PAGE | `project_operations.project_contractors` GET | workspace tabs | contractor assignment view + effective project scope | Operations → project → role | KEEP |
| CONTEXTUAL_PAGE | `project_operations.contractor_detail` / `contractor_create` / `contractor_edit` GET | catalog and row actions | contractor permission + scope | Catalog → contractor | KEEP |
| CONTEXTUAL_PAGE | `project_operations.project_updates` / `project_update_new` / `project_update_edit` GET | workspace/timeline actions | ProjectUpdate permission + effective project scope | Operations → project → Báo cáo xuyên suốt | KEEP |
| CONTEXTUAL_PAGE | `project_operations.assignment_updates` GET | assignment/project timeline | ProjectUpdate view + assignment project scope | assignment/project context | KEEP |
| CONTEXTUAL_PAGE | `reports.detail` / `reports.edit` GET | project report list | report permission + project scope | project report list | KEEP |

## API-only, mutation-only, and internal routes

| Class | Route family | Reason |
| --- | --- | --- |
| API_ONLY | `/api/reports/dashboard/system/overview`, `/customers/<id>/overview`, `/contractors/<id>/overview`, `/projects/<id>/section-status` | Chart fetches; no direct navigation required. |
| API_ONLY | Daily Report V2 upload-session APIs | Direct S3/HEIC flow remains API-only and unchanged. |
| MUTATION_ONLY | ProjectUpdate create/delete; contractor archive/restore; assignment create/update/end | CSRF-protected POST forms and modal actions only. |
| MUTATION_ONLY | Daily Report, issue, attachment, membership, and storage mutation routes | Existing contextual buttons/forms only. |
| INTERNAL | `/health`, `/healthz`, login/logout and signed-upload helpers | Runtime, authentication, or workflow infrastructure. |

## Findings

- Every Reports/Project Operations `USER_PAGE` has a sidebar/module entry.
- Every reviewed `CONTEXTUAL_PAGE` has an inbound link from its parent resource;
  dashboard routes are reachable without typing a URL.
- Dashboard selector options are rendered only for their matching dashboard
  permission; project scope is enforced again by the target route/API.
- Dashboard type cards resolve their first accessible Customer, Project, or
  Contractor server-side and link directly to the canonical resource URL; an
  unavailable resource renders as a disabled, non-enumerating card.
- The Project Dashboard selector performs canonical navigation to
  `/reports/projects/<id>/dashboard`, sorts active projects before paused or
  completed projects, and contains only the effective project scope.
- Assignment edit and removal remain POST-only modal actions; no new GET
  mutation route was introduced.
- No API-only or mutation-only route was promoted into the main navigation.
- The System overview API has additive `system_analytics` data only for the
  System scope. It covers customer share, contractor coverage, project status,
  and project activity; Customer API output does not expand its scope.
