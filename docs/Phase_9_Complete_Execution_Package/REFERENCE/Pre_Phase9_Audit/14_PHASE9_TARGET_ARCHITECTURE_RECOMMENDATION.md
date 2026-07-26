# TARGET: Phase 9 architecture recommendation

**TARGET, not current state.** Current evidence: project-scoped categories/reports/issues and separate Partner domain. Gap: Customer/contractor aggregation and responsibility.

```mermaid
erDiagram
 CUSTOMER ||--o{ PROJECT : groups
 PROJECT ||--o{ PROJECT_CONTRACTOR : uses
 PROJECT_CONTRACTOR ||--o{ PROJECT_CONTRACTOR_ASSIGNMENT : assigns
 PROJECT_CONTRACTOR ||--o{ PROJECT_CONTRACTOR_UPDATE : receives
 DAILY_REPORT_SECTION }o--o| PROJECT_CONTRACTOR : optional_context
 PERSISTENT_ISSUE }o--o| PROJECT_CONTRACTOR : responsible
 PERSISTENT_ISSUE }o--o| REPORT_CATEGORY : category
```

Recommend a new Customer domain; additive nullable `projects.customer_id`; new project-local contractor entities (not `Partner`); keep `ReportCategory`; extend section/issue only with nullable context links after policy decisions. Implement dashboard query services around an explicit `DashboardScope` value object (SYSTEM/CUSTOMER/PROJECT/CONTRACTOR), not an ORM table unless saved views are required. Route ownership remains Reports blueprint/sub-blueprints; use service boundaries for customer, contractors, today, dashboard aggregation.

Migration: nullable columns/new tables first; no destructive link. RBAC: explicit contractor/dashboard capabilities. Tests: scope isolation, old report rendering, V2 finalize. Compatibility: preserve all existing URLs and optional/null associations.
