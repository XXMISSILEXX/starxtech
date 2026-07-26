# Executive summary

**VERIFIED.** The present app is a Flask/Jinja system with a canonical Reports module, project capability flags, per-project `ReportCategory`, Daily Report V2 direct S3 upload/finalize, issues, and report-centric dashboards. The Partner module is separate (`Company`, `Partner`, `PartnerRelationship` and `/partners`, `/partner-companies` routes); it must not become the Phase 9 Customer/contractor domain.

Reusable: `Project`, `ProjectUser` capability enforcement, `ReportCategory`, `DailyReport`/`DailyReportSection`, private `ReportAttachment`/`StorageObject`, upload sessions, derivatives, `PersistentIssue`, `AuditLog`, and report dashboard query scope. Missing: Customer grouping, project contractor/assignment/update entities, Today semantics, missing-report population, dashboard scopes and contractor responsibility links.

Important corrections: no `ProjectReportItem` is justified—`ReportCategory` already is project configuration and sections reference it uniquely. The four requested Phase 9 items belong in Reports-module navigation, not global navigation: current module switch selects a module then `app/navigation.py::get_sidebar_items` renders module-local sidebar.

Top risks: (1) V2 upload invariants, (2) category rename changes historical display, (3) legacy roles/grants diverge from registry defaults, (4) DB stats are stale, (5) archived project reports exist, (6) no issue-to-section/contractor foreign keys, (7) dashboard only counts submitted reports, (8) project status is not a create gate, (9) hard-delete report storage cleanup, (10) unmade product/RBAC decisions.

Recommended order: 9.0 audit; 9.1 Customer; 9.2 contractor; 9.3 project UI; 9.4 Today/navigation; 9.5 additive report links; 9.6 project dashboard; 9.7 customer/system dashboard; 9.8 contractor dashboard; 9.9 stabilization. See [21](21_RECOMMENDED_PHASE9_EXECUTION_PLAN.md).
