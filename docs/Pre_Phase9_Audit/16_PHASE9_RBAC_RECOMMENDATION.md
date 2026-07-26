# TARGET: RBAC recommendation

Current evidence: registry permissions and project capability flags are distinct; DB includes legacy grants. Gap: no customer/contractor/dashboard scope rights.

Recommend registry codes: `customers.view/manage`, `project_contractors.view/manage`, `project_contractor_assignments.manage`, `project_contractor_updates.create/edit/delete`, `dashboards.system.view`, `dashboards.customer.view`, `dashboards.contractor.view`, and narrowly-scoped issue assignment. Reuse `projects.view/manage`, Reports module access, report/issue/category capability helpers. Default: SUPER_ADMIN bypass; ADMIN global manage; VIEWER_ADMIN global read dashboards/data; PM via project flags only; Reporter create/edit-own as existing unless owner chooses otherwise. Contractor update delete and mass membership/contractor changes are dangerous and audited.

Migration impact: insert registry metadata explicitly, do not reset DB defaults. Test impact: a role × project scope matrix, direct URL tests and nav visibility. Compatibility impact: legacy roles retain current grants until deliberate reconciliation.
