# Step 9.9 — Contractor Dashboard smoke

Date: 2026-07-27

## Implemented routes

- `GET /reports/dashboard/contractors/<contractor_id>`
- `GET /api/reports/dashboard/contractors/<contractor_id>/overview`

Both require `modules.reports.access` and `dashboards.contractor.view`.
For non-global project scope, the contractor is resolved only through a visible
assignment.  An inaccessible or forged contractor/project therefore returns
404 after permission validation.

## Verified locally

```text
pytest -q tests/test_dashboard_issues.py -k contractor
2 passed, 12 deselected

python -m compileall -q app
node --check app/static/js/contractor-dashboard-charts.js
```

The automated smoke creates one active and one ended assignment across two
customers, verifies the default history excludes `ENDED`, `ALL` restores it,
checks that only assignment-bound `ProjectUpdate` rows appear, and verifies a
partial-scope reporter receives 404 for another contractor and forged project.

No migration was created; the expected migration head remains `c4d2e980f617`.
