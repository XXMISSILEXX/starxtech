# Quyết định khóa Phase 9

Tài liệu này là bản dịch trung thực của `Phase_9_Complete_Execution_Package/FINAL_DECISIONS.md`; khi có mâu thuẫn, quyết định trong package là nguồn gốc.

| Chủ đề | Quyết định khóa |
| --- | --- |
| Daily Report section status | Giữ `INFO/GOOD/PROCESSING/ATTENTION/CRITICAL`. |
| Daily Report overall status | Giữ `UPDATED/GOOD/PROCESSING/ATTENTION/CRITICAL`. |
| Health/OpenIssue/observation | Không tạo health model, OpenIssue, observation table hoặc status mapping. |
| PersistentIssue | Domain riêng, không liên quan Daily Report; không auto-create/link từ section. |
| Category | Tái sử dụng `ReportCategory`; không tạo `ProjectReportItem`. Snapshot name/icon chỉ additive khi Step 9.6 và source safety được xác nhận. |
| Required category | Chỉ enforce sau khi form và finalize cùng cập nhật; không phá report cũ. |
| Customer/contractor | Customer và `ProjectContractor` là domain mới, độc lập Partner/CRM; không dùng/FK `Company`, `Partner`, `PartnerRelationship` hoặc route `/partners`. |
| Contractor assignment | Roles `CONSTRUCTION`, `SOLUTION`; cùng contractor/project có thể có cả hai; removal chuyển `ENDED`, giữ lịch sử. |
| ProjectUpdate | Một timeline riêng; assignment FK nullable, phải cùng project. Không attachment MVP, không approval workflow. |
| Lifecycle | Customer/project/contractor archive; assignment end; ProjectUpdate soft-delete. |
| RBAC | Custom role dùng permission catalogue; không hard-code custom role name. Không multi-role/direct per-user permission trong Phase 9. |
| Scope | Tái sử dụng `ProjectUser` và helper hiện tại. |
| Report creation | Chỉ project `ACTIVE` được tạo mới; status khác read-only trong Phase 9. |
| Customer backfill | Gán project cũ vào `Khách hàng chưa phân loại`, vẫn áp scope user project. |
| Dashboard | Missing project hiển thị riêng và giảm submission rate; section chart dùng trực tiếp 5 status; contractor không bị quy kết section/PersistentIssue. |
| System analytics | `PersistentIssue` tồn đọng là `OPEN` + `PROCESSING`, không soft-delete, trong effective project scope. Project-activity payload thêm `total_count`/`percentages`; tỷ lệ dùng tổng activity được trả về, không dùng số project. |
| Navigation shell | `/admin/projects...`, memberships/categories, Customer và project-contractor catalog giữ URL nhưng luôn render shell **Quản lý dự án**. Vai trò/phân quyền là System Admin độc lập. |
| Upload | Daily Report V2, direct S3, HEIC preview, finalize, private attachment và Celery giữ nguyên. |
