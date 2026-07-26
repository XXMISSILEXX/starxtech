# Target domain Phase 9

`Customer 1--N Project`; `ProjectContractor N--N Project` qua `ProjectContractorAssignment`; `Project 1--N ProjectUpdate`; `ProjectUpdate` optional assignment.

## Additive model target

- `Customer`: name/normalized_name, description, active/archive audit fields.
- `Project`: thêm nullable `customer_id`, `start_date`, `expected_end_date`, `completed_at`; tái sử dụng `Project.status`, không thêm status thứ hai.
- `ProjectContractor`: catalog độc lập Partner gồm identity/contact, active/archive audit fields.
- `ProjectContractorAssignment`: project, contractor, role `CONSTRUCTION|SOLUTION`, status `ACTIVE|PAUSED|COMPLETED|ENDED`, date/note/audit. Không có hai assignment chưa ended cùng `(project, contractor, role)`.
- `ProjectUpdate`: project, nullable assignment, type `GENERAL|PROGRESS|HANDOVER|CONTRACTOR|STATUS_CHANGE|NOTE`, title/content/date/audit/soft delete. Assignment phải thuộc cùng project và assignment ended không nhận update mới.

Daily Report và `PersistentIssue` giữ quan hệ/lifecycle hiện tại. Không tạo `HealthStatus`, `OpenIssue`, `PersistentIssueObservation`, `DailyReportIssueLink`, `ContractorIssueResponsibility` hay `ProjectReportItem`.
