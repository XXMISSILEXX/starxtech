# Final Phase 9 permission matrix

- Dashboard pages require their individual `dashboards.*.view` permission; `projects.scope_all` expands only scope.
- ProjectUpdate mutations require matching `project_updates.*` permissions plus project scope.
- Contractor list/mutations require `contractor_assignments.*` plus project scope.
- UI visibility mirrors backend checks; direct URLs and POSTs remain enforced.
