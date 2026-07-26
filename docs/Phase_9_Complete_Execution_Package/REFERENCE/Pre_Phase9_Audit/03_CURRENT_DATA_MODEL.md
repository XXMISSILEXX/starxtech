# Current data model

**VERIFIED** model evidence: `app/models/project.py`, `daily_report.py`, `issue.py`, `rbac.py`, `storage.py`, `media_processing.py`, `audit_log.py`.

```mermaid
erDiagram
 USERS ||--o{ PROJECT_USERS : membership
 PROJECTS ||--o{ PROJECT_USERS : has
 PROJECTS ||--o{ REPORT_CATEGORIES : configures
 PROJECTS ||--o{ DAILY_REPORTS : owns
 DAILY_REPORTS ||--o{ DAILY_REPORT_SECTIONS : contains
 REPORT_CATEGORIES ||--o{ DAILY_REPORT_SECTIONS : selected_by
 DAILY_REPORT_SECTIONS ||--o{ REPORT_ATTACHMENTS : has
 STORAGE_OBJECTS ||--o{ REPORT_ATTACHMENTS : stores
 PROJECTS ||--o{ PERSISTENT_ISSUES : owns
 USERS ||--o{ AUDIT_LOGS : acts
 ROLES ||--o{ USERS : assigns
 ROLES ||--o{ ROLE_PERMISSIONS : grants
 PERMISSIONS ||--o{ ROLE_PERMISSIONS : defines
```

`Project` soft-deletes; `ProjectUser` is unique `(project_id,user_id)`, active/inactive, stores a display preset and canonical boolean capabilities. `ReportCategory` is soft-deletable and unique `(project_id,name)` at DB level. `DailyReport` uniquely reserves `(project_id,report_date)` and `(project_id,client_request_id)`; `DailyReportSection` uniquely binds one category per report. `PersistentIssue` only links project/owner/creator. `ReportAttachment` references private `StorageObject`; `AuditLog` stores JSON old/new snapshots.

Compatibility fields: `User.role` is legacy mirror while `role_id` is canonical; `ProjectUser.role_in_project` aliases `project_role_code`; nullable `DailyReport.client_request_id` is pre-V2 compatibility; nullable attachment storage FK is migration-transition compatibility. Category name/icon are read through the current category relationship—there is no snapshot field on section (**VERIFIED**).
