# Mô hình dữ liệu mục tiêu

## Customer

```text
id
name
normalized_name
description nullable
is_active
archived_at nullable
created_by_id
updated_by_id nullable
created_at
updated_at
```

Constraints/index:

- unique normalized active name theo convention được chọn;
- index `is_active`, `normalized_name`;
- customer có project không hard-delete.

## Project extension

Thêm additive:

```text
customer_id nullable trước
start_date nullable
expected_end_date nullable
completed_at nullable
```

Tái sử dụng `Project.status` hiện tại nếu enum đã có active/paused/completed/archived. Không tạo cột status thứ hai.

Backfill project hiện có vào một Customer hệ thống:

```text
Khách hàng chưa phân loại
```

## ProjectContractor

```text
id
name
normalized_name
short_name nullable
description nullable
phone nullable
email nullable
address nullable
is_active
archived_at nullable
created_by_id
updated_by_id nullable
created_at
updated_at
```

Không FK tới Partner module.

## ProjectContractorAssignment

```text
id
project_id
contractor_id
role: CONSTRUCTION | SOLUTION
status: ACTIVE | PAUSED | COMPLETED | ENDED
started_on nullable
ended_on nullable
note nullable
created_by_id
updated_by_id nullable
created_at
updated_at
```

Rules:

- project và contractor phải active khi tạo assignment;
- cùng contractor/project được phép hai role;
- không có hai assignment chưa kết thúc trùng project+contractor+role;
- `ENDED` giữ lịch sử;
- không đổi `project_id`, `contractor_id`, `role` sau khi đã có update; kết thúc rồi tạo assignment mới khi cần.

## ProjectUpdate

```text
id
project_id
contractor_assignment_id nullable
update_type: GENERAL | PROGRESS | HANDOVER | CONTRACTOR | STATUS_CHANGE | NOTE
title
content
update_date
created_by_id
updated_by_id nullable
created_at
updated_at
deleted_at nullable
```

Validation:

- assignment nếu có phải thuộc cùng project;
- assignment `ENDED` không nhận update mới;
- title/content giới hạn chiều dài rõ;
- update date không vượt quá policy tương lai; MVP cho phép ngày hiện tại/quá khứ;
- soft delete và AuditLog.

## DailyReportSection optional safety fields

Chỉ thêm khi step 9.6 thực hiện:

```text
category_name_snapshot nullable
category_icon_snapshot nullable
```

- New reports ghi snapshot lúc finalize.
- Report cũ fallback relationship.
- Không thêm health/status mới.

## Không tạo

```text
ProjectReportItem
HealthStatus
OpenIssue
PersistentIssueObservation
DailyReportIssueLink
ContractorIssueResponsibility
```
