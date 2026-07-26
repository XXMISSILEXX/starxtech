# Step 9.9 — Legacy Dashboard removal smoke

Date: 2026-07-27

## Expected result

The following retired endpoints have no alias, redirect, or 410 handler and
naturally return 404:

- `/reports/dashboard`
- `/api/reports/dashboard/status-chart`
- `/api/reports/dashboard/report-count-chart`

System, Customer, Project, and Contractor dashboard endpoints remain in the
`/reports/dashboard/...` namespace.  The Reports selector now lands on System
Dashboard only when authorized; otherwise it lands on `/reports/projects`.

## Verification record

The final verification command and results are recorded with the implementation
commit.  This evidence intentionally does not claim a browser smoke while the
local PostgreSQL service is unavailable.
