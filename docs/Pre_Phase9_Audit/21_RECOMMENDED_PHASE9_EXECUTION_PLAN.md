# TARGET: recommended execution plan

| Phase | Goal/source area | Migration/compatibility | Gate |
|---|---|---|---|
| 9.0 | preserve audit/contracts | none | decisions approved |
| 9.1 | Customer foundation | new table + nullable Project FK | model/RBAC/rollback tests |
| 9.2 | contractor foundation | new local tables | isolation/migration rehearsal |
| 9.3 | project/contractor UI | additive routes/templates | manual permissions/URLs |
| 9.4 | Today/nav/config hub | no report rewrite | mobile/direct URL tests |
| 9.5 | report additive evolution | nullable links only | V2/storage regression |
| 9.6 | project dashboard core | scoped queries/indexes | aggregation/query-count |
| 9.7 | customer/system dashboards | new DashboardScope service | isolation/performance |
| 9.8 | contractor dashboard | assignment-aware query | least privilege/manual |
| 9.9 | stabilization/release | no speculative schema | backup/restore/security |

Each phase must have objective, source diff review, migration upgrade/rollback plan, compatibility check, automated tests, explicit manual acceptance and Definition of Done. Do not begin the next gate while its migration or V2 regression is unresolved.
