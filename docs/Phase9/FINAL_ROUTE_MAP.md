# Final Phase 9 route map

Canonical dashboards are System, Customer, Project, and Contractor. System
Dashboard is the navigation hub; overview APIs remain API-only. ProjectUpdate
and contractor-assignment pages are contextual under the Project Workspace.
The retired report-centric dashboard URLs intentionally return 404.

Project Dashboard keeps `/reports/projects/<id>/dashboard` as its canonical
URL; its scoped selector/search changes resources by navigating to that URL.
Assignment lifecycle mutations remain POST-only under
`/project-operations/assignments/<id>/update` and `/end`.
