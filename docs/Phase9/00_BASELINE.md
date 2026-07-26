# Phase 9 baseline

Ngày xác minh: 2026-07-26. Baseline source là branch `feature/phase-9-project-contractor-management`, HEAD `eb46a6c63a79cc15b8164b57495a7ba8452869f4`.

## Source hiện tại

- `Project` soft-delete, có status `active`, `paused`, `completed`, `archived`, `ProjectUser`, `ReportCategory`, Daily Report và `PersistentIssue`.
- `ProjectUser` là scope theo project. Boolean capability là nguồn quyền project; `project_role_code` chỉ là preset/metadata.
- `ReportCategory` là cấu hình theo project, unique `(project_id, name)`, được section tham chiếu. Không có lý do tạo `ProjectReportItem`.
- Daily Report V2 giữ unique `(project_id, report_date)` và `(project_id, client_request_id)`. Status overall là `UPDATED/GOOD/PROCESSING/ATTENTION/CRITICAL`; section là `INFO/GOOD/PROCESSING/ATTENTION/CRITICAL`.
- V2 dùng upload session, presigned direct S3/MinIO, HEAD/checksum verify, finalize idempotent và Celery derivative sau commit. Attachment là private qua route được authorize.
- `PersistentIssue` độc lập theo project; không FK sang Daily Report, section, category hoặc contractor.
- Dashboard hiện tại tổng hợp `DailyReport.overall_status`, issue riêng, và chỉ các report đã nộp; chưa có submission denominator/missing-project query hay Customer/contractor scope.
- Navigation Reports hiện có: Bảng điều khiển, Dự án, Báo cáo. Partner là module riêng với `Company`, `Partner`, `PartnerRelationship` và route `/partners*`; đây không phải boundary cho Phase 9.

## Runtime/database read-only inventory

- Alembic current/head: `20260725_0026`.
- Roles: `005`, `ADMIN`, `PARTNER`, `PROJECT_MANAGER`, `PROJECT_STAFF`, `REPORTER`, `SUPER_ADMIN`, `VIEWER_ADMIN`.
- Permission rows: 100; `role_permissions` rows: 196.
- Registry system defaults chỉ định nghĩa `SUPER_ADMIN`, `ADMIN`, `VIEWER_ADMIN`; role/grant legacy/custom phải giữ nguyên cho đến khi có reconcile được phê duyệt.

Raw non-secret command output được lưu trong `evidence/`.

## Baseline boundary

Step 9.0 chỉ tạo tài liệu/evidence. Không model, migration, route, template, registry permission, DB grant, test expectation hoặc application behavior nào được đổi.
