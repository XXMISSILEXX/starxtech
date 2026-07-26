# Phase 9 gap analysis

| Capability | Hiện có | Thiếu | Reuse | Cần mới | Risk |
|---|---|---|---|---|---|
| Customer/grouping | No | customer ownership | Project | Customer + FK | data classification |
| Contractors | Partner module only, independent | project contractor lifecycle | RBAC/audit | ProjectContractor | domain collision |
| Assignments/updates | No | role/update records | Project scope | assignment/update tables | ownership |
| Today | reports list | expected/submitted/missing | report dates | query/UI | status policy |
| Dashboards | report-centric | system/customer/contractor scope | scoped queries | DashboardScope/query core | aggregation correctness |
| Health | overall status | defined calculation | labels | policy/service | legacy INFO |
| Issues | project issue | section/category/contractor links | PersistentIssue | nullable FKs | automatic creation |
| Category templates | per-project categories | reusable template copy | ReportCategory | template tables/command | history |
| Navigation | Reports sidebar | four new entries | module switch | nav changes | bookmarks |
| RBAC/audit | flags/audit | contractor and dashboard rights | helpers | codes/tests | legacy grants |
| Migration | head consistent | additive rollout | Alembic | phased migrations | data loss |

Each target recommendation in 14–18 uses: current evidence above, stated gap, additive recommendation, migration/RBAC/test/compatibility impacts. Nothing in this table is claimed implemented.
