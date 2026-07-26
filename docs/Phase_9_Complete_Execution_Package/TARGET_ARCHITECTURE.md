# Kiến trúc đích Phase 9

## Component map

```mermaid
flowchart TD
  Nav[Reports module navigation] --> Today[Hôm nay]
  Nav --> Ops[Quản lý dự án & nhà thầu]
  Nav --> Dash[Dashboard quản trị]
  Nav --> Config[Cấu hình]

  Ops --> Customer
  Customer --> Project
  Project --> Daily[Daily Reports hiện tại]
  Project --> Updates[Báo cáo xuyên suốt / ProjectUpdate]
  Project --> Issues[PersistentIssue riêng]
  Project --> Assignments[Contractor Assignments]

  Assignments --> Contractor[ProjectContractor catalog]
  Updates --> AssignmentOptional[Optional assignment FK]

  Daily --> S3[Direct S3 + StorageObject]
  S3 --> Celery[Celery derivatives]

  Dash --> Scope[DashboardScope]
  Scope --> SystemScope[SYSTEM]
  Scope --> CustomerScope[CUSTOMER]
  Scope --> ProjectScope[PROJECT]
  Scope --> ContractorScope[CONTRACTOR]
```

## Model map

```mermaid
erDiagram
  CUSTOMERS ||--o{ PROJECTS : owns
  PROJECTS ||--o{ PROJECT_USERS : scoped_to
  PROJECTS ||--o{ REPORT_CATEGORIES : configures
  PROJECTS ||--o{ DAILY_REPORTS : has
  DAILY_REPORTS ||--o{ DAILY_REPORT_SECTIONS : contains
  REPORT_CATEGORIES ||--o{ DAILY_REPORT_SECTIONS : categorizes
  DAILY_REPORT_SECTIONS ||--o{ REPORT_ATTACHMENTS : has

  PROJECTS ||--o{ PERSISTENT_ISSUES : has_separately

  PROJECT_CONTRACTORS ||--o{ PROJECT_CONTRACTOR_ASSIGNMENTS : participates
  PROJECTS ||--o{ PROJECT_CONTRACTOR_ASSIGNMENTS : has

  PROJECTS ||--o{ PROJECT_UPDATES : timeline
  PROJECT_CONTRACTOR_ASSIGNMENTS ||--o{ PROJECT_UPDATES : optional_subject
```

## Suggested packages

Tên file cuối cùng phải theo convention source thật sau khi Codex audit. Gợi ý:

```text
app/models/customer.py
app/models/project_contractor.py
app/models/project_update.py
app/project_operations/
app/templates/project_operations/
```

Không tạo một model/project route song song với `Project` hoặc `ReportCategory` hiện tại.

## Route target

```text
GET  /reports/today
GET  /project-operations
GET  /project-operations/customers/<id>
GET  /project-operations/projects/<id>
GET  /project-operations/projects/<id>/contractors/<role>
GET  /project-operations/projects/<id>/updates
POST /project-operations/projects/<id>/updates
GET  /project-operations/contractors/<id>

GET  /reports/dashboard/system
GET  /reports/dashboard/customers/<id>
GET  /projects/<id>/dashboard
GET  /reports/dashboard/contractors/<id>
GET  /reports/config
```

Có thể dùng API JSON riêng cho chart. Route cũ phải giữ hoặc redirect có kiểm thử.

## Workspace project

```text
Tổng quan
Báo cáo ngày
Báo cáo xuyên suốt
Vấn đề tồn đọng
Đối tác thi công
Đối tác giải pháp
```

## Data lifecycle

- Customer: active → archived.
- ProjectContractor: active → archived.
- Assignment: active/paused/completed/ended.
- ProjectUpdate: active → soft deleted.
- Daily Report/PersistentIssue: giữ lifecycle hiện tại, không coupling mới.
