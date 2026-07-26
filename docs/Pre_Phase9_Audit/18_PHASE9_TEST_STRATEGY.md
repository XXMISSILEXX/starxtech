# TARGET: test strategy

Model/migration tests: Customer, contractor, nullable-to-validated constraints, upgrade on populated DB. Service tests: DashboardScope, Today missing/submitted logic, health calculation, issue linking. Route/API tests: all new HTML/JSON errors and CSRF. RBAC: SUPER/ADMIN/VIEWER/PM/REPORTER × assigned/unassigned project, direct URL and UI visibility. Isolation: customer/contractor/project filters must never leak rows.

Regression gates: `test_daily_report_create_v2.py`, `test_report_create_entry.py`, `test_reports_attachments.py`, attachment signed/private access, derivative queue, idempotent finalize and duplicate race. Add JS tests/build plus `node --check`; manual Chrome and iPhone Safari must explicitly exercise HEIC preview/direct PUT/retry. Add query-count/performance tests for dashboard, migration rehearsal, backup/restore and security tests. Do not alter old expectations merely to make Phase 9 green.
